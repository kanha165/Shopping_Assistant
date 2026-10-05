/**
 * api.js — All backend API calls.
 */
const API_BASE = (typeof window !== 'undefined' && window.location && window.location.origin && window.location.origin.startsWith('http'))
  ? `${window.location.origin}/api`
  : 'http://localhost:8000/api';

const Api = {

  _getHeaders() {
    const token = localStorage.getItem('token');
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  },

  async _req(method, path, body = null) {
    const opts = { method, headers: this._getHeaders(), mode: 'cors' };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${API_BASE}${path}`, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    return data;
  },

  // ── Health ──────────────────────────────────────────────────────────────
  health()        { return this._req('GET', '/health'); },
  getPlatforms()  { return this._req('GET', '/platforms'); },

  // ── Auth ────────────────────────────────────────────────────────────────
  register(email, username, password) {
    return this._req('POST', '/auth/register', { email, username, password });
  },
  login(email, password) {
    return this._req('POST', '/auth/login', { email, password });
  },
  getMe() { return this._req('GET', '/auth/me'); },

  // ── Search ──────────────────────────────────────────────────────────────
  search(query, sessionId) {
    return this._req('POST', '/search/', {
      query, session_id: sessionId || genSid(),
    });
  },
  streamSearch(query, sessionId) {
    const sid = sessionId || genSid();
    const url = `${API_BASE}/search/stream?query=${encodeURIComponent(query)}&session_id=${sid}`;
    return { eventSource: new EventSource(url), sessionId: sid };
  },
  getSearchHistory(limit = 20, sessionId = null) {
    const q = sessionId ? `&session_id=${encodeURIComponent(sessionId)}` : '';
    return this._req('GET', `/search/history?limit=${limit}${q}`);
  },
  getSearchResult(id) { return this._req('GET', `/search/${id}`); },

  // ── Products ────────────────────────────────────────────────────────────
  getProduct(id)    { return this._req('GET', `/products/${id}`); },
  addToCart(productId, searchId, sessionId) {
    return this._req('POST', '/products/cart/add', {
      product_id: productId, search_id: searchId, session_id: sessionId,
    });
  },
  getApprovalSummary(productId) {
    return this._req('GET', `/orders/approval-summary/${productId}`);
  },

  // ── Orders ──────────────────────────────────────────────────────────────
  createOrder(payload)  { return this._req('POST', '/orders', payload); },
  approveOrder(orderId, confirmed) {
    return this._req('POST', '/orders/approve', { order_id: orderId, confirmed });
  },
  updateOrder(orderId, payload) {
    return this._req('PATCH', `/orders/${orderId}`, payload);
  },
  listOrders(sessionId = null) {
    const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
    return this._req('GET', `/orders${q}`);
  },
  getOrder(id)          { return this._req('GET', `/orders/${id}`); },

  // ── Addresses ───────────────────────────────────────────────────────────
  listAddresses()       { return this._req('GET', '/addresses'); },
  createAddress(payload){ return this._req('POST', '/addresses', payload); },
  deleteAddress(id)     { return this._req('DELETE', `/addresses/${id}`); },

  // ── Agent logs ──────────────────────────────────────────────────────────
  getSessionLogs(sid)   { return this._req('GET', `/agent/logs/${sid}`); },
};

function genSid() {
  return 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
}
