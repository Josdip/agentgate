'use strict';

const result = document.getElementById('result');
document.getElementById('report').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.submitter || event.currentTarget.querySelector('button');
  button.disabled = true;
  try {
    const gateway = new URL(document.getElementById('gateway').value);
    if (gateway.protocol !== 'http:' || gateway.hostname !== '127.0.0.1' ||
        gateway.username || gateway.password || gateway.pathname !== '/' || gateway.search || gateway.hash) {
      throw new Error('Enter the local AgentGate address, including its HTTP port.');
    }
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    const page = tab?.url && new URL(tab.url);
    if (!page || page.protocol !== 'https:' || page.host !== 'chatgpt.com') {
      throw new Error('Open a ChatGPT tab and try again.');
    }
    const code = document.getElementById('code');
    const mode = button.value || 'observe';
    const route = {observe: 'observation', enroll: 'enrollment', paired: 'report'}[mode];
    const storageKey = 'agentgate:' + gateway.origin;
    const credential = mode === 'paired'
      ? (await chrome.storage.local.get(storageKey))[storageKey] : code.value.trim();
    if (!credential) throw new Error('Enter a code or enroll this browser first.');
    const response = await fetch(gateway.origin + '/api/connectors/chrome/' + route, {
      method: 'POST',
      headers: {Authorization: 'Bearer ' + credential, 'Content-Type': 'application/json'},
      body: JSON.stringify({service: 'chatgpt'}),
      redirect: 'error',
    });
    if (!response.ok) throw new Error('AgentGate declined the report. Generate a new discovery code.');
    if (mode === 'enroll') {
      const {credential: issued} = await response.json();
      await chrome.storage.local.set({[storageKey]: issued});
    }
    code.value = '';
    result.textContent = mode === 'enroll' ? 'Chrome enrolled for inventory reporting.' : 'ChatGPT was reported to AgentGate.';
  } catch (error) {
    result.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
