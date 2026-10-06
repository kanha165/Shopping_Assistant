/* app.js - Init */

document.addEventListener('DOMContentLoaded', async () => {
  restoreSession();

  // Health check
  try {
    await Api.health();
  } catch {
    showToast('Cannot connect to backend. Make sure server is running on port 8000.', 'error');
  }

  // Keyboard shortcuts
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      ['product-modal','cart-modal','auth-modal'].forEach(id => {
        document.getElementById(id).classList.add('hidden');
      });
    }
    if (e.key === '/' && !e.ctrlKey && document.activeElement.tagName !== 'INPUT') {
      e.preventDefault();
      document.getElementById('query-input').focus();
    }
  });
});
