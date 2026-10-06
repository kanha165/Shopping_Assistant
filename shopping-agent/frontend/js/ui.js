/* ui.js — All DOM rendering */

// ── Timeline ────────────────────────────────────────────────────────────────
const TIMELINE_STEPS = [
  { id: 'parse',    icon: '🔍', label: 'Understanding your request'       },
  { id: 'search',   icon: '🌐', label: 'Searching marketplaces'           },
  { id: 'dedup',    icon: '🔎', label: 'Matching products across platforms'},
  { id: 'cost',     icon: '💰', label: 'Calculating total costs'          },
  { id: 'filter',   icon: '⚖️',  label: 'Filtering & ranking'             },
  { id: 'reviews',  icon: '⭐', label: 'Analyzing reviews'                },
  { id: 'recommend',icon: '🤖', label: 'Preparing recommendation'         },
];

function initTimeline() {
  const tl = document.getElementById('timeline');
  tl.innerHTML = TIMELINE_STEPS.map(s => `
    <div class="t-step" id="ts-${s.id}">
      <span class="t-icon">${s.icon}</span>
      <span>${s.label}</span>
    </div>
  `).join('');
  document.getElementById('timeline-wrap').classList.remove('hidden');
  initPlatformPills();
}

function setTimelineStep(stepId, status, extra) {
  const el = document.getElementById(`ts-${stepId}`);
  if (!el) return;
  el.className = `t-step ${status}`;
  if (status === 'active') {
    const icon = el.querySelector('.t-icon');
    icon.outerHTML = '<div class="t-spinner"></div>';
  }
  if (status === 'done') {
    const spinner = el.querySelector('.t-spinner');
    if (spinner) {
      const step = TIMELINE_STEPS.find(s => s.id === stepId);
      spinner.outerHTML = `<span class="t-icon">${step ? step.icon : '✅'}</span>`;
    }
  }
}

function _msgToStepId(msg) {
  const m = msg.toLowerCase();
  if (m.includes('understanding') || m.includes('query'))  return 'parse';
  if (m.includes('searching'))                              return 'search';
  if (m.includes('matching') || m.includes('dedup'))       return 'dedup';
  if (m.includes('cost'))                                   return 'cost';
  if (m.includes('filter') || m.includes('ranking'))       return 'filter';
  if (m.includes('review'))                                 return 'reviews';
  if (m.includes('recommend') || m.includes('preparing'))  return 'recommend';
  return null;
}

function addTimelineEvent(type, message) {
  const stepId = _msgToStepId(message);
  if (stepId) {
    if (type === 'thinking' || type === 'status') setTimelineStep(stepId, 'active');
    if (type === 'done')                          setTimelineStep(stepId, 'done');
  }
  // Add to state log too
  State.timelineSteps.push({ type, message });
}

// Platform pills
function initPlatformPills() {
  const row = document.getElementById('platform-row');
  const platforms = ['Amazon', 'Flipkart', 'Snapdeal', 'Meesho', 'Myntra'];
  row.innerHTML = platforms.map(p =>
    `<span class="p-pill searching" id="pp-${p.toLowerCase()}">${p}</span>`
  ).join('');
}

function setPlatformPill(platform, status) {
  const el = document.getElementById(`pp-${platform.toLowerCase()}`);
  if (!el) return;
  el.className = `p-pill ${status}`;
  const icons = { ok: '✓ ', fail: '⚠️ ', searching: '⟳ ' };
  const labels = {
    meesho: 'Meesho (bot protection)',
    myntra: 'Myntra (JS required)',
  };
  const name = platform.charAt(0).toUpperCase() + platform.slice(1);
  const text = status === 'fail' && labels[platform.toLowerCase()] ? labels[platform.toLowerCase()] : name;
  el.textContent = (icons[status] || '') + text;
}

function finaliseTimeline() {
  TIMELINE_STEPS.forEach(s => setTimelineStep(s.id, 'done'));
  Object.entries(State.platformStatus).forEach(([p, s]) => {
    const status = (typeof s === 'object' && s.status) ? s.status : (s === 'ok' ? 'ok' : 'fail');
    setPlatformPill(p, status === 'ok' ? 'ok' : 'fail');
  });
}

// ── Results ──────────────────────────────────────────────────────────────────
function showResults() { document.getElementById('results').classList.remove('hidden'); }

function setResultsHeader(query, total, platforms) {
  document.getElementById('results-title').textContent = `Results for "${query}"`;
  const failed = Object.entries(State.platformStatus)
    .filter(([,v]) => v !== 'ok').map(([k]) => k);
  let sub = `${total} products found on ${platforms.join(', ')}`;
  if (failed.length) sub += ` (${failed.join(', ')}: unavailable)`;
  document.getElementById('results-subtitle').textContent = sub;
}

function showRecommendation(text) {
  if (!text) return;
  document.getElementById('rec-text').textContent = text;
  document.getElementById('rec-banner').classList.remove('hidden');
}

// ── Cross-platform groups ────────────────────────────────────────────────────
function renderGroups(groups) {
  const sec = document.getElementById('groups-section');
  if (!groups || groups.length === 0) { sec.innerHTML = ''; return; }

  sec.innerHTML = `<h3 style="font-size:.9rem;font-weight:600;margin-bottom:10px;color:#333">
    📊 Same product on multiple platforms</h3>` +
    groups.map(g => `
      <div class="group-card">
        <div class="group-title">${esc(g.product_key)}</div>
        <div class="group-rows">
          ${g.items.map(p => {
            const unavail = !p.price || p.price <= 0 || p.price > 5000000;
            return `
            <div class="group-row ${p.is_cheapest_for_product && !unavail ? 'cheapest' : ''}">
              ${p.is_cheapest_for_product && !unavail
                ? `<span class="cheapest-tag">Cheapest</span>`
                : `<span style="width:68px"></span>`}
              <span class="group-platform platform-badge pb-${esc(p.platform)}">${esc(p.platform)}</span>
              <span class="group-price">${unavail ? '<span style="color:#dc2626;font-size:.75rem">Unavailable</span>' : fmtPrice(p.price)}</span>
              <span class="group-total">${unavail ? '' : 'Total: ' + fmtPrice(p.total_cost)}</span>
              <span class="group-delivery">${esc(p.delivery_info || '')}</span>
              ${unavail
                ? `<button class="btn-outline btn-sm" disabled style="opacity:.45;cursor:not-allowed">Unavailable</button>`
                : `<button class="btn-primary btn-sm"
                    onclick="openPurchaseFlow(${JSON.stringify(p).replace(/"/g,'&quot;')})">
                    Buy
                   </button>`}
            </div>`
          }).join('')}
        </div>
      </div>
    `).join('');
}

// ── Product Cards ────────────────────────────────────────────────────────────
function renderProducts(products) {
  const grid  = document.getElementById('product-grid');
  const empty = document.getElementById('empty-msg');
  if (!products || products.length === 0) {
    grid.innerHTML = ''; empty.classList.remove('hidden'); return;
  }
  empty.classList.add('hidden');
  grid.innerHTML = products.map((p, i) => buildCard(p, i)).join('');
}

function buildCard(p, i) {
  const rank = i + 1;
  const isTop  = State.topPickIndex ? rank === State.topPickIndex : rank === 1;
  const isCheap = p.is_lowest_price;
  const ratingClass = !p.rating ? '' : p.rating >= 4 ? '' : p.rating >= 3 ? 'mid' : 'low';
  const enc = encodeURIComponent(JSON.stringify(p));

  // Unavailable: availability explicitly false, OR price is null/0, OR price looks corrupt (> ₹50 lakh)
  const isUnavailable = p.availability === false || !p.price || p.price <= 0 || p.price > 5000000;

  const rankBadge = rank === 1
    ? `<div class="rank-badge gold">🥇 #1 Best Match</div>`
    : rank === 2
    ? `<div class="rank-badge silver">🥈 #2 Top Value</div>`
    : rank === 3
    ? `<div class="rank-badge bronze">🥉 #3 Great Choice</div>`
    : `<div class="rank-badge standard">#${rank} Ranked</div>`;

  const scoreBadge = p.rank_score ? `<span class="score-pill">⚡ Score: ${Math.round(p.rank_score)}%</span>` : '';

  // Price section — show "Unavailable" badge instead of corrupt/missing price
  const priceSection = isUnavailable
    ? `<div class="pcard-pricing">
         <span style="display:inline-block;background:#fee2e2;color:#dc2626;font-size:.78rem;
           font-weight:600;padding:3px 10px;border-radius:20px;letter-spacing:.3px">
           ⚠️ Price Unavailable
         </span>
       </div>`
    : `<div class="pcard-pricing">
         <span class="pcard-price">${fmtPrice(p.price)}</span>
         ${p.original_price && p.original_price > p.price
           ? `<span class="pcard-orig">${fmtPrice(p.original_price)}</span>
              <span class="pcard-disc">${Math.round(p.discount_percent||0)}% off</span>`
           : ''}
       </div>
       ${p.shipping_cost > 0
         ? `<div class="pcard-total">+ ₹${p.shipping_cost} shipping | Total: ${fmtPrice(p.total_cost)}</div>`
         : p.total_cost
           ? `<div class="pcard-total" style="color:#10b981;font-weight:600">Free shipping | Total: ${fmtPrice(p.total_cost)}</div>`
           : ''}`;

  return `
    <div class="pcard ${isTop ? 'top-pick' : ''} ${isUnavailable ? 'pcard-unavailable' : ''}">
      <div class="pcard-header-bar">
        ${rankBadge}
        ${scoreBadge}
      </div>
      ${isCheap && !isTop && !isUnavailable ? `<div class="cheapest-price-tag">💰 Lowest Total Price</div>` : ''}
      <div class="pcard-img">
        ${p.image_url
          ? `<img src="${esc(p.image_url)}" alt="${esc(p.product_name)}"
               onerror="this.parentElement.innerHTML='<div class=no-img>🛍️</div>'" loading="lazy"/>`
          : `<div class="no-img">🛍️</div>`}
      </div>
      <div class="pcard-body" onclick="openDetail('${enc}')">
        <span class="platform-badge pb-${esc(p.platform)}">${esc(p.platform)}</span>
        <div class="pcard-name">${esc(p.product_name)}</div>
        ${priceSection}
        ${p.rating
          ? `<div class="pcard-rating">
               <span class="rating-pill ${ratingClass}">★ ${p.rating.toFixed(1)}</span>
               ${p.review_count ? `<span>${fmtNum(p.review_count)} reviews</span>` : ''}
             </div>` : ''}
        ${p.delivery_info ? `<div class="pcard-delivery">🚚 ${esc(p.delivery_info)}</div>` : ''}
      </div>
      <div class="pcard-footer">
        <button class="btn-outline btn-sm" onclick="openDetail('${enc}')">Details</button>
        ${isUnavailable
          ? `<button class="btn-outline btn-sm" disabled style="opacity:.45;cursor:not-allowed">Unavailable</button>`
          : `<button class="btn-primary btn-sm" onclick="openPurchaseFlow(${JSON.stringify(p).replace(/"/g,'&quot;')});event.stopPropagation()">
               🛒 Buy Now
             </button>`}
      </div>
    </div>
  `;
}

// ── Product Detail Modal ────────────────────────────────────────────────────
function openDetail(enc) {
  const p = JSON.parse(decodeURIComponent(enc));
  const rs = p.review_summary;

  document.getElementById('product-modal-body').innerHTML = `
    <div class="detail-layout">
      <div>
        ${p.image_url
          ? `<img class="detail-img" src="${esc(p.image_url)}" alt="${esc(p.product_name)}"
               onerror="this.src=''"/>`
          : `<div class="detail-img" style="display:flex;align-items:center;justify-content:center;font-size:5rem">🛍️</div>`}
      </div>
      <div class="detail-info">
        <span class="platform-badge pb-${esc(p.platform)}">${esc(p.platform)}</span>
        <h2 class="detail-title">${esc(p.product_name)}</h2>
        <div>
          <span class="detail-price">${fmtPrice(p.price)}</span>
          ${p.original_price && p.original_price > p.price
            ? `<span class="pcard-orig" style="font-size:.9rem;margin-left:8px">${fmtPrice(p.original_price)}</span>
               <span class="pcard-disc" style="font-size:.82rem;margin-left:4px">${Math.round(p.discount_percent||0)}% off</span>`
            : ''}
        </div>
        <div style="font-size:.82rem;color:#555">
          Shipping: ${p.shipping_cost > 0 ? fmtPrice(p.shipping_cost) : 'Free'}
          &nbsp;|&nbsp;
          <strong>Total: ${fmtPrice(p.total_cost || p.price)}</strong>
        </div>
        ${p.rating
          ? `<div class="pcard-rating" style="margin-top:2px">
               <span class="rating-pill">★ ${p.rating.toFixed(1)}</span>
               ${p.review_count ? `<span>${fmtNum(p.review_count)} reviews</span>` : ''}
             </div>` : ''}
        ${p.delivery_info   ? `<p style="font-size:.82rem;color:#555">🚚 ${esc(p.delivery_info)}</p>` : ''}
        ${p.return_policy   ? `<p style="font-size:.82rem;color:#555">↩️ ${esc(p.return_policy)}</p>` : ''}
        ${p.seller          ? `<p style="font-size:.82rem;color:#555">🏪 Sold by ${esc(p.seller)}</p>` : ''}
        <div class="detail-actions">
          <a class="btn-outline" href="${esc(p.product_url)}" target="_blank" rel="noopener">
            View on ${esc(p.platform)}
          </a>
          <button class="btn-primary"
            onclick="openPurchaseFlow(${JSON.stringify(p).replace(/"/g,'&quot;')});closeModal('product-modal')">
            🛒 Buy Now
          </button>
        </div>
      </div>
    </div>

    ${p.specifications && Object.keys(p.specifications).length > 0 ? `
      <div style="margin-top:20px">
        <h4 style="margin-bottom:9px;font-size:.88rem">Specifications</h4>
        <div class="spec-grid">
          ${Object.entries(p.specifications).slice(0,12).map(([k,v]) => `
            <div class="spec-item">
              <div class="spec-key">${esc(k)}</div>
              <div class="spec-val">${esc(String(v))}</div>
            </div>`).join('')}
        </div>
      </div>` : ''}

    ${rs ? `
      <div style="margin-top:20px">
        <h4 style="margin-bottom:9px;font-size:.88rem">
          Review Analysis
          <small style="font-weight:400;color:#888;font-size:.72rem"> (based on actual reviews)</small>
        </h4>
        <div class="review-box">
          <span class="sentiment-badge s-${rs.overall_sentiment||'unknown'}">
            ${sentEmoji(rs.overall_sentiment)} ${cap(rs.overall_sentiment||'unknown')}
          </span>
          ${rs.review_summary ? `<p style="font-size:.82rem;color:#444;margin-bottom:8px">${esc(rs.review_summary)}</p>` : ''}
          ${(rs.pros||rs.positive_themes||[]).length ? `
            <p style="font-size:.76rem;color:#666;margin-bottom:4px">👍 Customers liked</p>
            <div class="theme-row">
              ${(rs.pros||rs.positive_themes||[]).map(t=>`<span class="theme-tag pos">${esc(t)}</span>`).join('')}
            </div>` : ''}
          ${(rs.cons||rs.negative_themes||[]).length ? `
            <p style="font-size:.76rem;color:#666;margin-top:10px;margin-bottom:4px">👎 Complaints</p>
            <div class="theme-row">
              ${(rs.cons||rs.negative_themes||[]).map(t=>`<span class="theme-tag neg">${esc(t)}</span>`).join('')}
            </div>` : ''}
        </div>
      </div>` : ''}
  `;
  openModal('product-modal');
}

// ── Compare Table ────────────────────────────────────────────────────────────
function renderCompare(products) {
  const wrap = document.getElementById('compare-wrap');
  const tbl  = document.getElementById('compare-table');
  if (!products || products.length === 0) { wrap.classList.add('hidden'); return; }

  const top = products.slice(0, 6);
  const prices = top.map(p => p.total_cost||p.price||0).filter(Boolean);
  const minPrice = prices.length ? Math.min(...prices) : null;
  const ratings  = top.map(p => p.rating||0);
  const maxRating = ratings.length ? Math.max(...ratings) : null;

  const header = `<thead><tr>
    <th style="width:130px">Feature</th>
    ${top.map(p => `<th>
      <span class="platform-badge pb-${p.platform}">${p.platform}</span><br/>
      <span style="font-size:.78rem;font-weight:600">${esc(p.product_name.slice(0,40))}…</span>
    </th>`).join('')}
  </tr></thead>`;

  const rows = [
    { label:'Price',    fn: p => fmtPrice(p.price),    best: p => (p.total_cost||p.price) === minPrice },
    { label:'Shipping', fn: p => p.shipping_cost > 0 ? fmtPrice(p.shipping_cost) : 'Free' },
    { label:'Total',    fn: p => fmtPrice(p.total_cost||p.price), best: p => (p.total_cost||p.price) === minPrice },
    { label:'Rating',   fn: p => p.rating ? `★ ${p.rating.toFixed(1)}` : '—', best: p => p.rating === maxRating },
    { label:'Reviews',  fn: p => p.review_count ? fmtNum(p.review_count) : '—' },
    { label:'Delivery', fn: p => p.delivery_info || '—' },
    { label:'Return',   fn: p => p.return_policy || '—' },
    { label:'Seller',   fn: p => p.seller || '—' },
  ];

  const body = `<tbody>${rows.map(r => `<tr>
    <td><strong>${r.label}</strong></td>
    ${top.map(p => `<td class="${r.best && r.best(p) ? 'best-cell' : ''}">${r.fn(p)}</td>`).join('')}
  </tr>`).join('')}</tbody>`;

  tbl.innerHTML = header + body;
  wrap.classList.remove('hidden');
}

// ── Sort / Filter ────────────────────────────────────────────────────────────
function applySort() {
  State.sortBy = document.getElementById('sort-select').value;
  applyFilters();
}

function applyFilters() {
  const maxPrice  = parseFloat(document.getElementById('filter-price').value)  || null;
  const minRating = parseFloat(document.getElementById('filter-rating').value) || null;
  const platform  = document.getElementById('filter-platform').value || '';

  let products = [...State.allProducts];
  if (maxPrice)  products = products.filter(p => !p.price   || p.price   <= maxPrice);
  if (minRating) products = products.filter(p => !p.rating  || p.rating  >= minRating);
  if (platform)  products = products.filter(p => p.platform === platform);

  switch (State.sortBy) {
    case 'price_asc':   products.sort((a,b)=>(a.price||99999)-(b.price||99999)); break;
    case 'price_desc':  products.sort((a,b)=>(b.price||0)-(a.price||0)); break;
    case 'rating':      products.sort((a,b)=>(b.rating||0)-(a.rating||0)); break;
    case 'total_cost':  products.sort((a,b)=>(a.total_cost||a.price||99999)-(b.total_cost||b.price||99999)); break;
    default:            products.sort((a,b)=>(b.rank_score||0)-(a.rank_score||0));
  }

  State.displayProducts = products;
  renderProducts(products);
  if (State.view === 'compare') renderCompare(products);
}

function clearFilters() {
  document.getElementById('filter-price').value   = '';
  document.getElementById('filter-rating').value  = '';
  document.getElementById('filter-platform').value= '';
  applyFilters();
}

function setView(v) {
  State.view = v;
  ['grid','list','compare'].forEach(x =>
    document.getElementById(`btn-${x}`)?.classList.toggle('active-view', x === v)
  );
  const grid    = document.getElementById('product-grid');
  const compare = document.getElementById('compare-wrap');

  if (v === 'list') {
    grid.classList.remove('hidden'); grid.classList.add('list-view');
    compare.classList.add('hidden');
  } else if (v === 'compare') {
    grid.classList.add('hidden');
    compare.classList.remove('hidden');
    renderCompare(State.displayProducts);
  } else {
    grid.classList.remove('hidden'); grid.classList.remove('list-view');
    compare.classList.add('hidden');
  }
}

// ── History & Orders ─────────────────────────────────────────────────────────
function renderHistory(items) {
  const el = document.getElementById('history-list');
  if (!items || items.length === 0) {
    el.innerHTML = `
      <div class="empty-panel">
        <div style="font-size:2rem;margin-bottom:6px">🔍</div>
        <p style="color:#666;font-size:.9rem;font-weight:500">No search history yet</p>
        <p style="color:#999;font-size:.78rem;margin-top:2px">Your past product searches will be saved here.</p>
      </div>`;
    document.getElementById('history-panel').classList.remove('hidden');
    return;
  }

  el.innerHTML = items.map(s => `
    <div class="history-card" onclick="rerunSearch('${esc(s.raw_query)}')">
      <div class="hc-info">
        <div class="hi-query">🔍 "${esc(s.raw_query)}"</div>
        <div class="hi-meta">
          <span>📅 ${new Date(s.created_at).toLocaleDateString('en-IN', {day:'numeric', month:'short', year:'numeric'})}</span>
          ${(s.platforms_searched||[]).length ? `<span>• ${s.platforms_searched.map(cap).join(', ')}</span>` : ''}
        </div>
      </div>
      <button class="btn-outline btn-sm" onclick="event.stopPropagation();rerunSearch('${esc(s.raw_query)}')">
        🔄 Re-run
      </button>
    </div>`).join('');
  document.getElementById('history-panel').classList.remove('hidden');
}

function renderOrders(orders) {
  const el = document.getElementById('orders-list');
  if (!orders || orders.length === 0) {
    el.innerHTML = `
      <div class="empty-panel">
        <div style="font-size:2rem;margin-bottom:6px">📦</div>
        <p style="color:#666;font-size:.9rem;font-weight:500">No orders placed yet</p>
        <p style="color:#999;font-size:.78rem;margin-top:2px">Confirmed purchases and cart handoffs will appear here.</p>
      </div>`;
    document.getElementById('orders-panel').classList.remove('hidden');
    return;
  }

  el.innerHTML = orders.map(o => `
    <div class="order-card">
      <div class="oc-top">
        <span class="platform-badge pb-${esc(o.platform)}">${esc(o.platform)}</span>
        <span class="oi-status ${statusCss(o.status)}">${esc(o.status.replace(/_/g,' '))}</span>
      </div>
      <div class="oi-name">${esc(o.product_name)}</div>
      <div class="oc-bottom">
        <span class="oc-price">${fmtPrice(o.total_amount)}</span>
        <span class="oc-date">📅 ${new Date(o.created_at).toLocaleDateString('en-IN', {day:'numeric', month:'short'})}</span>
        ${o.cart_url || o.marketplace_url ? `
          <a class="btn-primary btn-sm" href="${esc(o.cart_url || o.marketplace_url)}" target="_blank" rel="noopener" style="text-decoration:none">
            Open Deal →
          </a>` : ''}
      </div>
    </div>`).join('');
  document.getElementById('orders-panel').classList.remove('hidden');
}

function statusCss(s) {
  if (s.includes('confirmed')) return 'st-confirmed';
  if (s.includes('cancel'))    return 'st-cancelled';
  if (s.includes('progress'))  return 'st-progress';
  return 'st-pending';
}

function closePanel(id) { document.getElementById(id).classList.add('hidden'); }

// ── Modal helpers ────────────────────────────────────────────────────────────
function openModal(id)  { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }
function overlayClose(e, id) { if (e.target === e.currentTarget) closeModal(id); }

// ── Toast ────────────────────────────────────────────────────────────────────
let _toastT;
function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type}`;
  el.classList.remove('hidden');
  clearTimeout(_toastT);
  _toastT = setTimeout(() => el.classList.add('hidden'), 3200);
}

// ── Formatters ───────────────────────────────────────────────────────────────
function fmtPrice(v) {
  if (!v || v <= 0 || v > 5000000) return '—';
  return '₹' + Number(v).toLocaleString('en-IN');
}
function fmtNum(n)   { return n >= 1000 ? (n/1000).toFixed(1)+'K' : String(n); }
function cap(s)      { return s ? s[0].toUpperCase() + s.slice(1) : ''; }
function sentEmoji(s){ return s==='positive'?'😊':s==='negative'?'😞':'😐'; }
function esc(s) {
  if (typeof s !== 'string') return String(s || '');
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;')
           .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
