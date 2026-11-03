/* PICK's per-example classification pattern: two diagrams, three votes each. */
const el = id => document.getElementById(id);
let current = null;
let rendered = false;
let busy = false;
let polling = false;
let timer;
let displayedId = null;
let pendingPoll = Promise.resolve();

function lock() {
  document.querySelectorAll('.vote').forEach(button => {
    button.disabled = busy || !rendered;
  });
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

async function render(side, index, datum) {
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
    await graph.setViewOptions({toolbar: 'none', interaction: {nodeDrag: false, structuralEditing: false}});
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
    try { await Promise.all([graph.renderLayout(result.layout), complete]); }
    finally {
      clearTimeout(timeout);
      graph.removeEventListener('layout-complete', onComplete);
      graph.removeEventListener('layout-error', onError);
    }
  } finally { evaluator.dispose(); }
}

async function refresh() {
  const state = await api('state');
  if (state.status === 'error') throw Error(state.message);
  status(state.message);
  if (state.status !== 'ready') {
    rendered = false;
    lock();
    return;
  }
  if (displayedId !== state.question.id) {
    rendered = false;
    lock();
    current = state.question;
    selections(current.votes);
    await Promise.all(current.sides.map((side, index) => render(side, index, current.datum)));
    displayedId = current.id;
  } else {
    // Reloading restores partial votes; programmatic revisions may supply a new pair.
    current = state.question;
  }
  rendered = !document.querySelector('webcola-cnd-graph[data-failed]');
  if (rendered) error('');
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
    await api('vote', {
      question_id: questionId, side, value: button.dataset.value,
      layout_state: el(`diagram-${side}`).querySelector('webcola-cnd-graph').getLayoutState()
    });
    current.votes[side] = button.dataset.value;
    selections(current.votes);
    await refresh();
  } catch (err) { error(err.message); }
  finally { busy = false; lock(); timer = setTimeout(poll, 750); }
}));
window.addEventListener('pagehide', () => clearTimeout(timer));
poll();
