// Keep the released checker and selector evaluator loaded for a Python session.
// The CLI's exported main still owns parsing, checking, diagnostics and versions.
const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');
const checker = require(process.argv[2]);
const {evaluate} = require('./_eval_selectors.js');
const directory = process.argv[3];
const input = path.join(directory, 'cases.json');
const write = process.stdout.write.bind(process.stdout);

// Core diagnostics must not mix with the JSON-lines response protocol.
process.stdout.write = process.stderr.write.bind(process.stderr);
for (const method of ['log', 'info', 'debug']) console[method] = console.error;

function check(cases) {
  fs.writeFileSync(input, JSON.stringify({cases}));
  let output = '';
  const previous = process.stdout.write;
  process.stdout.write = chunk => { output += chunk; return true; };
  try {
    // Python enforces the hard timeout and kills this process if it expires.
    const code = checker.main(['--timeout', '0', input]);
    if (code !== 0 && code !== 1) throw Error(`Core checker exited ${code}`);
    return JSON.parse(output);
  } finally {
    process.stdout.write = previous;
  }
}

readline.createInterface({input: process.stdin}).on('line', line => {
  let response;
  try {
    const request = JSON.parse(line);
    if (!['check', 'selectors'].includes(request.kind)) throw Error('Unknown request');
    const value = request.kind === 'check' ? check(request.cases) : evaluate(request);
    response = {ok: true, value};
  } catch (error) {
    response = {ok: false, error: String(error.message || error)};
  }
  write(JSON.stringify(response) + '\n');
});
