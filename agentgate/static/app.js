'use strict';
let token = '';
let actions = [];
const $ = (id) => document.getElementById(id);
const status = (message) => { $('status').textContent = message; };
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
async function api(path, options = {}) {
  const requestToken = token;
  const response = await fetch(path, {...options, headers: {
    'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json'
  }});
  if (token !== requestToken || !token) throw new Error('Session changed. Connect again.');
  if (!response.ok) {
    if (response.status === 401) throw new Error('Access denied. Check your reviewer token.');
    if (response.status === 409) throw new Error('Data changed since you loaded it. Reconnect to reload the profile, or refresh reviewed actions.');
    if (response.status === 422) throw new Error('Invalid values. Check field lengths, provider/model names, and duplicate model entries.');
    throw new Error(`Request failed (${response.status}).`);
  }
  return response.json();
}
function render() {
  for (const key of ['denied', 'pending', 'executed']) {
    $(key).textContent = actions.filter((a) => a.outcome === key).length;
  }
  $('total').textContent = actions.length;
  const container = $('actions');
  container.replaceChildren();
  const filtered = actions.filter((a) => $('filter').value === 'all' || a.outcome === $('filter').value);
  if (!filtered.length) container.append(element('div', 'No activity matches this view. Run the demo or change the filter.', 'empty'));
  for (const action of filtered) {
    const card = element('article', undefined, 'action');
    const head = element('div', undefined, 'action-head');
    head.append(element('strong', action.tool), element('span', action.outcome, `badge ${action.outcome}`),
      element('span', new Date(action.created_at).toLocaleString(), 'meta'));
    card.append(head, element('p', action.reason, 'reason'),
      element('div', `${action.rule} · ${action.risk} risk · run ${action.run_id}`, 'rule'));
    const details = element('details');
    details.append(element('summary', 'Inspect request & result'), element('pre', JSON.stringify({
      id: action.id, agent: action.agent_id, arguments: action.arguments, result: action.result,
      reviewer: action.reviewer_id, reviewed_at: action.reviewed_at
    }, null, 2)));
    card.append(details);
    if (action.outcome === 'pending') {
      const buttons = element('div', undefined, 'review');
      for (const approve of [true, false]) {
        const button = element('button', approve ? 'Approve simulated refund' : 'Reject', approve ? '' : 'reject');
        button.addEventListener('click', async () => {
          buttons.querySelectorAll('button').forEach((b) => { b.disabled = true; });
          try {
            await api(`/api/actions/${encodeURIComponent(action.id)}/review`, {
              method: 'POST', body: JSON.stringify({approve})
            });
            await load();
            status(approve ? 'Refund approved and simulated execution recorded.' : 'Action rejected.');
          } catch (error) { status(error.message); buttons.querySelectorAll('button').forEach((b) => { b.disabled = false; }); }
        });
        buttons.append(button);
      }
      card.append(buttons);
    }
    container.append(card);
  }
}

let profile = null;
let loading = false;
let editorReady = false;
let scenarioItems = [];
const demoResults = new Map();
const runningScenarios = new Set();

function modelRow(connection = {}) {
  const row = element('div', undefined, 'model-row');
  for (const key of ['provider', 'model']) {
    const input = element('input');
    input.placeholder = key === 'provider' ? 'Provider name' : 'Model name / ID';
    input.setAttribute('aria-label', key === 'provider' ? 'Model provider' : 'Model name');
    input.required = true;
    input.maxLength = key === 'provider' ? 80 : 120;
    input.dataset.field = key;
    input.value = connection[key] || '';
    row.append(input);
  }
  const remove = element('button', 'Remove', 'secondary');
  remove.type = 'button';
  remove.addEventListener('click', () => row.remove());
  row.append(remove);
  $('model-rows').append(row);
}
function fillEditor() {
  $('agent-name').value = profile.display_name;
  $('agent-description').value = profile.description;
  $('model-rows').replaceChildren();
  profile.model_connections.forEach(modelRow);
  $('profile-form').dataset.revision = profile.revision;
  editorReady = true;
}
function renderProfile() {
  const container = $('profile-summary');
  container.className = '';
  container.replaceChildren();
  container.append(element('h3', profile.display_name), element('p', profile.description, 'help'),
    element('p', `${profile.agent_id} · revision ${profile.revision} · synthetic execution`, 'rule'));
  const facts = element('div', undefined, 'profile-facts');
  const a = profile.activity;
  facts.append(element('p', `${a.total_actions} lifetime actions · ${a.denied} blocked · ${a.pending} pending`),
    element('p', `Last observed: ${a.last_seen ? new Date(a.last_seen).toLocaleString() : 'No activity yet'}`));
  container.append(facts, element('h3', 'LLM connections'));
  if (!profile.model_connections.length) container.append(element('p', 'None registered. Demo requests are scripted; no LLM is connected.', 'help'));
  for (const connection of profile.model_connections) {
    container.append(element('p', `${connection.provider} / ${connection.model} · registered, unverified`, 'model-entry'));
  }
  container.append(element('h3', 'Enforced tool access & permissions'));
  const tools = element('div', undefined, 'tool-grid');
  for (const tool of profile.tools) {
    const card = element('article', undefined, 'tool-card');
    card.append(element('strong', tool.tool), element('p', tool.permission),
      element('p', `Scope: ${tool.scope.join(', ')}`, 'help'), element('p', tool.approval, 'rule'));
    tools.append(card);
  }
  container.append(tools, element('p', 'All other tools denied · agent cannot approve actions · permissions come from gateway policy', 'help'));
  $('history-list').replaceChildren();
  for (const entry of profile.history) {
    const item = element('details');
    item.append(element('summary', `Revision ${entry.revision} · ${new Date(entry.changed_at).toLocaleString()} · ${entry.changed_by}`),
      element('pre', JSON.stringify(entry.metadata, null, 2)));
    $('history-list').append(item);
  }
  $('profile-editor').hidden = false;
  $('profile-history').hidden = false;
  if (!editorReady) fillEditor();
}
function renderScenarios() {
  const container = $('scenarios');
  container.replaceChildren();
  scenarioItems.forEach((item, index) => {
    const card = element('article', undefined, 'scenario');
    card.append(element('div', `CASE ${String(index + 1).padStart(2, '0')} · EXPECT ${item.expected.toUpperCase()}`, 'eyebrow'),
      element('h3', item.name), element('p', item.description, 'help'));
    const request = element('details');
    request.append(element('summary', 'Preview tool request'), element('pre', JSON.stringify({tool:item.tool, arguments:item.arguments}, null, 2)));
    card.append(request);
    const result = demoResults.get(item.id);
    const busy = runningScenarios.has(item.id);
    const run = element('button', busy ? 'Evaluating…' : result ? 'Run again' : 'Run scenario');
    run.disabled = busy || !token;
    run.addEventListener('click', async () => {
      runningScenarios.add(item.id); renderScenarios();
      status(`Submitting ${item.name} through the policy gateway…`);
      try {
        const outcome = await api(`/api/demo/scenarios/${encodeURIComponent(item.id)}/run`, {method:'POST'});
        demoResults.set(item.id, outcome);
        await load(true);
        status(`${item.name}: ${outcome.action.outcome}. ${outcome.action.reason}`);
      } catch (error) { status(error.message); }
      finally { runningScenarios.delete(item.id); renderScenarios(); }
    });
    card.append(run);
    if (busy) card.append(element('p', 'Request submitted → policy evaluation → audit record', 'help'));
    if (result) {
      const current = actions.find((action) => action.id === result.action.id) || result.action;
      const output = element('div', undefined, 'scenario-result');
      output.setAttribute('aria-live', 'polite');
      output.append(element('span', current.outcome, `badge ${current.outcome}`),
        element('p', result.matched ? 'Initial policy outcome matched expectation.' : 'Unexpected policy outcome.', 'rule'),
        element('p', current.reason, 'help'), element('p', `Rule: ${current.rule} · Risk: ${current.risk}`, 'rule'));
      const details = element('details');
      details.append(element('summary', 'View recorded result'), element('pre', JSON.stringify(current, null, 2)));
      output.append(details);
      if (current.outcome === 'pending') output.append(element('p', 'Awaiting your decision in Activity & decisions below.', 'help'));
      card.append(output);
    }
    container.append(card);
  });
}
async function load(quiet = false) {
  if (!token) { if (!quiet) status('Enter a reviewer token to connect.'); return; }
  if (loading) return;
  loading = true;
  $('refresh').disabled = true;
  try {
    const [newActions, newProfile] = await Promise.all([api('/api/actions'), api('/api/agent')]);
    const actionsChanged = JSON.stringify(actions) !== JSON.stringify(newActions);
    const profileChanged = JSON.stringify(profile) !== JSON.stringify(newProfile);
    const firstLoad = !scenarioItems.length;
    actions = newActions; profile = newProfile;
    if (firstLoad) scenarioItems = await api('/api/demo/scenarios');
    if (actionsChanged || firstLoad) { render(); renderScenarios(); }
    if (profileChanged || !editorReady) renderProfile();
    $('disconnect').hidden = false;
    $('live-state').textContent = 'LIVE · UPDATES EVERY 3 SECONDS';
    if (!quiet) status('Connected. Run a scenario below; activity updates automatically.');
  } catch (error) { status(error.message); $('live-state').textContent = 'CONNECTION ERROR'; }
  finally { loading = false; $('refresh').disabled = false; }
}
$('connect').addEventListener('click', () => {
  token = $('token').value; $('token').value = ''; editorReady = false;
  load();
});
$('token').addEventListener('keydown', (event) => { if (event.key === 'Enter') $('connect').click(); });
$('disconnect').addEventListener('click', () => {
  token = ''; actions = []; profile = null; scenarioItems = []; editorReady = false;
  demoResults.clear(); render();
  $('scenarios').replaceChildren(element('div', 'Connect to run demo scenarios.', 'empty'));
  $('profile-summary').replaceChildren(element('p', 'Connect to load the agent profile.'));
  $('model-rows').replaceChildren(); $('agent-name').value = ''; $('agent-description').value = '';
  $('history-list').replaceChildren(); $('profile-status').textContent = '';
  $('profile-editor').hidden = true; $('profile-history').hidden = true;
  $('disconnect').hidden = true; $('live-state').textContent = 'CONNECT TO BEGIN';
  status('Disconnected. Token removed from memory.');
});
$('add-model').addEventListener('click', () => {
  if ($('model-rows').children.length >= 10) { $('profile-status').textContent = 'Maximum 10 model connections.'; return; }
  modelRow();
});
$('profile-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  $('save-profile').disabled = true;
  try {
    const model_connections = [...$('model-rows').children].map((row) => ({
      provider:row.querySelector('[data-field="provider"]').value.trim(),
      model:row.querySelector('[data-field="model"]').value.trim()
    }));
    profile = await api('/api/agent', {method:'PUT', body:JSON.stringify({
      revision:Number($('profile-form').dataset.revision), display_name:$('agent-name').value.trim(),
      description:$('agent-description').value, model_connections
    })});
    fillEditor(); renderProfile();
    $('profile-status').textContent = 'Profile saved. Model entries are unverified inventory.';
  } catch (error) { $('profile-status').textContent = error.message; }
  finally { $('save-profile').disabled = false; }
});
$('refresh').addEventListener('click', () => load());
$('filter').addEventListener('change', render);
setInterval(() => { if (token && !document.hidden) load(true); }, 3000);
