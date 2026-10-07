/* api.js — Backend API calls */

const API_BASE = (window.location.origin.startsWith('http'))
  ? `${window.location.origin}/api`
  : 'http://localhost:8000/api';

const Api = {

  async _req(method, path, body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${API_BASE}${path}`, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    return data;
  },

  // ── Health ──────────────────────────────────────────────────────────────
  health()       { return this._req('GET', '/health'); },
  getPlatforms() { return this._req('GET', '/platforms'); },

  // ── Search ──────────────────────────────────────────────────────────────
  search(query, sessionId) {
    return this._req('POST', '/search/', { query, session_id: sessionId });
  },
  streamSearch(query, sessionId) {
    const sid = sessionId || ('sess_' + Date.now());
    const url = `${API_BASE}/search/stream?query=${encodeURIComponent(query)}&session_id=${sid}`;
    return { eventSource: new EventSource(url), sessionId: sid };
  },
};
