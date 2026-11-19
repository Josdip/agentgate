'use strict';

const byId = id => document.getElementById(id);
const seen = new Map();
let token = '';
let loading = false;

const states = {
  pending: 'Awaiting review', ready: 'Authorized · awaiting execution', denied: 'Blocked by rule',
  rejected: 'Rejected by reviewer', executing: 'Execution started · receipt pending',
  executed: 'Executed', failed: 'Execution failed', expired: 'Expired', superseded: 'Authorization withdrawn · rule changed',
};
const tools = {read_file: 'Read file', write_file: 'Write file'};
const announce = text => { byId('status').textContent = text; };

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

function text(tag, value) {
  const node = document.createElement(tag);
  node.textContent = value;
  return node;
}

function renderActivity(actions) {
  const activity = byId('activity');
  for (const id of seen.keys()) {
    if (!actions.some(action => action.id === id)) {
      seen.get(id).node.remove();
      seen.delete(id);
    }
  }
  if (!actions.length) {
    activity.textContent = 'No managed tool actions yet.';
    return;
  }
  if (!seen.size) activity.textContent = '';
  for (const action of [...actions].reverse()) {
    const existing = seen.get(action.id);
    if (existing?.state === action.status) continue;
    const node = text('article', '');
    node.append(
      text('strong', tools[action.tool] + ' · ' + action.path),
      text('p', states[action.status] + ' · Rule ' + action.decision + ' · ' + new Date(action.created * 1000).toLocaleString())
    );
    if (action.size !== null) {
      node.append(text('p', action.size + ' bytes · Proposal SHA-256 ' + action.digest));
    }
    if (action.status === 'pending') {
      for (const approve of [true, false]) {
        const button = text('button', approve ? 'Approve request' : 'Reject request');
        button.type = 'button';
        button.addEventListener('click', async () => {
          const buttons = [...node.querySelectorAll('button')];
          buttons.forEach(item => { item.disabled = true; });
          try {
            await api('/api/proposals/' + action.id + '/review', 'POST', {approve});
            announce(approve ? 'Request authorized. Waiting for execution.' : 'Request rejected.');
            await refresh();
          } catch (error) {
            announce(error.message);
          } finally {
            buttons.forEach(item => { item.disabled = false; });
          }
        });
        node.append(button);
      }
    }
    if (existing) {
      const focused = existing.node.contains(document.activeElement);
      existing.node.replaceWith(node);
      if (focused) {
        node.tabIndex = -1;
        node.focus();
      }
    } else {
      activity.prepend(node);
    }
    seen.set(action.id, {node, state: action.status});
  }
}

async function refresh(loadRules = false) {
  if (loading) return;
  loading = true;
  try {
    const data = await api('/api/overview');
    const agent = data.agents[0];
    const descriptions = {
      managed: 'Sonar · Managed. Pairing verified at last scan.',
      discovered: 'Sonar · Discovered. The runtime identified itself without verified pairing.',
      offline: 'Sonar · Unreachable at last scan.',
    };
    byId('agent').textContent = agent
      ? descriptions[agent.state] + ' ' + new Date(agent.scanned * 1000).toLocaleString()
      : 'No agents discovered yet.';
    if (loadRules) {
      for (const rule of data.rules) byId(rule.tool).value = rule.mode;
    }
    renderActivity(data.activity);
  } finally {
    loading = false;
  }
}

byId('connect').addEventListener('submit', async event => {
  event.preventDefault();
  token = byId('token').value.trim();
  try {
    await refresh(true);
    byId('token').value = '';
    byId('connect').hidden = true;
    byId('workspace').hidden = false;
    announce('Reviewer connected.');
  } catch (error) {
    token = '';
    announce(error.message);
  }
});

byId('scan').addEventListener('click', async event => {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    const result = await api('/api/discovery', 'POST');
    announce(result.state === 'offline' ? 'No compatible Sonar endpoint responded.' : 'Sonar responded to the scan.');
    await refresh();
  } catch (error) {
    announce(error.message);
  } finally {
    button.disabled = false;
  }
});

for (const button of document.querySelectorAll('[data-save]')) {
  button.addEventListener('click', async () => {
    const tool = button.dataset.save;
    button.disabled = true;
    try {
      await api('/api/rules/' + tool, 'PUT', {mode: byId(tool).value});
      announce(tools[tool] + ' rule saved.');
    } catch (error) {
      announce(error.message);
    } finally {
      button.disabled = false;
    }
  });
}

setInterval(() => {
  if (token && !byId('workspace').hidden) refresh().catch(error => announce(error.message));
}, 2500);
