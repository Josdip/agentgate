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
  const response = await fetch(path, {...options, headers: {
    'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json'
  }});
  if (!response.ok) {
    if (response.status === 401) throw new Error('Access denied. Check your reviewer token.');
    if (response.status === 409) throw new Error('This action was already reviewed. Refresh the list.');
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
async function load() {
  if (!token) { status('Enter a reviewer token to connect.'); return; }
  $('refresh').disabled = true;
  try {
    actions = await api('/api/actions');
    render();
    $('disconnect').hidden = false;
    status('Connected. Activity loaded; refresh to fetch new actions.');
  } catch (error) { status(error.message); }
  finally { $('refresh').disabled = false; }
}
$('connect').addEventListener('click', () => { token = $('token').value; $('token').value = ''; load(); });
$('token').addEventListener('keydown', (event) => { if (event.key === 'Enter') $('connect').click(); });
$('disconnect').addEventListener('click', () => {
  token = ''; actions = []; render(); $('disconnect').hidden = true;
  status('Disconnected. Token removed from memory.');
});
$('refresh').addEventListener('click', load);
$('filter').addEventListener('change', render);
