const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../connectors/chrome/popup.js'), 'utf8');

async function submit(tabUrl, gateway = 'http://127.0.0.1:8001') {
  let listener;
  const calls = [];
  const result = {textContent: ''};
  const ids = {
    report: {addEventListener: (_, callback) => { listener = callback; }},
    gateway: {value: gateway},
    code: {value: 'temporary-code'},
    result,
  };
  vm.runInNewContext(source, {
    URL,
    document: {getElementById: id => ids[id]},
    chrome: {tabs: {query: async () => [{url: tabUrl}]}},
    fetch: async (url, request) => {
      calls.push([url, JSON.parse(request.body)]);
      return {ok: true};
    },
  });
  await listener({preventDefault() {}, currentTarget: {querySelector: () => ({})}});
  return {calls, result: result.textContent};
}

test('reports ChatGPT without sending the conversation URL', async () => {
  const result = await submit('https://chatgpt.com/c/private-id?secret=secret');
  assert.deepEqual(result.calls, [
    ['http://127.0.0.1:8001/api/connectors/chrome/observation', {service: 'chatgpt'}],
  ]);
});

test('rejects unrelated pages and remote gateways', async () => {
  assert.equal((await submit('https://chatgpt.com.example.org/')).calls.length, 0);
  assert.equal((await submit('https://chatgpt.com/', 'https://example.org')).calls.length, 0);
});
