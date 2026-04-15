const API_BASE = '/api/report';
const REFRESH_INTERVAL = 60000; // 60 seconds

// ─── STATE ──────────────────────────────────────────────────────────────────
let password = '';
let clicksChart = null;
let utmSortCol = 'sales';
let utmSortDir = 'desc';
let utmData = [];
let autoRefreshTimer = null;

// ─── DOM REFS ────────────────────────────────────────────────────────────────
const loginScreen     = document.getElementById('login-screen');
const dashboard       = document.getElementById('dashboard');
const passwordInput   = document.getElementById('password-input');
const loginBtn        = document.getElementById('login-btn');
const loginError      = document.getElementById('login-error');
const refreshBtn      = document.getElementById('refresh-btn');
const refreshIndicator = document.getElementById('refresh-indicator');
const lastUpdatedEl   = document.getElementById('last-updated');
const inlineError     = document.getElementById('inline-error');

// ─── FORMATTING HELPERS ──────────────────────────────────────────────────────
function formatNumber(n) {
  if (n == null || isNaN(n)) return '0';
  return Number(n).toLocaleString('en-PH');
}

function formatPeso(n) {
  if (n == null || isNaN(n)) return '₱0';
  return '₱' + Number(n).toLocaleString('en-PH', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function formatPct(num, den) {
  if (!den || den === 0) return '0.0%';
  return ((num / den) * 100).toFixed(1) + '%';
}

function formatDate(dateStr) {
  const d = new Date(dateStr);
  if (isNaN(d)) return dateStr;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function tierLabel(tier) {
  const map = { early_bird: 'Early Bird', regular: 'Regular', vip: 'VIP' };
  return map[tier] || tier;
}

function tierClass(tier) {
  const map = { early_bird: 'early-bird', regular: 'regular', vip: 'vip' };
  return map[tier] || '';
}

function now() {
  return new Date().toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// ─── API HELPERS ─────────────────────────────────────────────────────────────
async function apiFetch(action) {
  const url = `${API_BASE}?action=${action}`;
  const res = await fetch(url, {
    headers: { 'Authorization': `Bearer ${password}` }
  });

  if (res.status === 401) {
    showInlineError('Session expired. Please log out and log back in.');
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

// Expose apiFetch globally so admin-sales.js can use it after auth.
window.apiFetch = apiFetch;

// ─── AUTH ────────────────────────────────────────────────────────────────────
async function attemptLogin(pw) {
  try {
    const url = `${API_BASE}?action=auth`;
    const res = await fetch(url, {
      headers: { 'Authorization': `Bearer ${pw}` }
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.authenticated) {
        return true;
      }
    }
    return false;
  } catch {
    return false;
  }
}

async function handleLogin() {
  const pw = passwordInput.value.trim();
  if (!pw) return;

  loginBtn.disabled = true;
  loginBtn.textContent = 'Logging in…';
  loginError.style.display = 'none';

  const ok = await attemptLogin(pw);

  if (ok) {
    password = pw;
    sessionStorage.setItem('admin_pw', pw);
    showDashboard();
  } else {
    loginError.style.display = 'block';
    loginBtn.disabled = false;
    loginBtn.textContent = 'Log In';
    passwordInput.focus();
  }
}

function showDashboard() {
  loginScreen.style.display = 'none';
  dashboard.style.display = 'block';
  window.dispatchEvent(new Event('admin:authed'));
  refreshAll();
  startAutoRefresh();
}

// ─── ERROR DISPLAY ───────────────────────────────────────────────────────────
function showInlineError(msg) {
  inlineError.textContent = msg;
  inlineError.style.display = 'block';
}

function clearInlineError() {
  inlineError.style.display = 'none';
  inlineError.textContent = '';
}

// ─── LOADING INDICATOR ───────────────────────────────────────────────────────
function setLoading(loading) {
  if (loading) {
    refreshIndicator.textContent = 'Refreshing…';
    refreshIndicator.classList.add('loading');
    refreshBtn.disabled = true;
  } else {
    refreshIndicator.textContent = 'Auto-refresh: 60s';
    refreshIndicator.classList.remove('loading');
    refreshBtn.disabled = false;
  }
}

// ─── SUMMARY CARDS ───────────────────────────────────────────────────────────
async function fetchSummary() {
  const data = await apiFetch('summary');

  const visits  = data.total_visits  || 0;
  const clicks  = data.total_clicks  || 0;
  const sales   = data.total_sales   || 0;
  const revenue = data.total_revenue || 0;

  document.getElementById('stat-visits').textContent  = formatNumber(visits);
  document.getElementById('stat-clicks').textContent  = formatNumber(clicks);
  document.getElementById('stat-sales').textContent   = formatNumber(sales);
  document.getElementById('stat-revenue').textContent = formatPeso(revenue);

  // Funnel
  document.getElementById('funnel-visits').textContent         = formatNumber(visits);
  document.getElementById('funnel-clicks').textContent         = formatNumber(clicks);
  document.getElementById('funnel-sales').textContent          = formatNumber(sales);
  document.getElementById('funnel-visit-click-pct').textContent = formatPct(clicks, visits);
  document.getElementById('funnel-click-sale-pct').textContent  = formatPct(sales, clicks);
}

// ─── UTM TABLE ───────────────────────────────────────────────────────────────
async function fetchByUTM() {
  const data = await apiFetch('by_utm');
  utmData = Array.isArray(data) ? data : [];
  renderUTMTable();
}

function renderUTMTable() {
  const tbody = document.getElementById('utm-table-body');

  if (!utmData.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state" style="display:block"><span class="empty-icon">📊</span><p>No data yet. Check back once tracking is live.</p></div></td></tr>`;
    return;
  }

  // Sort
  const sorted = [...utmData].sort((a, b) => {
    let av = a[utmSortCol] ?? 0;
    let bv = b[utmSortCol] ?? 0;
    if (typeof av === 'string') av = av.toLowerCase();
    if (typeof bv === 'string') bv = bv.toLowerCase();
    if (av < bv) return utmSortDir === 'asc' ? -1 : 1;
    if (av > bv) return utmSortDir === 'asc' ? 1 : -1;
    return 0;
  });

  // Find top performer (most sales)
  const maxSales = Math.max(...utmData.map(r => r.sales || 0));

  // Totals
  const totals = utmData.reduce((acc, r) => {
    acc.visits     += r.visits     || 0;
    acc.clicks     += r.clicks     || 0;
    acc.sales      += r.sales      || 0;
    acc.revenue    += r.revenue    || 0;
    acc.early_bird += r.early_bird || 0;
    acc.regular    += r.regular    || 0;
    acc.vip        += r.vip        || 0;
    return acc;
  }, { visits: 0, clicks: 0, sales: 0, revenue: 0, early_bird: 0, regular: 0, vip: 0 });

  let html = '';

  for (const row of sorted) {
    const source = row.utm_source || 'direct';
    const isTop = maxSales > 0 && (row.sales || 0) === maxSales;
    const badgeClass = source === 'direct' ? 'source-badge direct' : 'source-badge';

    html += `
      <tr${isTop ? ' class="top-performer"' : ''}>
        <td class="source-cell"><span class="${badgeClass}">${escapeHtml(source)}</span></td>
        <td>${formatNumber(row.visits)}</td>
        <td>${formatNumber(row.clicks)}</td>
        <td class="sales-cell">${formatNumber(row.sales)}</td>
        <td class="revenue-cell">${formatPeso(row.revenue)}</td>
        <td>${formatNumber(row.early_bird)}</td>
        <td>${formatNumber(row.regular)}</td>
        <td>${formatNumber(row.vip)}</td>
      </tr>
    `;
  }

  // Totals row
  html += `
    <tr class="totals-row">
      <td class="source-cell">Total</td>
      <td>${formatNumber(totals.visits)}</td>
      <td>${formatNumber(totals.clicks)}</td>
      <td class="sales-cell">${formatNumber(totals.sales)}</td>
      <td class="revenue-cell">${formatPeso(totals.revenue)}</td>
      <td>${formatNumber(totals.early_bird)}</td>
      <td>${formatNumber(totals.regular)}</td>
      <td>${formatNumber(totals.vip)}</td>
    </tr>
  `;

  tbody.innerHTML = html;
  syncSortHeaders();
}

function syncSortHeaders() {
  const headers = document.querySelectorAll('#utm-table thead th');
  headers.forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.col === utmSortCol) {
      th.classList.add(utmSortDir === 'asc' ? 'sort-asc' : 'sort-desc');
    }
  });
}

function handleUTMSort(col) {
  if (utmSortCol === col) {
    utmSortDir = utmSortDir === 'asc' ? 'desc' : 'asc';
  } else {
    utmSortCol = col;
    utmSortDir = 'desc';
  }
  renderUTMTable();
}

// ─── TIER TABLE ──────────────────────────────────────────────────────────────
async function fetchByTier() {
  const data = await apiFetch('by_tier');
  const rows = Array.isArray(data) ? data : [];
  const tbody = document.getElementById('tier-table-body');

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state" style="display:block"><span class="empty-icon">🎫</span><p>No ticket data yet.</p></div></td></tr>`;
    return;
  }

  const totalRevenue = rows.reduce((sum, r) => sum + (r.revenue || 0), 0);

  let html = '';
  for (const row of rows) {
    const label = tierLabel(row.tier);
    const cls   = tierClass(row.tier);
    const pct   = formatPct(row.revenue || 0, totalRevenue);

    html += `
      <tr>
        <td><span class="tier-badge ${cls}">${escapeHtml(label)}</span></td>
        <td>${formatNumber(row.count)}</td>
        <td class="revenue-cell">${formatPeso(row.revenue)}</td>
        <td>${pct}</td>
      </tr>
    `;
  }

  tbody.innerHTML = html;
}

// ─── CHART ───────────────────────────────────────────────────────────────────
async function fetchClicksOverTime() {
  const data = await apiFetch('clicks_over_time');
  const rows = Array.isArray(data) ? data : [];
  renderChart(rows);
}

function renderChart(rows) {
  const ctx = document.getElementById('clicks-chart').getContext('2d');

  const labels = rows.map(r => formatDate(r.date));
  const counts  = rows.map(r => r.count || 0);

  if (clicksChart) {
    clicksChart.data.labels = labels;
    clicksChart.data.datasets[0].data = counts;
    clicksChart.update();
    return;
  }

  clicksChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Clicks',
        data: counts,
        backgroundColor: '#4dd4c8',
        hoverBackgroundColor: '#f3ba5b',
        borderRadius: 4,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a2f3a',
          borderColor: '#233c48',
          borderWidth: 1,
          titleColor: '#e8eaf0',
          bodyColor: '#9aa3b8',
          callbacks: {
            label: (ctx) => ` ${formatNumber(ctx.parsed.y)} clicks`
          }
        }
      },
      scales: {
        x: {
          ticks: {
            color: '#6b7a99',
            font: { family: 'Space Grotesk', size: 12 }
          },
          grid: { color: 'rgba(255,255,255,0.04)' }
        },
        y: {
          ticks: {
            color: '#6b7a99',
            font: { family: 'Space Grotesk', size: 12 },
            callback: (v) => formatNumber(v)
          },
          grid: { color: 'rgba(255,255,255,0.06)' },
          beginAtZero: true
        }
      }
    }
  });
}

// ─── REFRESH ALL ─────────────────────────────────────────────────────────────
async function refreshAll() {
  clearInlineError();
  setLoading(true);

  try {
    await Promise.all([
      fetchSummary(),
      fetchByUTM(),
      fetchByTier(),
      fetchClicksOverTime(),
    ]);
    lastUpdatedEl.textContent = `Last updated: ${now()}`;
  } catch (err) {
    if (err.message !== 'Unauthorized') {
      showInlineError('Could not load data. Check your connection or try refreshing.');
    }
  } finally {
    setLoading(false);
  }
}

// ─── AUTO-REFRESH ────────────────────────────────────────────────────────────
function startAutoRefresh() {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer);
  autoRefreshTimer = setInterval(refreshAll, REFRESH_INTERVAL);
}

// ─── UTILITY ─────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

// ─── EVENT LISTENERS ─────────────────────────────────────────────────────────
loginBtn.addEventListener('click', handleLogin);

passwordInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') handleLogin();
});

refreshBtn.addEventListener('click', () => {
  refreshAll();
  // Reset the auto-refresh timer so it doesn't fire too soon after manual refresh
  startAutoRefresh();
});

// Sort UTM table on header click
document.getElementById('utm-table').addEventListener('click', (e) => {
  const th = e.target.closest('thead th[data-col]');
  if (th) handleUTMSort(th.dataset.col);
});

// ─── INIT ────────────────────────────────────────────────────────────────────
(async function init() {
  const saved = sessionStorage.getItem('admin_pw');
  if (saved) {
    const ok = await attemptLogin(saved);
    if (ok) {
      password = saved;
      showDashboard();
      return;
    } else {
      sessionStorage.removeItem('admin_pw');
    }
  }
  // Show login
  loginScreen.style.display = 'flex';
  passwordInput.focus();
})();
