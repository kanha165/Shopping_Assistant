/* state.js — Global app state */

const State = {
  sessionId:        'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8),
  currentSearchId:  null,
  currentQuery:     '',

  allProducts:      [],
  shortlistedProducts: [],
  displayProducts:  [],
  productGroups:    [],
  topPickIndex:     null,

  view:   'grid',
  sortBy: 'rank',

  agentExplanation: '',
  platformsSearched: [],
  platformStatus:   {},
  timelineSteps:    [],

  pendingProduct: null,

  resetSearch() {
    this.allProducts        = [];
    this.shortlistedProducts = [];
    this.displayProducts    = [];
    this.productGroups      = [];
    this.topPickIndex       = null;
    this.currentSearchId    = null;
    this.agentExplanation   = '';
    this.platformsSearched  = [];
    this.platformStatus     = {};
    this.timelineSteps      = [];
    this.pendingProduct     = null;
  },
};
