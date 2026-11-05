/* PICK's per-example classification pattern: two diagrams, three votes each. */
const el = id => document.getElementById(id);
let current = null;
let rendered = false;
let busy = false;
let polling = false;
let timer;
let displayedId = null;
let pendingPoll = Promise.resolve();
let paused = false;
let history = null;
let historyIndex = 0;
let available = false;
let editing = null;
let properties = [];
let activePropertyId = null;
let canVote = false;

function lock() {
  document.querySelectorAll('.vote').forEach(button => {
    const side = Number(button.closest('.card').dataset.side);
    button.disabled = busy || !rendered || (!history && (!canVote || paused)) ||
      (history && !current.observations?.[side]);
  });
  el('done').disabled = busy || !available || !activePropertyId;
  for (const id of ['add-property', 'explore', 'continue-property', 'cancel-property']) el(id).disabled = busy || !available;
  document.querySelectorAll('#properties button').forEach(b => b.disabled = busy || !available);
  el('history').disabled = busy || !available;
  el('previous').disabled = busy || historyIndex === 0;
  el('next-history').disabled = busy || !history || historyIndex >= history.length - 1;
}

function status(message) {
  el('status').textContent = message;
  el('status').hidden = !message;
}

function error(message) {
  el('error').textContent = message;
  el('error').hidden = !message;
}

function selections(votes) {
  document.querySelectorAll('.card').forEach((card, side) => {
    card.dataset.vote = votes[side] || '';
    card.querySelectorAll('.vote').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.value === votes[side]));
    });
  });
}

async function api(route, body) {
  const response = await fetch(route, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
  });
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'The request failed.');
  return result;
}

async function render(side, index, datum, savedState) {
  const core = window.spytialcore || window.SpytialCore || window.CndCore || window.CnDCore;
  if (!core) throw Error('The diagram renderer could not load. Reload to try again.');
  const instance = new core.JSONDataInstance(datum);
  const evaluator = new core.SGraphQueryEvaluator();
  evaluator.initialize({sourceData: instance});
  try {
    const spec = core.parseLayoutSpec(JSON.stringify(side.program));
    const result = new core.LayoutInstance(spec, evaluator).generateLayout(instance);
    if (result.error) throw Error('This diagram could not be rendered.');
    const graph = document.createElement('webcola-cnd-graph');
    const slot = el(`diagram-${index}`);
    slot.classList.remove('skeleton');
    slot.replaceChildren(graph);
    await graph.setViewOptions({toolbar: 'none', interaction: {nodeDrag: !history, structuralEditing: false}});
    graph.addEventListener('layout-error', event => {
      if (!graph.isConnected) return;
      graph.dataset.failed = 'true';
      rendered = false;
      lock();
      error(event.detail?.message || 'The diagram could not be solved.');
    });
    let timeout, onComplete, onError;
    const complete = new Promise((resolve, reject) => {
      onComplete = resolve;
      onError = event => reject(Error(event.detail?.message || 'The diagram could not be solved.'));
      graph.addEventListener('layout-complete', onComplete, {once: true});
      graph.addEventListener('layout-error', onError, {once: true});
      timeout = setTimeout(() => reject(Error('The diagram did not finish. Reload to try again.')), 30000);
    });
    try { await Promise.all([graph.renderLayout(result.layout, savedState ?
      {priorPositions: savedState, transitionMode: 'replace'} : undefined), complete]); }
    finally {
      clearTimeout(timeout);
      graph.removeEventListener('layout-complete', onComplete);
      graph.removeEventListener('layout-error', onError);
    }
  } finally { evaluator.dispose(); }
}

async function refresh() {
  const state = await api('state');
  available = ['ready', 'empty', 'paused', 'idle'].includes(state.status);
  canVote = state.status === 'ready';
  if (state.properties) syncProperties(state);
  paused = state.status === 'paused';
  el('done').textContent = paused ? 'Resume' : "I'm done";
  if (history) return;
  if (state.status === 'error') throw Error(state.message);
  status(state.message);
  if (!state.question || state.status === 'loading') {
    rendered = false;
    lock();
    return;
  }
  if (displayedId !== state.question.id) {
    rendered = false;
    lock();
    current = state.question;
    document.querySelector('.pair').classList.toggle('preview', current.kind === 'preview');
    document.querySelectorAll('.card').forEach((card, side) => {
      card.hidden = side >= current.sides.length;
      card.querySelector('.votes').hidden = current.kind === 'preview';
    });
    selections(current.votes);
    await Promise.all(current.sides.map((side, index) =>
      render(side, index, current.datum, current.layout_states?.[index])));
    displayedId = current.id;
  } else {
    // Reloading restores partial votes; programmatic revisions may supply a new pair.
    current = state.question;
  }
  rendered = !document.querySelector('webcola-cnd-graph[data-failed]');
  selections(current.votes);
  lock();
}

async function poll() {
  if (polling || busy) return;
  polling = true;
  pendingPoll = refresh();
  try { await pendingPoll; }
  catch (err) { rendered = false; lock(); error(err.message); }
  finally { polling = false; timer = setTimeout(poll, 750); }
}

// Each click is saved immediately. A second vote completes the pair and advances.
document.querySelectorAll('.vote').forEach(button => button.addEventListener('click', async () => {
  if (busy || !rendered || !current) return;
  const questionId = current.id;
  busy = true;
  clearTimeout(timer);
  lock();
  error('');
  const side = Number(button.closest('.card').dataset.side);
  try {
    await pendingPoll;
    if (!rendered || current?.id !== questionId) return;
    await api(history ? 'reclassify' : 'vote', {
      question_id: questionId, side, value: button.dataset.value,
      layout_state: el(`diagram-${side}`).querySelector('webcola-cnd-graph').getLayoutState()
    });
    current.votes[side] = button.dataset.value;
    selections(current.votes);
    if (!history) await refresh();
  } catch (err) { error(err.message); }
  finally { busy = false; lock(); timer = setTimeout(poll, 750); }
}));

async function showHistory() {
  current = history[historyIndex];
  if (!current) { status('No judgments yet.'); return; }
  rendered = false;
  lock();
  document.querySelector('.pair').classList.remove('preview');
  document.querySelectorAll('.card').forEach(card => { card.hidden = false; card.querySelector('.votes').hidden = false; });
  await Promise.all(current.sides.map((side, i) => render(side, i, current.datum, current.layout_states?.[i])));
  rendered = !document.querySelector('webcola-cnd-graph[data-failed]');
  selections(current.votes);
  status(current.prompt);
  el('history-position').textContent = `${historyIndex + 1} / ${history.length}`;
  el('previous').disabled = historyIndex === 0;
  el('next-history').disabled = historyIndex === history.length - 1;
}

async function action(fn) {
  if (busy) return;
  busy = true; clearTimeout(timer); lock(); error('');
  try { await pendingPoll; await fn(); }
  catch (err) { error(err.message); }
  finally { busy = false; lock(); timer = setTimeout(poll, 750); }
}
el('done').addEventListener('click', () => action(async () => {
  status(paused ? 'Resuming…' : 'Saving…');
  await api(paused ? 'resume' : 'done', {});
  if (history) closeHistory();
  await refresh();
}));
function closeHistory() {
  history = null; current = null; displayedId = null;
  el('history').textContent = 'History';
  for (const id of ['previous', 'next-history', 'history-position']) el(id).hidden = true;
}
el('history').addEventListener('click', () => action(async () => {
  if (history) { closeHistory(); await refresh(); return; }
  const records = (await api('history')).records;
  if (!records.length) { status('No judgments yet.'); return; }
  history = records; historyIndex = records.length - 1;
  el('history').textContent = 'Back';
  for (const id of ['previous', 'next-history', 'history-position']) el(id).hidden = false;
  await showHistory();
}));
el('previous').addEventListener('click', () => action(async () => { historyIndex--; await showHistory(); }));
el('next-history').addEventListener('click', () => action(async () => { historyIndex++; await showHistory(); }));
function syncProperties(state) {
  const previousActive = activePropertyId;
  properties = state.properties;
  activePropertyId = state.active_property_id;
  if (activePropertyId !== previousActive && properties.length && !busy) el("property-form").hidden = true;
  const signature = JSON.stringify([properties.map(p => [p.id, p.prompt, p.status]), activePropertyId]);
  if (el('properties').dataset.signature === signature) return;
  el('properties').dataset.signature = signature;
  el('properties').replaceChildren(...properties.map(property => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = `${property.status === 'accepted' ? '✓ ' : ''}${property.prompt}`;
    button.setAttribute('aria-current', String(property.id === activePropertyId));
    button.setAttribute('aria-label', `Edit property: ${property.prompt}`);
    button.addEventListener('click', () => openProperty(property));
    return button;
  }));
  if (!properties.length && el('property-form').hidden) openProperty();
}
function openProperty(property = null) {
  editing = property?.id || null;
  el('property-form').hidden = false;
  el('property-prompt').value = property?.prompt || '';
  el('explore').textContent = editing ? 'Revise' : 'Explore';
  el('continue-property').hidden = !editing;
  el('cancel-property').hidden = !properties.length;
  el('property-prompt').focus();
}
el('add-property').addEventListener('click', () => openProperty());
el('cancel-property').addEventListener('click', () => { el('property-form').hidden = true; });
el('continue-property').addEventListener('click', () => action(async () => {
  await api('resume', {property_id: editing});
  el('property-form').hidden = true;
  if (history) closeHistory();
  displayedId = null;
  await refresh();
}));
el('property-form').addEventListener('submit', event => {
  event.preventDefault();
  action(async () => {
    status('Drafting property interpretations…');
    await api(editing ? 'edit-property' : 'add-property', {
      prompt: el('property-prompt').value, property_id: editing
    });
    el('property-form').hidden = true;
    if (history) closeHistory();
    displayedId = null;
    await refresh();
  });
});
window.addEventListener('pagehide' , () => clearTimeout(timer));
poll();
