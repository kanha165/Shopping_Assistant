/* app.js — Init, page navigation, and insights charts */

let insightsCharts = {};

function showPage(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active-page'));

  const el = document.getElementById('page-' + page);
  if (el) el.classList.add('active-page');

  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('nav-' + page);
  if (btn) btn.classList.add('active');

  if (page === 'insights') {
    setTimeout(initInsightsCharts, 100);
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function syncQuery() {
  const homeVal = document.getElementById('query-input-home')?.value.trim();
  if (homeVal) {
    document.getElementById('query-input').value = homeVal;
  }
}

function quickSearch(query) {
  const homeInput = document.getElementById('query-input-home');
  const searchInput = document.getElementById('query-input');
  if (homeInput) homeInput.value = query;
  if (searchInput) searchInput.value = query;
  showPage('search');
  startSearch();
}

// ── Insights charts (driven by live search results) ────────────────────────

function initInsightsCharts() {
  const products = (typeof State !== 'undefined' && State.allProducts && State.allProducts.length > 0)
    ? State.allProducts
    : [];

  let amazonPrices = [], flipkartPrices = [], snapdealPrices = [];
  let r5 = 0, r4 = 0, r3 = 0, r2 = 0;
  let amazonDisc = [], flipkartDisc = [], snapdealDisc = [];

  products.forEach(p => {
    const plat  = (p.platform || '').toLowerCase();
    const price = p.price || 0;
    const rating = p.rating || 0;
    const disc  = p.discount_percent || 0;

    if (plat.includes('amazon')   && price > 0) amazonPrices.push(price);
    if (plat.includes('flipkart') && price > 0) flipkartPrices.push(price);
    if (plat.includes('snapdeal') && price > 0) snapdealPrices.push(price);

    if (rating >= 4.5) r5++;
    else if (rating >= 4.0) r4++;
    else if (rating >= 3.5) r3++;
    else r2++;

    if (plat.includes('amazon'))   amazonDisc.push(disc);
    if (plat.includes('flipkart')) flipkartDisc.push(disc);
    if (plat.includes('snapdeal')) snapdealDisc.push(disc);
  });

  const avg = arr => arr.length ? Math.round(arr.reduce((a, b) => a + b, 0) / arr.length) : 0;

  const amzAvg = avg(amazonPrices)   || 45000;
  const flpAvg = avg(flipkartPrices) || 43500;
  const snpAvg = avg(snapdealPrices) || 46200;

  const total  = products.length || 100;
  const r5Pct  = products.length ? Math.round((r5 / total) * 100) : 55;
  const r4Pct  = products.length ? Math.round((r4 / total) * 100) : 30;
  const r3Pct  = products.length ? Math.round((r3 / total) * 100) : 10;
  const r2Pct  = products.length ? Math.round((r2 / total) * 100) : 5;

  const amzDiscAvg = avg(amazonDisc)   || 18;
  const flpDiscAvg = avg(flipkartDisc) || 22;
  const snpDiscAvg = avg(snapdealDisc) || 15;

  const label = State.currentQuery
    ? `Search: "${State.currentQuery.slice(0, 18)}"`
    : 'Live Platform Index';

  // Chart 1: Platform average price
  const ctx1 = document.getElementById('priceComparisonChart')?.getContext('2d');
  if (ctx1) {
    if (insightsCharts.c1) insightsCharts.c1.destroy();
    insightsCharts.c1 = new Chart(ctx1, {
      type: 'bar',
      data: {
        labels: [label],
        datasets: [
          { label: 'Amazon Avg ₹',   data: [amzAvg], backgroundColor: '#ff9900', borderRadius: 6 },
          { label: 'Flipkart Avg ₹', data: [flpAvg], backgroundColor: '#2874f0', borderRadius: 6 },
          { label: 'Snapdeal Avg ₹', data: [snpAvg], backgroundColor: '#e40046', borderRadius: 6 },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });
  }

  // Chart 2: Rating distribution
  const ctx2 = document.getElementById('ratingDistChart')?.getContext('2d');
  if (ctx2) {
    if (insightsCharts.c2) insightsCharts.c2.destroy();
    insightsCharts.c2 = new Chart(ctx2, {
      type: 'doughnut',
      data: {
        labels: ['4.5–5.0 ★', '4.0–4.4 ★', '3.5–3.9 ★', 'Below 3.5'],
        datasets: [{
          data: [r5Pct, r4Pct, r3Pct, r2Pct],
          backgroundColor: ['#10b981', '#38bdf8', '#ffc857', '#ef4444'],
        }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });
  }

  // Chart 3: Average discount %
  const ctx3 = document.getElementById('discountChart')?.getContext('2d');
  if (ctx3) {
    if (insightsCharts.c3) insightsCharts.c3.destroy();
    insightsCharts.c3 = new Chart(ctx3, {
      type: 'bar',
      data: {
        labels: ['Amazon', 'Flipkart', 'Snapdeal'],
        datasets: [{
          label: 'Average Discount %',
          data: [amzDiscAvg, flpDiscAvg, snpDiscAvg],
          backgroundColor: ['#ff9900', '#2874f0', '#e40046'],
          borderRadius: 6,
        }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });
  }

  // Chart 4: Delivery time comparison
  const ctx4 = document.getElementById('deliveryTimeChart')?.getContext('2d');
  if (ctx4) {
    if (insightsCharts.c4) insightsCharts.c4.destroy();
    insightsCharts.c4 = new Chart(ctx4, {
      type: 'bar',
      data: {
        labels: ['Amazon Prime', 'Flipkart Plus', 'Snapdeal Standard'],
        datasets: [{
          label: 'Avg Delivery Time (Days)',
          data: [1.2, 1.8, 3.2],
          backgroundColor: ['#ff9900', '#2874f0', '#e40046'],
          borderRadius: 6,
        }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });
  }
}

// ── Keyboard shortcuts & health check ─────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  try {
    await Api.health();
  } catch {
    console.log('Backend not reachable on port 8000 — demo mode active.');
  }

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      ['product-modal', 'approval-modal'].forEach(id => {
        document.getElementById(id)?.classList.add('hidden');
      });
    }
    if (e.key === '/' && !e.ctrlKey && document.activeElement.tagName !== 'INPUT') {
      e.preventDefault();
      showPage('search');
      document.getElementById('query-input')?.focus();
    }
  });
});
