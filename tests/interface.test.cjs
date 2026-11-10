// Dependency-free regression checks for UI state helpers; no browser or server needed.
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

function workspace(fetch) {
  const elements = new Map();
  let document;
  class Element {
    constructor(tag = 'div') {
      this.tagName = tag; this.children = []; this.dataset = {}; this.listeners = {};
      this.value = ''; this.options = []; this.classList = {toggle() {}, remove() {}};
      this.textContent = ''; this.open = false;
    }
    addEventListener(name, fn) { this.listeners[name] = fn; }
    setAttribute() {}
    removeAttribute() {}
    focus() { document.activeElement = this; }
    contains(node) { return this === node || this.children.some(child => child.contains(node)); }
    append(...nodes) { nodes.forEach(node => this.insertBefore(node, null)); }
    insertBefore(node, reference) {
      if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1);
      const at = reference ? this.children.indexOf(reference) : this.children.length;
      this.children.splice(at, 0, node); node.parent = this;
    }
    replaceChildren(...nodes) { this.children.forEach(node => { node.parent = null; }); this.children = []; this.append(...nodes); }
    replaceWith(node) {
      const parent = this.parent;
      parent.children.splice(parent.children.indexOf(this), 1, node); node.parent = parent; this.parent = null;
      if (this.contains(document.activeElement)) document.activeElement = document.body;
    }
    remove() { if (this.parent) this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; }
    querySelectorAll(selector) {
      const tags = selector.split(','); const found = [];
      for (const child of this.children) {
        if (tags.includes(child.tagName)) found.push(child);
        found.push(...child.querySelectorAll(selector));
      }
      return found;
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  }
  document = {
    body: new Element('body'),
    activeElement: null,
    getElementById(id) { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); },
    createElement: tag => new Element(tag),
    querySelector: selector => document.getElementById(selector),
    querySelectorAll: () => [],
    addEventListener() {},
  };
  document.activeElement = document.body;
  const context = vm.createContext({document, fetch, URLSearchParams, Intl, Date, Map, Set, Boolean, JSON,
    location: {pathname: '/', search: ''}, history: {}, window: {addEventListener() {}},
    setInterval() {}, Option: function(text, value) { const node = new Element('option'); node.textContent = text; node.value = value; return node; }});
  vm.runInContext(readFileSync(resolve(__dirname, '../agentgate/static/app.js'), 'utf8'), context);
  return {context, document, Element};
}

test('late response cannot restore workspace data after disconnect', async () => {
  let release, jsonStarted;
  const started = new Promise(resolve => { jsonStarted = resolve; });
  const {context, document} = workspace(async () => ({ok: true, json() { jsonStarted(); return new Promise(resolve => { release = resolve; }); }}));
  vm.runInContext("token='example-reviewer-credential';", context);
  const result = context.api('/api/agents');
  await started;
  document.getElementById('disconnect').listeners.click();
  release([{agent_id: 'private-record'}]);
  await assert.rejects(result, /access changed/);
  assert.equal(vm.runInContext('token', context), '');
  assert.equal(document.getElementById('total').textContent, '—');
  assert.equal(document.getElementById('last-updated').textContent, 'No data loaded yet');
});

test('unavailable server produces a useful message rather than a zero count', async () => {
  const {context, document} = workspace(async () => { throw new TypeError('fetch failed'); });
  vm.runInContext("token='example-reviewer-credential';", context);
  await context.load();
  assert.match(document.getElementById('status').textContent, /local server is running/);
  assert.match(document.getElementById('status').textContent, /unavailable/);
  assert.equal(document.getElementById('total').textContent, '—');
  assert.equal(document.getElementById('.connection').dataset.state, 'error');
});

test('failed refresh explicitly marks cached totals as stale', async () => {
  const {context, document} = workspace(async () => { throw new TypeError('offline'); });
  vm.runInContext("token='example-reviewer-credential'; loadedAt.set('/',new Date());", context);
  document.getElementById('total').textContent = '42';
  await context.load(true);
  assert.equal(document.getElementById('total').textContent, '42');
  assert.equal(document.getElementById('.connection').dataset.state, 'stale');
  assert.match(document.getElementById('status').textContent, /Previously loaded data/);
  assert.match(document.getElementById('last-updated').textContent, /may be out of date/);
});

test('live row inserts and changed records preserve expanded evidence and keyboard focus', () => {
  const {context, document, Element} = workspace();
  const container = new Element();
  const build = record => {
    const article = new Element('article'); const details = new Element('details');
    const summary = new Element('summary'); summary.textContent = record.id;
    details.append(summary); article.append(details); return article;
  };
  const key = record => record.id;
  const signature = record => JSON.stringify(record);
  context.syncRows(container, [{id: 'a'}, {id: 'b'}], key, signature, build);
  const old = container.children[0]; old.children[0].open = true; old.children[0].children[0].focus();
  context.syncRows(container, [{id: 'new'}, {id: 'a'}, {id: 'b'}], key, signature, build);
  assert.equal(container.children[1], old);
  assert.equal(document.activeElement, old.children[0].children[0]);
  context.syncRows(container, [{id: 'new'}, {id: 'a', outcome: 'executed'}, {id: 'b'}], key, signature, build);
  assert.notEqual(container.children[1], old);
  assert.equal(container.children[1].children[0].open, true);
  assert.equal(document.activeElement, container.children[1].children[0].children[0]);
});

test('a completed demo cannot overwrite disconnect guidance while its refresh is in flight', async () => {
  let releaseRefresh, refreshStarted;
  const refreshing = new Promise(resolve => { refreshStarted = resolve; });
  const {context, document} = workspace(async path => {
    if (path.endsWith('/run')) return {ok: true, json: async () => ({matched:true, action:{id:'demo-action', outcome:'executed', reason:'Simulated result'}})};
    refreshStarted();
    return new Promise(resolve => { releaseRefresh = resolve; });
  });
  vm.runInContext(`token='example-reviewer-credential';
    scenarioItems=[{id:'sample',agent_id:'support-agent',name:'Sample action',description:'Synthetic',tool:'documents.read',arguments:{document_id:'refund-policy'},expected:'executed'}];`, context);
  document.getElementById('demo-agent').value='support-agent';
  context.renderScenarios();
  const button=document.getElementById('scenarios').querySelector('button');
  const completing=button.listeners.click();
  await refreshing;
  document.getElementById('disconnect').listeners.click();
  releaseRefresh({ok:true,json:async()=>[]});
  await completing;
  assert.match(document.getElementById('status').textContent,/Disconnected/);
  assert.equal(document.getElementById('scenarios').children[0].textContent,'Connect to run demo cases.');
});
