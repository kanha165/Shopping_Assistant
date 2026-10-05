/**
 * state.js — Global app state.
 */

// ── Persistent guest session ID ──────────────────────────────────────────────
// Same session survives page reloads so guest history accumulates correctly.
// Only reset when the user explicitly clears browser storage.
function _getOrCreateGuestSessionId() {
  let sid = localStorage.getItem('guest_session_id');
  if (!sid) {
    sid = 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
    localStorage.setItem('guest_session_id', sid);
  }
  return sid;
}

const State = {
  currentUser:      null,
  sessionId:        _getOrCreateGuestSessionId(),   // persisted across reloads
  currentSearchId:  null,
  currentQuery:     '',

  allProducts:       [],
  shortlistedProducts: [],
  displayProducts:   [],
  productGroups:     [],
  topPickIndex:      null,

  view:   'grid',
  sortBy: 'rank',

  filters: { maxPrice: null, minRating: null, platform: '' },

  agentRunning:     false,
  agentExplanation: '',
  platformsSearched: [],
  platformStatus:   {},

  timelineSteps: [],

  pendingOrder: null,
  pendingProduct: null,

  resetSearch() {
    this.allProducts       = [];
    this.shortlistedProducts = [];
    this.displayProducts   = [];
    this.productGroups     = [];
    this.topPickIndex      = null;
    this.currentSearchId   = null;
    this.agentExplanation  = '';
    this.platformsSearched = [];
    this.platformStatus    = {};
    this.timelineSteps     = [];
    this.filters = { maxPrice: null, minRating: null, platform: '' };
    this.sortBy  = 'rank';
    this.pendingOrder   = null;
    this.pendingProduct = null;
    // NOTE: sessionId is NOT reset here — we keep the same session
    // so all searches in one browser session appear in history together
  },
};
