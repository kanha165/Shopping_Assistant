/* search.js — Search logic + SSE streaming */

let _es = null;

async function startSearch() {
  const q = document.getElementById('query-input').value.trim();
  if (!q) { toast('Please enter a search query', 'err'); return; }

  State.resetSearch();
  State.currentQuery = q;
  // Keep the same persistent sessionId — do NOT call genSid() here.
  // This ensures all searches in one browser session share the same session_id
  // and all appear together in guest history.

  // UI reset
  document.getElementById('btn-search').disabled = true;
  document.getElementById('btn-search').textContent = 'Searching…';
  document.getElementById('rec-banner').classList.add('hidden');
  document.getElementById('results').classList.add('hidden');
  document.getElementById('groups-section').innerHTML = '';
  document.getElementById('history-panel').classList.add('hidden');
  document.getElementById('orders-panel').classList.add('hidden');

  initTimeline();

  if (_es) { _es.close(); _es = null; }

  const { eventSource, sessionId } = Api.streamSearch(q, State.sessionId);
  // sessionId returned from streamSearch should equal State.sessionId — keep it consistent
  State.sessionId = sessionId;
  _es = eventSource;

  eventSource.onmessage = e => {
    try { handleEvent(JSON.parse(e.data)); }
    catch {}
  };
  eventSource.onerror = () => {
    eventSource.close(); _es = null;
    fallback(q);
  };
}

async function fallback(q) {
  addTimelineEvent('status', 'Searching (may take a moment)…');
  try {
    const r = await Api.search(q, State.sessionId);
    onResult(r);
  } catch(e) { onError(e.message); }
}

function handleEvent(ev) {
  const { type, message, platform } = ev;
  switch (type) {
    case 'start':
      addTimelineEvent('status', message);
      break;
    case 'status':
    case 'thinking':
      addTimelineEvent(type, message);
      if (platform) setPlatformPill(platform, 'searching');
      break;
    case 'platform_ok':
      if (platform) {
        State.platformStatus[platform] = 'ok';
        setPlatformPill(platform, 'ok');
      }
      break;
    case 'platform_fail':
      if (platform) {
        State.platformStatus[platform] = 'unavailable';
        setPlatformPill(platform, 'fail');
      }
      break;
    case 'done':
      addTimelineEvent('done', message);
      break;
    case 'error':
      addTimelineEvent('error', message);
      break;
    case 'result':
      if (ev.data) onResult(ev.data);
      break;
  }
}

function onResult(result) {
  if (_es) { _es.close(); _es = null; }

  State.allProducts        = result.all_products || result.shortlisted_products || [];
  State.shortlistedProducts= result.shortlisted_products || [];
  State.agentExplanation   = result.agent_explanation || '';
  State.platformsSearched  = result.platforms_searched || [];
  State.platformStatus     = result.platform_status || {};
  State.currentSearchId    = result.search_id;
  State.topPickIndex       = result.top_pick_index;
  State.productGroups      = result.product_groups || [];

  // Sort shortlisted first, then by rank
  State.allProducts.sort((a,b) => {
    if (a.is_shortlisted && !b.is_shortlisted) return -1;
    if (!a.is_shortlisted && b.is_shortlisted) return  1;
    return (b.rank_score||0)-(a.rank_score||0);
  });
  State.displayProducts = [...State.allProducts];

  finaliseTimeline();
  document.getElementById('results').classList.remove('hidden');
  setResultsHeader(State.currentQuery, State.allProducts.length, State.platformsSearched);
  showRecommendation(State.agentExplanation);
  renderGroups(State.productGroups);
  renderProducts(State.displayProducts);

  // Smoothly scroll down to recommendations and product results
  setTimeout(() => {
    document.getElementById('results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 100);

  document.getElementById('btn-search').disabled = false;
  document.getElementById('btn-search').textContent = 'Search';
  toast(`Found ${State.allProducts.length} products!`, 'ok');
}

function onError(msg) {
  document.getElementById('btn-search').disabled = false;
  document.getElementById('btn-search').textContent = 'Search';
  toast('Search failed: ' + msg, 'err');
}

function fillQuery(el) {
  document.getElementById('query-input').value = el.textContent;
  document.getElementById('query-input').focus();
}

function rerunSearch(q) {
  document.getElementById('query-input').value = q;
  closePanel('history-panel');
  startSearch();
}

async function loadHistory() {
  const panel = document.getElementById('history-panel');
  if (!panel.classList.contains('hidden')) { closePanel('history-panel'); return; }
  try {
    // Logged-in users: backend uses JWT, no session_id needed
    // Guest users: pass the persistent session_id from localStorage
    const sessionId = State.currentUser ? null : State.sessionId;
    const data = await Api.getSearchHistory(50, sessionId);
    renderHistory(data);
  } catch(e) {
    console.error(e);
    toast('Could not load history', 'err');
  }
}

async function showOrders() {
  const panel = document.getElementById('orders-panel');
  if (!panel.classList.contains('hidden')) { closePanel('orders-panel'); return; }
  try {
    // Logged-in: backend uses JWT token automatically, no session_id needed
    // Guest: pass session_id to get guest orders
    const sessionId = State.currentUser ? null : State.sessionId;
    const data = await Api.listOrders(sessionId);
    renderOrders(data);
  } catch(e) {
    console.error(e);
    toast('Could not load orders', 'err');
  }
}
