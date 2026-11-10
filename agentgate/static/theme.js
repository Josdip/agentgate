// Run before styles load so a saved dark preference does not flash the light theme.
(() => {
  const key = 'agentgate.theme';
  let theme = 'light';
  try {
    const saved = localStorage.getItem(key);
    if (saved === 'light' || saved === 'dark') theme = saved;
  } catch {
    // Theme switching still works when browser storage is unavailable.
  }
  document.documentElement.dataset.theme = theme;
  document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('theme-toggle');
    if (!toggle) return;
    toggle.setAttribute('aria-pressed', String(theme === 'dark'));
    toggle.addEventListener('click', () => {
      theme = theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = theme;
      toggle.setAttribute('aria-pressed', String(theme === 'dark'));
      try {
        localStorage.setItem(key, theme);
      } catch {
        // Keep the choice for this page even if it cannot be saved across visits.
      }
    });
  });
})();
