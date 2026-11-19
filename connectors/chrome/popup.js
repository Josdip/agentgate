'use strict';

const result = document.getElementById('result');
document.getElementById('report').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button');
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
    const response = await fetch(gateway.origin + '/api/connectors/chrome/observation', {
      method: 'POST',
      headers: {Authorization: 'Bearer ' + code.value.trim(), 'Content-Type': 'application/json'},
      body: JSON.stringify({service: 'chatgpt'}),
      redirect: 'error',
    });
    if (!response.ok) throw new Error('AgentGate declined the report. Generate a new discovery code.');
    code.value = '';
    result.textContent = 'ChatGPT was added to the AgentGate inventory.';
  } catch (error) {
    result.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
