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
let agents = [];
let before = null;
let cursorStack = [];
let nextCursor = null;
let activeProfileId = null;
let summary = null;
let routeVersion = 0;
let requestedAgentFilter = null;
const agentName = (id) => agents.find(a => a.agent_id === id)?.display_name || id;
const money = (cents) => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(cents / 100);
function actionTitle(action) {
  const args = action.arguments;
  const names = {'documents.read':`Requested document “${args.document_id}”`, 'refunds.create':`Requested a ${money(args.amount_cents || 0)} customer refund`, 'messages.send':`Requested a message to ${args.destination}`, 'crm.read':`Requested sales lead ${args.lead_id}`, 'invoices.read':`Requested invoice ${args.invoice_id}`, 'payments.create':`Requested a ${money(args.amount_cents || 0)} supplier payment`};
  return names[action.tool] || `Attempted an unregistered tool (${action.tool})`;
}
function actionCard(action, compact = false) {
  const card = element('article', undefined, 'action');
  const head = element('div', undefined, 'action-head');
  head.append(element('strong', actionTitle(action)), element('span', action.outcome === 'denied' ? 'Blocked' : action.outcome, `badge ${action.outcome}`));
  card.append(head, element('p', `${agentName(action.agent_id)} · ${new Date(action.created_at).toLocaleString()} · ${action.risk} action risk`, 'rule'));
  if (compact) return card;
  card.append(element('p', action.reason, 'reason'));
  const details = element('details');
  details.append(element('summary','Inspect technical evidence'),element('pre',JSON.stringify(action,null,2)));
  card.append(details);
  if (action.outcome === 'pending') {
    const buttons = element('div',undefined,'review');
    for (const approve of [true,false]) {
      const button = element('button',approve ? 'Approve simulated action' : 'Reject',approve ? '' : 'reject');
      button.addEventListener('click',async () => {
        buttons.querySelectorAll('button').forEach(b=>{b.disabled=true;});
        try {
          const updated = await api(`/api/actions/${encodeURIComponent(action.id)}/review`,{method:'POST',body:JSON.stringify({approve})});
          for (const result of demoResults.values()) if (result.action.id === updated.id) result.action = updated;
          await load(); status(approve ? 'Approved. Simulated execution recorded.' : 'Action rejected.');
        } catch (error) { status(error.message); buttons.querySelectorAll('button').forEach(b=>{b.disabled=false;}); }
      });
      buttons.append(button);
    }
    card.append(buttons);
  }
  return card;
}
function render() {
  const container = $('actions'); container.replaceChildren();
  if (!actions.length) container.append(element('div','No actions match these filters.','empty'));
  actions.forEach(action=>container.append(actionCard(action)));
}
function renderOverview() {
  for (const key of ['total','denied','pending','executed']) $(key).textContent = summary[key];
  $('known-agents').textContent = `${summary.agents} registered demo agents · View inventory →`;
  $('recent-actions').className = '';
  $('recent-actions').replaceChildren();
  if (!summary.recent.length) $('recent-actions').append(element('div','Run a case to see recent activity.','empty'));
  summary.recent.forEach(action=>$('recent-actions').append(actionCard(action,true)));
}
function renderDirectory() {
  const query = $('directory-search').value.toLowerCase();
  const matches = agents.filter(a=>`${a.display_name} ${a.owner} ${a.location}`.toLowerCase().includes(query));
  $('agent-count').textContent = `${matches.length} of ${agents.length} registered demo agents`;
  $('agent-directory').replaceChildren();
  for (const agent of matches) {
    const card = element('article',undefined,'agent-tile');
    card.append(element('div',`${agent.owner} · ${agent.location} (simulated)`,'eyebrow'),element('h2',agent.display_name),element('p',agent.description,'help'),element('p',`${agent.tools.length} tools · ${agent.activity.total_actions} actions · ${agent.activity.pending} awaiting approval`,'rule'));
    const link=element('a','View agent profile →');link.href=`/agents/${agent.agent_id}`;link.dataset.nav='';card.append(link);
    $('agent-directory').append(card);
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
  $('profile-panel').hidden = false;
  const container = $('profile-summary');
  container.className = '';
  container.replaceChildren();
  container.append(element('h3', profile.display_name), element('p', profile.description, 'help'),
    element('p', `${profile.agent_id} · ${profile.owner} · ${profile.location} (simulated) · revision ${profile.revision}`, 'rule'));
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
  scenarioItems.filter(item => item.agent_id === $('demo-agent').value).forEach((item, index) => {
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
      if (current.outcome === 'pending') { const reviewLink = element('a','Review this request →'); reviewLink.href=`/activity?outcome=pending&agent_id=${item.agent_id}`; reviewLink.dataset.nav=''; output.append(reviewLink); }
      card.append(output);
    }
    container.append(card);
  });
}
function activityQuery() {
  const query = new URLSearchParams({limit:'20'});
  for (const [id,key] of [['activity-agent','agent_id'],['filter','outcome'],['risk-filter','risk'],['activity-search','search']]) if ($(id).value) query.set(key,$(id).value);
  if (before) query.set('before',before);
  return query;
}
async function load(quiet = false) {
  if (!token) { if (!quiet) status('Connect with your reviewer token to load data.'); return; }
  if (loading) return;
  loading = true;
  const version = routeVersion;
  try {
    const directory = await api('/api/agents');
    if (version !== routeVersion) return;
    const directoryChanged = JSON.stringify(agents) !== JSON.stringify(directory);
    agents = directory;
    if (directoryChanged) {
      renderDirectory();
      const selected = $('activity-agent').value;
      $('activity-agent').replaceChildren(new Option('All agents',''));
      agents.forEach(a=>$('activity-agent').append(new Option(a.display_name,a.agent_id)));
      $('activity-agent').value=requestedAgentFilter ?? selected; requestedAgentFilter=null;
    }
    if (location.pathname === '/') {
      const next = await api('/api/overview');
      if (version !== routeVersion) return;
      if (JSON.stringify(summary)!==JSON.stringify(next)) {summary=next;renderOverview();}
      if (!scenarioItems.length) {scenarioItems=await api('/api/demo/scenarios');renderScenarios();}
    } else if (location.pathname === '/activity') {
      const page = await api(`/api/activity?${activityQuery()}`);
      if (version !== routeVersion) return;
      if (JSON.stringify(actions)!==JSON.stringify(page.items)) {actions=page.items;render();}
      else if (!actions.length) render();
      nextCursor=page.next_cursor;
      $('activity-count').textContent=`${page.total} matching actions · showing ${page.items.length} · ${before ? 'older results (auto-refresh paused)' : 'newest first'}`;
      $('older').disabled=!nextCursor;$('newer').disabled=!cursorStack.length;
      $('page-label').textContent=`20 per page · page ${cursorStack.length+1}`;
    } else if (activeProfileId) {
      const next=agents.find(a=>a.agent_id===activeProfileId);
      if (!next) {status('Agent not found.');$('profile-panel').hidden=true;return;}
      if (JSON.stringify(profile)!==JSON.stringify(next) || !editorReady) {profile=next;renderProfile();}
    }
    $('disconnect').hidden=false;
    $('live-state').textContent='LIVE · UPDATES EVERY 3 SECONDS';
    if (!quiet) status('Connected. Activity updates automatically; your token stays in memory.');
  } catch (error) {status(error.message);}
  finally {loading=false;}
}
function route() {
  routeVersion++;
  const path=location.pathname;
  $('home-page').hidden=path!=='/';$('agents-page').hidden=!path.startsWith('/agents');$('activity-page').hidden=path!=='/activity';
  activeProfileId=path.startsWith('/agents/') ? decodeURIComponent(path.split('/')[2]) : null;
  $('profile-panel').hidden=!activeProfileId;
  profile=null;editorReady=false;before=null;cursorStack=[];actions=[];
  const query=new URLSearchParams(location.search);
  requestedAgentFilter=query.get('agent_id');
  for (const [id,key] of [['activity-agent','agent_id'],['filter','outcome'],['risk-filter','risk'],['activity-search','search']]) $(id).value=query.get(key)||'';
  document.querySelectorAll('nav a').forEach(link=>{link.classList.toggle('active',link.pathname==='/' ? path==='/' : path.startsWith(link.pathname));});
  if (path === '/' && scenarioItems.length) renderScenarios();
  load();
}
document.addEventListener('click',event=>{
  const link=event.target.closest('a[data-nav]');
  if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.button!==0) return;
  event.preventDefault();history.pushState({},'',link.href);route();window.scrollTo(0,0);
});
window.addEventListener('popstate',route);
$('connect').addEventListener('click',()=>{token=$('token').value;$('token').value='';editorReady=false;load();});
$('token').addEventListener('keydown',event=>{if(event.key==='Enter')$('connect').click();});
$('disconnect').addEventListener('click',()=>{
  token='';actions=[];agents=[];profile=null;summary=null;scenarioItems=[];demoResults.clear();editorReady=false;
  $('disconnect').hidden=true;
  $('scenarios').replaceChildren(element('div','Connect to run demo cases.','empty'));
  $('agent-directory').replaceChildren();$('actions').replaceChildren();$('recent-actions').replaceChildren();
  $('profile-panel').hidden=true;$('profile-summary').replaceChildren();$('model-rows').replaceChildren();$('history-list').replaceChildren();
  $('agent-name').value='';$('agent-description').value='';$('profile-status').textContent='';
  for(const id of ['total','denied','pending','executed'])$(id).textContent='—';
  $('activity-count').textContent='Connect to view activity.';$('agent-count').textContent='';
  $('live-state').textContent='CONNECT TO BEGIN';status('Disconnected. Token removed from memory.');
});
$('add-model').addEventListener('click',()=>{if($('model-rows').children.length<10)modelRow();});
$('profile-form').addEventListener('submit',async event=>{
  event.preventDefault();$('save-profile').disabled=true;
  try {
    const model_connections=[...$('model-rows').children].map(row=>({provider:row.querySelector('[data-field="provider"]').value.trim(),model:row.querySelector('[data-field="model"]').value.trim()}));
    profile=await api(`/api/agents/${activeProfileId}`,{method:'PUT',body:JSON.stringify({revision:Number($('profile-form').dataset.revision),display_name:$('agent-name').value.trim(),description:$('agent-description').value,model_connections})});
    fillEditor();renderProfile();$('profile-status').textContent='Saved a new profile revision. Model inventory remains unverified.';
    await load(true);
  } catch(error){$('profile-status').textContent=error.message;}
  finally{$('save-profile').disabled=false;}
});
$('demo-agent').addEventListener('change',renderScenarios);
$('directory-search').addEventListener('input',renderDirectory);
$('activity-filters').addEventListener('submit',event=>{event.preventDefault();before=null;cursorStack=[];actions=[];load();});
$('older').addEventListener('click',()=>{cursorStack.push(before);before=nextCursor;load();});
$('newer').addEventListener('click',()=>{before=cursorStack.pop();load();});
$('refresh').addEventListener('click',()=>load());
setInterval(()=>{if(token&&!document.hidden&&!(location.pathname==='/activity'&&before))load(true);},3000);
route();
