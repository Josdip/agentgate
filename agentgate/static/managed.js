'use strict';

const byId = id => document.getElementById(id);
const tools = {read_file: 'Read file', write_file: 'Write file'};
const states = {
  pending: 'Awaiting review', ready: 'Authorized · awaiting execution', denied: 'Blocked by rule',
  rejected: 'Rejected by reviewer', executing: 'Execution started · receipt pending',
  executed: 'Executed', failed: 'Execution failed', expired: 'Expired',
  superseded: 'Authorization withdrawn · rule changed',
};
const pages = {'/': 'home', '/agents': 'agents', '/activity': 'activity', '/rules': 'rules', '/security': 'security'};
const announce = message => { byId('status').textContent = message; };
let token = '';
let snapshot = null;
let filter = '';
let search = '';
let generation = 0;
let lastView = '';
let busy = false;

async function api(path, method = 'GET', body) {
  const response = await fetch(path, {
    method,
    headers: {Authorization: 'Bearer ' + token, 'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'AgentGate request failed.');
  return data;
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

function button(label, execute, style) {
  const node = element('button', label, style);
  node.type = 'button';
  node.addEventListener('click', async () => {
    node.disabled = true;
    try { await execute(); }
    catch (error) { announce(error.message); }
    finally { node.disabled = false; }
  });
  return node;
}

function renderAction(action) {
  const item = element('article', '', 'action');
  const head = element('div', '', 'action-head');
  head.append(element('strong', 'Sonar · ' + tools[action.tool] + ' · ' + action.path),
    element('span', action.decision === "invalid request" ? "Blocked · invalid request" : states[action.status], 'badge ' + action.status));
  item.append(head, element('p', 'Rule: ' + action.decision + ' · ' +
    new Date(action.created * 1000).toLocaleString(), 'help'));
  if (action.size !== null) {
    item.append(element('p', action.size + ' bytes · Proposal SHA-256 ' + action.digest, 'help'));
  }
  if (action.status === 'pending') {
    const review = element('div', '', 'review');
    for (const approve of [true, false]) {
      review.append(button(approve ? 'Approve request' : 'Reject request', async () => {
        await api('/api/proposals/' + action.id + '/review', 'POST', {approve});
        announce(approve ? 'Request authorized. Waiting for execution.' : 'Request rejected.');
        await refresh();
      }, approve ? '' : 'reject'));
    }
    item.append(review);
  }
  return item;
}

function renderDirectory(agent, externalAgents) {
  const directory = byId('agent-directory');
  if (!agent && !externalAgents.length) {
    byId('agent-count').textContent = 'No agents discovered yet.';
    directory.replaceChildren();
    return;
  }
  const rows = [];
  if (agent) {
    const state = {discovered: 'Discovered · awaiting enrollment', managed: 'Managed', offline: 'Unreachable'};
    const row = element('tr', '');
    for (const value of ['Sonar · Local AI assistant', 'Local operator', 'This computer', state[agent.state],
      new Date(agent.scanned * 1000).toLocaleString()]) row.append(element('td', value));
    const cell = element('td', '');
    if (agent.state === 'discovered') {
      cell.append(button('Add Sonar', () => byId('enrollment').showModal()));
    }
    if (agent.url) {
      const link = element('a', 'Open managed Sonar');
      link.href = agent.url;
      link.target = '_blank';
      link.rel = 'noopener';
      cell.append(link);
    }
    row.append(cell);
    rows.push(row);
  }
  for (const observed of externalAgents) {
    const row = element('tr', '');
    const location = observed.connector === 'chrome' ? 'Chrome · ChatGPT' : 'AWS Bedrock · ' + observed.scope;
    for (const value of [observed.name, '—', location,
      'Discovered · ' + observed.provider_status, new Date(observed.scanned * 1000).toLocaleString(),
      'Inventory only']) row.append(element('td', value));
    rows.push(row);
  }
  directory.replaceChildren(...rows);
  byId('agent-count').textContent = rows.length + (rows.length === 1 ? ' agent' : ' agents');

}

function render() {
  const page = pages[location.pathname] || 'home';
  for (const name of Object.values(pages)) byId(name + '-page').hidden = name !== page;
  for (const link of document.querySelectorAll('nav [data-nav]')) {
    if (pages[new URL(link.href).pathname] === page) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  if (!snapshot) return;
  const {agents, external_agents: externalAgents = [], activity, counts} = snapshot;
  const agent = agents[0];
  const view = JSON.stringify([page, page === 'agents' ? [agent, externalAgents] : [agent, activity, counts, filter, search]]);
  if (view === lastView) return;
  lastView = view;
  if (page === 'agents') renderDirectory(agent, externalAgents);
  if (page === 'home') {
    for (const status of ['pending', 'denied', 'executed', 'total']) byId(status).textContent = counts[status];
    byId('attention').textContent = counts.pending + ' requests awaiting review';
    byId('coverage').textContent = agent?.state === 'managed' ? 'Sonar project files are governed.' : 'No managed agent is running.';
    byId('recent-actions').replaceChildren(...activity.slice(0, 3).map(renderAction));
  }
  if (page === 'activity') {
    const actions = activity.filter(action => (!filter || action.status === filter) &&
      (!search || (action.tool + ' ' + action.path).toLowerCase().includes(search)));
    byId('activity-count').textContent = actions.length + ' actions';
    byId('actions').replaceChildren(...actions.map(renderAction));
  }
  if (page === 'security') {
    byId('security-coverage').textContent = agent?.state === 'managed'
      ? 'The managed Sonar session enforces project file read and write rules.'
      : 'No managed Sonar session is running.';
  }
}

async function refresh(loadRules = false) {
  const current = generation;
  const data = await api('/api/overview');
  if (current !== generation) return;
  snapshot = data;
  byId("external-connectors").hidden = !Array.isArray(data.external_agents);
  if (loadRules) for (const rule of data.rules) byId(rule.tool).value = rule.mode;
  render();
}

function navigate() {
  filter = new URLSearchParams(location.search).get('outcome') || '';
  byId('filter').value = filter;
  render();
}
document.addEventListener('click', event => {
  const link = event.target.closest('[data-nav]');
  if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  history.pushState({}, '', link.href);
  navigate();
});
window.addEventListener('popstate', navigate);

async function connect(reviewerToken) {
  token = reviewerToken;
  try {
    await refresh(true);
    byId('token').value = '';
    byId('connect').hidden = true;
    byId('disconnect').hidden = false;
    byId('workspace-data').hidden = false;
    announce('Reviewer connected.');
  } catch (error) {
    token = '';
    announce(error.message);
  }
}

byId('connect').addEventListener('submit', event => {
  event.preventDefault();
  connect(byId('token').value.trim());
});

const firstRunCode = new URLSearchParams(location.hash.slice(1)).get('connect');
if (firstRunCode) {
  history.replaceState(history.state, '', location.pathname + location.search);
  api('/api/first-run/connection', 'POST', {code: firstRunCode})
    .then(({token: reviewerToken}) => connect(reviewerToken))
    .catch(error => announce(error.message));
}
byId('disconnect').addEventListener('click', () => {
  generation++;
  token = '';
  snapshot = null;
  byId('chrome-token').value = '';
  byId('chrome-pairing').hidden = true;
  lastView = '';
  byId('workspace-data').hidden = true;
  byId('disconnect').hidden = true;
  byId('connect').hidden = false;
  announce('Disconnected.');
});

for (const [id, action] of [
  ['scan', async () => {
    const result = await api('/api/discovery', 'POST');
    announce(result.state === 'offline' ? 'No running standalone Sonar was found.' : 'Sonar found.');
    await refresh();
  }],
  ['confirm-enroll', async () => {
    byId('enrollment').close();
    announce('Starting managed Sonar…');
    await api('/api/enrollment', 'POST');
    await refresh();
    announce('Managed Sonar is ready. Open it from the Agents page.');
  }],
  ['refresh', () => refresh()],
]) {
  byId(id).addEventListener('click', async event => {
    const control = event.currentTarget;
    control.disabled = true;
    try { await action(); }
    catch (error) { announce(error.message); }
    finally { control.disabled = false; }
  });
}
byId('chrome-code').addEventListener('click', async () => {
  const current = generation;
  try {
    const result = await api('/api/connectors/chrome/code', 'POST');
    if (current !== generation) return;
    byId('chrome-origin').value = location.origin;
    byId('chrome-token').value = result.code;
    byId('chrome-pairing').hidden = false;
    announce('Copy the discovery code into the Chrome extension.');
  } catch (error) { announce(error.message); }
});
byId('bedrock-scan').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button');
  button.disabled = true;
  try {
    const result = await api('/api/connectors/bedrock/discovery', 'POST', {
      region: byId('bedrock-region').value.trim(), profile: byId('bedrock-profile').value.trim(),
    });
    await refresh();
    announce('Bedrock agents discovered: ' + result.count + '.');
  } catch (error) { announce(error.message); }
  finally { button.disabled = false; }
});
byId('cancel-enroll').addEventListener('click', () => byId('enrollment').close());
byId('activity-filters').addEventListener('submit', event => {
  event.preventDefault();
  filter = byId('filter').value;
  search = byId('activity-search').value.toLowerCase();
  render();
});
for (const control of document.querySelectorAll('[data-save]')) {
  control.addEventListener('click', async () => {
    const tool = control.dataset.save;
    control.disabled = true;
    try {
      await api('/api/rules/' + tool, 'PUT', {mode: byId(tool).value});
      announce(tools[tool] + ' rule saved.');
      await refresh();
    } catch (error) { announce(error.message); }
    finally { control.disabled = false; }
  });
}
navigate();
setInterval(async () => {
  if (!token || busy) return;
  busy = true;
  try { await refresh(); }
  catch (error) { if (token) announce(error.message); }
  finally { busy = false; }
}, 3000);
