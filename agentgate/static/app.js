'use strict';
let token = '';
let actions = [];
const $ = (id) => document.getElementById(id);
const status = (message) => { $('status').textContent = message; };
let sessionVersion = 0;
let reloadRequested = false;
const loadedAt = new Map();
const decisionLabel = (outcome) => ({executed:'Executed (simulated)', denied:'Blocked', pending:'Awaiting review', rejected:'Rejected'}[outcome] || 'Unknown');
function syncRows(container, records, key, signature, build) {
  const existing = new Map([...container.children].filter(node => node.dataset.recordId).map(node => [node.dataset.recordId,node]));
  const retained = new Set();
  records.forEach((record,index) => {
    const id=key(record); retained.add(id);
    let node=existing.get(id);
    const value=signature(record);
    if (!node || node.dataset.signature!==value) {
      const replacement=build(record);
      replacement.dataset.recordId=id; replacement.dataset.signature=value;
      if (node) {
        const opened=[...node.querySelectorAll('details')].map(item=>item.open);
        const focused=node.contains(document.activeElement);
        const focusIndex=[...node.querySelectorAll('a,button,summary')].indexOf(document.activeElement);
        node.replaceWith(replacement);
        replacement.querySelectorAll('details').forEach((item,i)=>{item.open=opened[i] || false;});
        if (focused) {
          const target=replacement.querySelectorAll('a,button,summary')[focusIndex] || replacement.querySelector('button:not(:disabled)');
          if (target && !target.disabled) target.focus({preventScroll:true});
          else {replacement.tabIndex=-1;replacement.focus({preventScroll:true});}
        }
      }
      node=replacement;
    }
    if (container.children[index]!==node) container.insertBefore(node,container.children[index] || null);
  });
  [...container.children].forEach(node=>{if(!retained.has(node.dataset.recordId))node.remove();});
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
async function api(path, options = {}) {
  const requestSession=sessionVersion;
  let response;
  try {
    response=await fetch(path,{...options,headers:{'Authorization':`Bearer ${token}`,'Content-Type':'application/json'}});
  } catch {
    throw new Error('Could not reach AgentGate. Check that your local server is running, then retry.');
  }
  if(requestSession!==sessionVersion || !token) throw new Error('Your access changed. Connect again to continue.');
  if(!response.ok) {
    if(response.status===401) throw new Error('Access was not accepted. Check that you used the reviewer token, then reconnect.');
    if(response.status===409) throw new Error('This record changed. Refresh activity, or reopen the agent profile before saving.');
    if(response.status===422) throw new Error('Some values are not valid. Check field lengths and provider/model names; model entries must be unique.');
    throw new Error(`AgentGate could not complete this request (${response.status}). Please retry.`);
  }
  const result=await response.json();
  if(requestSession!==sessionVersion || !token) throw new Error('Your access changed. Connect again to continue.');
  return result;
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
  const card=element('article',undefined,'action');
  const head=element('div',undefined,'action-head');
  head.append(element('strong',actionTitle(action)),element('span',decisionLabel(action.outcome),`badge ${action.outcome}`));
  card.append(head,element('p',`${agentName(action.agent_id)} · ${new Date(action.created_at).toLocaleString()} · ${action.risk} action risk`,'rule'));
  if(compact) return card;
  card.append(element('p',action.reason,'reason'));
  const details=element('details');
  details.append(element('summary','View evidence'),element('pre',JSON.stringify(action,null,2)));
  card.append(details);
  if(action.outcome==='pending') {
    const context=element('section',undefined,'review-context');
    const target=action.arguments.ticket_id || action.arguments.vendor_id || 'See request evidence';
    context.append(element('h3','Review request'),element('p',`${agentName(action.agent_id)} · ${actionTitle(action)}`),
      element('p',`Target: ${target}. Current state: awaiting review.`),element('p',`Why review is needed: ${action.reason}`),
      element('p','Approving executes this simulated action once. No real payment, refund, or message will be sent.'));
    const buttons=element('div',undefined,'review');
    for(const approve of [true,false]) {
      const button=element('button',approve?'Approve simulated action':'Reject request',approve?'':'reject');
      button.addEventListener('click',async()=>{
        const reviewSession=sessionVersion;
        buttons.querySelectorAll('button').forEach(b=>{b.disabled=true;});
        try {
          const updated=await api(`/api/actions/${encodeURIComponent(action.id)}/review`,{method:'POST',body:JSON.stringify({approve})});
          for(const result of demoResults.values()) if(result.action.id===updated.id) result.action=updated;
          actions=actions.map(item=>item.id===updated.id?updated:item);render();
          await load(true);if(reviewSession!==sessionVersion)return;status(approve?'Request approved. The simulated result is recorded.':'Request rejected. No action was executed.');
          if(!document.body.contains(button)){const count=$('activity-count');count.tabIndex=-1;count.focus({preventScroll:true});}
        } catch(error) {if(reviewSession===sessionVersion)status(error.message);buttons.querySelectorAll('button').forEach(b=>{b.disabled=false;});}
      });
      buttons.append(button);
    }
    context.append(buttons);card.append(context);
  }
  return card;
}
function render() {
  if(!actions.length) {
    $('actions').replaceChildren(element('div','No actions match these filters. Try another agent or decision, or clear your search.','empty'));
    return;
  }
  syncRows($('actions'),actions,a=>a.id,a=>JSON.stringify([a,agentName(a.agent_id)]),a=>actionCard(a));
}
function renderOverview() {
  for(const key of ['total','denied','pending','executed']) $(key).textContent=summary[key];
  $('known-agents').textContent=`${summary.agents} registered demo agents · View inventory →`;
  $('attention-title').textContent=summary.pending?`${summary.pending} ${summary.pending===1?'request needs':'requests need'} your review`:'No requests waiting for review';
  $('attention-description').textContent=summary.pending?'Review the agent, target, and policy reason before approving or rejecting a request.':'New sensitive requests will appear here. This does not mean that agent exposure has been assessed.';
  document.querySelector('.attention-panel').classList.toggle('has-pending',summary.pending>0);
  $('recent-actions').className='';
  if(!summary.recent.length) $('recent-actions').replaceChildren(element('div','No activity recorded yet. Try an interactive case below to see a policy decision.','empty'));
  else syncRows($('recent-actions'),summary.recent,a=>a.id,a=>JSON.stringify([a,agentName(a.agent_id)]),a=>actionCard(a,true));
}
function renderDirectory() {
  if(!token || !loadedAt.has('directory')) {
    $('agent-count').textContent='Connect to load your agent inventory.';
    $('agent-directory').replaceChildren();return;
  }
  const query=$('directory-search').value.toLowerCase();
  const matches=agents.filter(a=>`${a.display_name} ${a.owner} ${a.location}`.toLowerCase().includes(query));
  $('agent-count').textContent=matches.length?`${matches.length} of ${agents.length} registered demo agents`:'No agents match this search. Try a name, team, or location.';
  syncRows($('agent-directory'),matches,a=>a.agent_id,a=>JSON.stringify([a.display_name,a.description,a.owner,a.location,a.activity.last_seen]),agent=>{
    const row=element('tr');
    const name=element('td');name.append(element('strong',agent.display_name),element('p',agent.description));row.append(name);
    for(const [label,value] of [['Owner',agent.owner],['Location',`${agent.location} (demo)`],['Observation',agent.activity.last_seen?'Demo activity recorded':'No activity yet'],['Last activity',agent.activity.last_seen?new Date(agent.activity.last_seen).toLocaleString():'Not observed']]) {
      const cell=element('td',value);cell.dataset.label=label;row.append(cell);
    }
    const action=element('td');const link=element('a','View profile →');link.href=`/agents/${agent.agent_id}`;link.dataset.nav='';link.setAttribute('aria-label',`View profile for ${agent.display_name}`);action.append(link);row.append(action);
    return row;
  });
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
  container.append(facts, element('h3', 'Language model connections'));
  if (!profile.model_connections.length) container.append(element('p', 'No models registered. These agents use scripted requests; no live language model is connected.', 'help'));
  for (const connection of profile.model_connections) {
    container.append(element('p', `${connection.provider} / ${connection.model} · registered, unverified`, 'model-entry'));
  }
  container.append(element('h3', 'Enforced tool access & permissions'));
  const tools = element('div', undefined, 'tool-grid');
  for (const tool of profile.tools) {
    const card = element('article', undefined, 'tool-card');
    card.append(element('strong', tool.permission), element('p', `Tool: ${tool.tool}`, 'rule'),
      element('p', `Scope: ${tool.scope.join(', ')}`, 'help'), element('p', tool.approval, 'rule'));
    tools.append(card);
  }
  container.append(tools, element('p', 'All other tools are blocked. This agent cannot approve its own requests. Access is enforced by the gateway.', 'help'));
  syncRows($('history-list'),profile.history,entry=>String(entry.revision),entry=>JSON.stringify(entry),entry=>{
    const item=element('details');
    item.append(element('summary',`Revision ${entry.revision} · ${new Date(entry.changed_at).toLocaleString()} · ${entry.changed_by}`),element('pre',JSON.stringify(entry.metadata,null,2)));
    return item;
  });
  $('profile-editor').hidden = false;
  $('profile-history').hidden = false;
  if (!editorReady) fillEditor();
}
function renderScenarios() {
  const container = $('scenarios');
  const items=scenarioItems.filter(item=>item.agent_id===$('demo-agent').value);
  syncRows(container,items,item=>item.id,item=>JSON.stringify([item,demoResults.get(item.id),runningScenarios.has(item.id)]),item=>{
    const index=items.indexOf(item);
    const card = element('article', undefined, 'scenario');
    card.append(element('div', `Case ${index + 1} · Expected: ${decisionLabel(item.expected)}`, 'eyebrow'),
      element('h3', item.name), element('p', item.description, 'help'));
    const request = element('details');
    request.append(element('summary', 'Preview tool request'), element('pre', JSON.stringify({tool:item.tool, arguments:item.arguments}, null, 2)));
    card.append(request);
    const result = demoResults.get(item.id);
    const busy = runningScenarios.has(item.id);
    const run = element('button', busy ? 'Evaluating…' : result ? 'Run again' : 'Run scenario');
    run.disabled = busy || !token;
    run.addEventListener('click', async () => {
      const runSession=sessionVersion;
      runningScenarios.add(item.id); renderScenarios();
      status(`Submitting ${item.name} through the policy gateway…`);
      try {
        const outcome = await api(`/api/demo/scenarios/${encodeURIComponent(item.id)}/run`, {method:'POST'});
        demoResults.set(item.id, outcome);
        await load(true);
        if(runSession===sessionVersion)status(`${item.name}: ${decisionLabel(outcome.action.outcome)}. ${outcome.action.reason}`);
      } catch (error) { if(runSession===sessionVersion)status(error.message); }
      finally { runningScenarios.delete(item.id); if(runSession===sessionVersion)renderScenarios(); }
    });
    card.append(run);
    if (busy) card.append(element('p', 'Request submitted → policy evaluation → audit record', 'help'));
    if (result) {
      const current = actions.find((action) => action.id === result.action.id) || result.action;
      const output = element('div', undefined, 'scenario-result');
      output.setAttribute('aria-live', 'polite');
      output.append(element('span', decisionLabel(current.outcome), `badge ${current.outcome}`),
        element('p', result.matched ? 'The initial decision matched this case’s expected result.' : 'This case returned an unexpected decision.', 'rule'),
        element('p', current.reason, 'help'), element('p', `Rule: ${current.rule} · Risk: ${current.risk}`, 'rule'));
      const details = element('details');
      details.append(element('summary', 'View recorded result'), element('pre', JSON.stringify(current, null, 2)));
      output.append(details);
      if (current.outcome === 'pending') { const reviewLink = element('a','Review request →'); reviewLink.href=`/activity?outcome=pending&agent_id=${item.agent_id}`; reviewLink.dataset.nav=''; output.append(reviewLink); }
      card.append(output);
    }
    return card;
  });
}
function activityQuery() {
  const query = new URLSearchParams({limit:'20'});
  for (const [id,key] of [['activity-agent','agent_id'],['filter','outcome'],['risk-filter','risk'],['activity-search','search']]) if ($(id).value) query.set(key,$(id).value);
  if (before) query.set('before',before);
  return query;
}
function describeUpdate() {
  const time=loadedAt.get(location.pathname);
  $('last-updated').textContent=time?`Last updated ${time.toLocaleTimeString()}`:'No data loaded for this page';
}
function showLoadError(error) {
  const cached=loadedAt.has(location.pathname);
  document.querySelector('.connection').dataset.state=cached?'stale':'error';
  status(`${error.message}${cached?' Previously loaded data is still shown and may be out of date.':' Data for this page is unavailable.'}`);
  $('live-state').textContent=cached?'Updates paused · data may be stale':'Unavailable';
  describeUpdate();
  if(cached) $('last-updated').textContent+=' · may be out of date';
  if(!cached) {
    if(location.pathname==='/') {
      for(const key of ['total','denied','pending','executed'])$(key).textContent='—';
      $('attention-title').textContent='Review status unavailable';
      $('attention-description').textContent='Reconnect or retry once the local server is available.';
      $('recent-actions').replaceChildren(element('div','Activity could not be loaded. Check the connection and retry.','empty'));
    } else if(location.pathname==='/activity') $('activity-count').textContent='Activity unavailable. Retry with Refresh activity.';
    else $('agent-count').textContent='Inventory unavailable. Check the connection and retry.';
  }
}
async function load(quiet=false) {
  if(!token) {if(!quiet)status('Not connected. Enter your reviewer token to load the workspace.');return;}
  if(loading) {reloadRequested=true;return;}
  loading=true;
  const version=routeVersion, requestSession=sessionVersion, pagePath=location.pathname;
  const isCurrent=()=>version===routeVersion && requestSession===sessionVersion && Boolean(token);
  const priorState=document.querySelector('.connection').dataset.state;
  if(!quiet) {status('Loading your workspace…');document.querySelector('.connection').dataset.state='loading';}
  if(!loadedAt.has(pagePath)) {
    $('last-updated').textContent='Loading…';
    if(pagePath==='/activity')$('activity-count').textContent='Loading activity…';
    else if(pagePath.startsWith('/agents'))$('agent-count').textContent='Loading inventory…';
  }
  try {
    const directory=await api('/api/agents');
    if(!isCurrent())return;
    const directoryChanged=JSON.stringify(agents)!==JSON.stringify(directory);
    const initialDirectory=!loadedAt.has('directory');
    agents=directory;loadedAt.set('directory',new Date());
    if(directoryChanged || initialDirectory) {
      renderDirectory();
      const selected=$('activity-agent').value;
      $('activity-agent').replaceChildren(new Option('All agents',''));
      agents.forEach(a=>$('activity-agent').append(new Option(a.display_name,a.agent_id)));
      $('activity-agent').value=requestedAgentFilter??selected;requestedAgentFilter=null;
    }
    if(pagePath==='/agents')renderDirectory();
    if(pagePath==='/') {
      const next=await api('/api/overview');if(!isCurrent())return;
      if(JSON.stringify(summary)!==JSON.stringify(next)){summary=next;renderOverview();}
      if(!scenarioItems.length){scenarioItems=await api('/api/demo/scenarios');if(!isCurrent())return;renderScenarios();}
    } else if(pagePath==='/activity') {
      const query=activityQuery().toString();
      const page=await api(`/api/activity?${query}`);if(!isCurrent())return;
      if(query!==activityQuery().toString()){reloadRequested=true;return;}
      if(JSON.stringify(actions)!==JSON.stringify(page.items)||!actions.length){actions=page.items;render();}
      nextCursor=page.next_cursor;
      $('activity-count').textContent=`${page.total} matching ${page.total===1?'action':'actions'} · Showing ${page.items.length} · ${before?'Older results; automatic updates paused':'Newest first'}`;
      $('older').disabled=!nextCursor;$('newer').disabled=!cursorStack.length;
      $('page-label').textContent=`Page ${cursorStack.length+1} · Up to 20 actions`;
    } else if(activeProfileId) {
      const next=agents.find(a=>a.agent_id===activeProfileId);
      if(!next){$('profile-panel').hidden=true;throw new Error('This agent was not found. Return to Agents to choose a registered profile.');}
      if(JSON.stringify(profile)!==JSON.stringify(next)||!editorReady){profile=next;renderProfile();}
    }
    loadedAt.set(pagePath,new Date());describeUpdate();
    document.querySelector('.connection').dataset.state='connected';
    $('disconnect').hidden=false;$('connect').textContent='Reconnect';
    $('live-state').textContent='Updates every 3 seconds';
    if(!quiet || priorState==='stale' || priorState==='error') status('Connected as reviewer. Your token stays only in this tab.');
  } catch(error) {if(isCurrent())showLoadError(error);}
  finally {
    loading=false;
    if(reloadRequested){reloadRequested=false;load(true);}
  }
}
function route() {
  routeVersion++;
  const path=location.pathname;
  $('home-page').hidden=path!=='/';$('agents-page').hidden=!path.startsWith('/agents');$('activity-page').hidden=path!=='/activity';
  activeProfileId=path.startsWith('/agents/') ? decodeURIComponent(path.split('/')[2]) : null;
  $('profile-panel').hidden=true;
  $('directory-panel').hidden=Boolean(activeProfileId);
  $('actions').replaceChildren();
  if(activeProfileId)$('profile-summary').replaceChildren(element('p','Loading profile…','help'));
  profile=null;editorReady=false;before=null;cursorStack=[];actions=[];
  $('profile-status').textContent='';
  const query=new URLSearchParams(location.search);
  requestedAgentFilter=query.get('agent_id');
  for (const [id,key] of [['activity-agent','agent_id'],['filter','outcome'],['risk-filter','risk'],['activity-search','search']]) $(id).value=query.get(key)||'';
  document.querySelectorAll('nav a').forEach(link=>{const current=link.pathname==='/'?path==='/':path.startsWith(link.pathname);link.classList.toggle('active',current);if(current)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');});
  document.title=`AgentGate · ${path.startsWith('/agents')?'Agents':path==='/activity'?'Activity & decisions':'Overview'}`;
  if([...$('activity-agent').options].some(option=>option.value===requestedAgentFilter))requestedAgentFilter=null;
  describeUpdate();
  if (path === '/' && scenarioItems.length) renderScenarios();
  load();
}
document.addEventListener('click',event=>{
  const link=event.target.closest('a[data-nav]');
  if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.button!==0) return;
  event.preventDefault();history.pushState({},'',link.href);route();window.scrollTo(0,0);
  const heading=document.querySelector('#home-page:not([hidden]) h1, #agents-page:not([hidden]) h1, #activity-page:not([hidden]) h1');
  if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true});}
});
window.addEventListener('popstate',route);
$('connect').addEventListener('click',()=>{
  const entered=$('token').value.trim();
  if(!entered){status('Enter your reviewer token first. Find it in your local .env file.');$('token').focus();return;}
  sessionVersion++;token=entered;$('token').value='';editorReady=false;load();
});
$('token').addEventListener('keydown',event=>{if(event.key==='Enter')$('connect').click();});
$('disconnect').addEventListener('click',()=>{
  sessionVersion++;token='';actions=[];agents=[];profile=null;summary=null;scenarioItems=[];demoResults.clear();runningScenarios.clear();editorReady=false;loadedAt.clear();
  $('disconnect').hidden=true;
  $('scenarios').replaceChildren(element('div','Connect to run demo cases.','empty'));
  $('agent-directory').replaceChildren();$('actions').replaceChildren();$('recent-actions').replaceChildren();
  $('profile-panel').hidden=true;$('profile-summary').replaceChildren();$('model-rows').replaceChildren();$('history-list').replaceChildren();
  $('agent-name').value='';$('agent-description').value='';$('profile-status').textContent='';
  for(const id of ['total','denied','pending','executed'])$(id).textContent='—';
  $('activity-count').textContent='Connect to view activity.';$('agent-count').textContent='';
  $('live-state').textContent='Not connected';$('connect').textContent='Connect';
  document.querySelector('.connection').dataset.state='disconnected';
  $('attention-title').textContent='Connect to see requests awaiting review';
  $('attention-description').textContent='Sensitive actions pause until a reviewer makes a decision.';
  document.querySelector('.attention-panel').classList.remove('has-pending');
  $('known-agents').textContent='View registered agents →';$('last-updated').textContent='No data loaded yet';
  $('newer').disabled=true;$('older').disabled=true;
  status('Disconnected. Your token and loaded workspace data were cleared.');
});
$('add-model').addEventListener('click',()=>{if($('model-rows').children.length<10){modelRow();$('model-rows').lastElementChild.querySelector('input').focus();}else $('profile-status').textContent='You can register up to 10 models. Remove an entry before adding another.';});
$('profile-form').addEventListener('submit',async event=>{
  event.preventDefault();$('save-profile').disabled=true;
  try {
    const model_connections=[...$('model-rows').children].map(row=>({provider:row.querySelector('[data-field="provider"]').value.trim(),model:row.querySelector('[data-field="model"]').value.trim()}));
    const savingAgent=activeProfileId, savingSession=sessionVersion;
    const updated=await api(`/api/agents/${savingAgent}`,{method:'PUT',body:JSON.stringify({revision:Number($('profile-form').dataset.revision),display_name:$('agent-name').value.trim(),description:$('agent-description').value,model_connections})});
    if(activeProfileId!==savingAgent || sessionVersion!==savingSession)return;
    profile=updated;fillEditor();renderProfile();$('profile-status').textContent='Changes saved to a new revision. Model entries are still unverified.';
    await load(true);
  } catch(error){$('profile-status').textContent=error.message;}
  finally{$('save-profile').disabled=false;}
});
$('demo-agent').addEventListener('change',renderScenarios);
$('directory-search').addEventListener('input',renderDirectory);
$('activity-filters').addEventListener('submit',event=>{event.preventDefault();before=null;cursorStack=[];requestedAgentFilter=null;actions=[];load();});
$('older').addEventListener('click',()=>{if(!nextCursor||loading)return;cursorStack.push(before);before=nextCursor;load();});
$('newer').addEventListener('click',()=>{if(!cursorStack.length||loading)return;before=cursorStack.pop();load();});
$('refresh').addEventListener('click',()=>load());
setInterval(()=>{if(token&&!document.hidden&&!(location.pathname==='/activity'&&before))load(true);},3000);
route();
