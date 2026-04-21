// Admin dashboard — Webinar Funnel Attendees section.
// Loaded AFTER js/admin.js and js/admin-sales.js. Scoped in an IIFE so it
// cannot collide with variables in the other admin scripts.
//
// Strategy: poll sessionStorage for 'admin_pw' (set by admin.js after login)
// for the first ~60s of page life. Once present, fetch /api/webinar-report
// with the Bearer token and render. Dashboard section is hidden by default
// (display:none in HTML) and only revealed when the fetch succeeds — so
// anonymous pageviews never see the section even briefly.
(function () {
  const ENDPOINT = '/api/webinar-report';
  const POLL_EVERY_MS = 1000;
  const GIVE_UP_AFTER_MS = 60000;

  let loaded = false;
  let chart = null;
  let rawRows = [];
  let pollHandle = null;

  // ─── Helpers ──────────────────────────────────────────────────────────
  function getPassword() {
    try { return sessionStorage.getItem('admin_pw') || ''; } catch (_) { return ''; }
  }

  function maskEmail(email) {
    if (!email || typeof email !== 'string') return '';
    const at = email.indexOf('@');
    if (at < 2) return '***' + email.slice(at);
    const local = email.slice(0, at);
    const domain = email.slice(at);
    const visible = local.slice(0, 2);
    return visible + '*'.repeat(Math.max(1, local.length - 2)) + domain;
  }

  function formatTimestamp(ts) {
    if (!ts) return '—';
    const d = new Date(ts);
    if (isNaN(d.getTime())) return String(ts).slice(0, 16);
    // Always display in PHT (UTC+8) for consistency with the rest of the admin
    return d.toLocaleString('en-PH', {
      timeZone: 'Asia/Manila',
      year: 'numeric', month: 'short', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false,
    });
  }

  function escapeHTML(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }

  // ─── Rendering ────────────────────────────────────────────────────────
  function renderKPIs(data) {
    const totalEl = document.getElementById('webinar-total');
    const todayEl = document.getElementById('webinar-today');
    const weekEl = document.getElementById('webinar-week');
    if (!totalEl || !todayEl || !weekEl) return;

    totalEl.textContent = data.total.toLocaleString();

    const today = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Manila' }); // YYYY-MM-DD
    const now = new Date();
    const weekAgo = new Date(now.getTime() - 7 * 24 * 3600 * 1000);

    let todayCount = 0;
    let weekCount = 0;
    for (const row of data.rows) {
      if (!row.timestamp) continue;
      const d = new Date(row.timestamp);
      if (isNaN(d.getTime())) continue;
      const phtDate = d.toLocaleDateString('en-CA', { timeZone: 'Asia/Manila' });
      if (phtDate === today) todayCount++;
      if (d >= weekAgo) weekCount++;
    }
    todayEl.textContent = todayCount.toLocaleString();
    weekEl.textContent = weekCount.toLocaleString();
  }

  function renderChart(byDay) {
    const canvas = document.getElementById('webinar-chart');
    if (!canvas || typeof Chart === 'undefined') return;

    const labels = byDay.map(d => d.date);
    const counts = byDay.map(d => d.count);

    if (chart) { chart.destroy(); chart = null; }

    chart = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Registrations',
          data: counts,
          backgroundColor: 'rgba(13, 148, 136, 0.7)',
          borderColor: '#0D9488',
          borderWidth: 1,
          borderRadius: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#9aa3b8' }, grid: { color: 'rgba(154,163,184,0.08)' } },
          y: { beginAtZero: true, ticks: { color: '#9aa3b8', precision: 0 }, grid: { color: 'rgba(154,163,184,0.08)' } },
        },
      },
    });
  }

  function renderTable(rows) {
    const body = document.getElementById('webinar-table-body');
    if (!body) return;

    if (!rows.length) {
      body.innerHTML = `
        <tr><td colspan="4">
          <div class="empty-state" style="display:block">
            <span class="empty-icon">🎟️</span>
            <p>No webinar registrations yet.</p>
          </div>
        </td></tr>`;
      return;
    }

    const html = rows.slice(0, 20).map(r => `
      <tr>
        <td>${escapeHTML(formatTimestamp(r.timestamp))}</td>
        <td>${escapeHTML(r.name)}</td>
        <td style="font-family:'SF Mono',Menlo,monospace;font-size:13px;">${escapeHTML(maskEmail(r.email))}</td>
        <td style="font-family:'SF Mono',Menlo,monospace;font-size:13px;">${escapeHTML(r.phone)}</td>
      </tr>
    `).join('');
    body.innerHTML = html;
  }

  function renderAll(data) {
    renderKPIs(data);
    renderChart(data.by_day || []);
    renderTable(data.rows || []);
    const section = document.getElementById('webinar-section');
    if (section) section.style.display = 'block';
  }

  // ─── CSV export ───────────────────────────────────────────────────────
  function csvEscape(v) {
    const s = String(v == null ? '' : v);
    if (/[",\n\r]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
    return s;
  }

  function exportCSV() {
    if (!rawRows.length) return;
    const headers = ['timestamp', 'name', 'email', 'phone'];
    const lines = [headers.join(',')];
    for (const r of rawRows) {
      lines.push(headers.map(h => csvEscape(r[h])).join(','));
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const stamp = new Date().toISOString().replace(/[:T.]/g, '-').slice(0, 19);
    a.download = `webinar-registrations-${stamp}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ─── Load ─────────────────────────────────────────────────────────────
  async function loadWebinarData() {
    if (loaded) return;
    const pw = getPassword();
    if (!pw) return;

    try {
      const res = await fetch(ENDPOINT, {
        headers: { 'Authorization': 'Bearer ' + pw },
        cache: 'no-store',
      });
      if (res.status === 401) return; // wrong password — admin.js will handle login
      if (!res.ok) {
        console.warn('webinar-report:', res.status);
        return;
      }
      const data = await res.json();
      if (!data || !data.ok) return;
      rawRows = data.rows || [];
      renderAll(data);
      loaded = true;
      if (pollHandle) { clearInterval(pollHandle); pollHandle = null; }
    } catch (err) {
      console.warn('webinar-report fetch failed:', err);
    }
  }

  // ─── Init ─────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    const exportBtn = document.getElementById('webinar-export-csv');
    if (exportBtn) exportBtn.addEventListener('click', exportCSV);

    loadWebinarData();
    pollHandle = setInterval(loadWebinarData, POLL_EVERY_MS);
    setTimeout(() => {
      if (pollHandle) { clearInterval(pollHandle); pollHandle = null; }
    }, GIVE_UP_AFTER_MS);
  });
})();
