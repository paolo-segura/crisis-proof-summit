/**
 * admin-sales.js
 * Populates the Sales & UTM Attribution section of admin.html.
 * Depends on: admin.js defining window.apiFetch (existing).
 */

(function () {
  'use strict';

  var revenueChart = null;
  var ticketsChart = null;
  var conversionChart = null;

  // Storage values from DB → human-readable display labels
  var TIER_LABELS = { early_bird: 'Early Bird', regular: 'Regular', vip: 'VIP', other: 'Other' };

  function tierLabel(t) { return TIER_LABELS[t] || (t ? String(t) : ''); }

  function peso(n) {
    return '₱' + Number(n || 0).toLocaleString('en-PH', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  }

  function ago(iso) {
    if (!iso) return '—';
    var diffMs = Date.now() - new Date(iso).getTime();
    var diffMin = Math.round(diffMs / 60000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return diffMin + 'm ago';
    var diffHr = Math.round(diffMin / 60);
    if (diffHr < 24) return diffHr + 'h ago';
    return Math.round(diffHr / 24) + 'd ago';
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  async function loadSyncStatus() {
    var dot = document.getElementById('sync-dot');
    var label = document.getElementById('sync-label');
    if (!dot || !label) return;
    try {
      var log = await window.apiFetch('last_sync');
      if (!log) {
        dot.className = 'dot err'; label.textContent = 'No syncs yet';
        return;
      }
      dot.className = 'dot ' + (log.success ? 'ok' : 'err');
      label.textContent = 'Last sync: ' + ago(log.started_at)
        + ' • ' + (log.rows_upserted || 0) + ' payments';
    } catch (err) {
      dot.className = 'dot err';
      label.textContent = 'Sync status unavailable';
    }
  }

  async function loadKPIs() {
    var summary = await window.apiFetch('summary');
    var revEl = document.getElementById('kpi-revenue');
    var tixEl = document.getElementById('kpi-tickets');
    var convEl = document.getElementById('kpi-conv');
    if (revEl) revEl.textContent = peso(summary.total_revenue);
    if (tixEl) tixEl.textContent = Number(summary.total_sales || 0).toLocaleString();
    if (convEl) convEl.textContent = (summary.conversion_rate || 0) + '%';

    var recent = await window.apiFetch('recent_payments');
    var unmatched = (recent || []).filter(function (r) { return r.match_method === 'direct'; }).length;
    var unEl = document.getElementById('kpi-unmatched');
    if (unEl) unEl.textContent = unmatched;

    return recent || [];
  }

  async function drawRevenueChart() {
    var data = await window.apiFetch('revenue_by_utm');
    var canvas = document.getElementById('chart-revenue-utm');
    if (!canvas) return;
    if (!Array.isArray(data) || data.length === 0) {
      if (revenueChart) { revenueChart.destroy(); revenueChart = null; }
      var ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#9ca3af';
      ctx.font = '13px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No data yet', canvas.width / 2, canvas.height / 2);
      return;
    }
    var ctx = canvas.getContext('2d');
    var labels = data.map(function (r) { return r.utm_source; });
    var values = data.map(function (r) { return r.revenue; });
    if (revenueChart) revenueChart.destroy();
    revenueChart = new Chart(ctx, {
      type: 'bar',
      data: { labels: labels, datasets: [{ label: 'Revenue (₱)', data: values, backgroundColor: '#0d9488' }] },
      options: {
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: function (c) { return peso(c.parsed.x); } } }
        },
        scales: { x: { ticks: { callback: function (v) { return peso(v); } } } }
      }
    });
  }

  async function drawTicketsChart() {
    var data = await window.apiFetch('tickets_by_utm_tier');
    var canvas = document.getElementById('chart-tickets-utm-tier');
    if (!canvas) return;
    if (!Array.isArray(data) || data.length === 0) {
      if (ticketsChart) { ticketsChart.destroy(); ticketsChart = null; }
      var ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#9ca3af';
      ctx.font = '13px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No data yet', canvas.width / 2, canvas.height / 2);
      return;
    }
    var ctx = canvas.getContext('2d');
    var labels = data.map(function (r) { return r.utm_source; });
    if (ticketsChart) ticketsChart.destroy();
    ticketsChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          { label: 'Early Bird', data: data.map(function (r) { return r.early_bird; }), backgroundColor: '#f59e0b' },
          { label: 'Regular',    data: data.map(function (r) { return r.regular; }),    backgroundColor: '#0d9488' },
          { label: 'VIP',        data: data.map(function (r) { return r.vip; }),        backgroundColor: '#7c3aed' },
          { label: 'Other',      data: data.map(function (r) { return r.other; }),      backgroundColor: '#9ca3af' }
        ]
      },
      options: {
        responsive: true,
        scales: { x: { stacked: true }, y: { stacked: true, ticks: { precision: 0 } } }
      }
    });
  }

  async function drawConversionChart() {
    var data = await window.apiFetch('conversion_by_utm');
    var canvas = document.getElementById('chart-conversion-utm');
    if (!canvas) return;
    if (!Array.isArray(data) || data.length === 0) {
      if (conversionChart) { conversionChart.destroy(); conversionChart = null; }
      var ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#9ca3af';
      ctx.font = '13px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No data yet', canvas.width / 2, canvas.height / 2);
      return;
    }
    var ctx = canvas.getContext('2d');
    var labels = data.map(function (r) { return r.utm_source; });
    if (conversionChart) conversionChart.destroy();
    conversionChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          { label: 'Visits',      data: data.map(function (r) { return r.visits; }),       backgroundColor: '#cbd5e1' },
          { label: 'Filled form', data: data.map(function (r) { return r.participants; }), backgroundColor: '#94a3b8' },
          { label: 'Paid',        data: data.map(function (r) { return r.paid; }),         backgroundColor: '#0d9488' }
        ]
      },
      options: { responsive: true, scales: { y: { ticks: { precision: 0 } } } }
    });
  }

  function renderPaymentsTable(rows) {
    var tbody = document.querySelector('#table-recent-payments tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!rows || rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#9ca3af;padding:24px;">No payments yet — waiting for the next sync.</td></tr>';
      return;
    }
    rows.forEach(function (r) {
      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + (r.paid_at ? new Date(r.paid_at).toLocaleString('en-PH') : '') + '</td>' +
        '<td>' + escapeHtml(r.full_name) + '</td>' +
        '<td>' + escapeHtml(r.email) + '</td>' +
        '<td>' + escapeHtml(tierLabel(r.ticket_tier)) + '</td>' +
        '<td>' + peso(r.amount) + '</td>' +
        '<td>' + escapeHtml(r.utm_source || 'direct') + '</td>' +
        '<td>' + escapeHtml(r.match_method) + '</td>' +
        '<td>' + escapeHtml(r.payment_status) + '</td>';
      tbody.appendChild(tr);
    });
  }

  async function loadParticipants() {
    try {
      return await window.apiFetch('recent_participants') || [];
    } catch (err) {
      console.error('[admin-sales] participants fetch failed', err);
      return [];
    }
  }

  async function downloadParticipantsCSV() {
    var btn = document.getElementById('btn-download-participants');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Preparing…'; }
    try {
      var rows = await window.apiFetch('all_participants') || [];
      var headers = ['When', 'Name', 'Email', 'Mobile', 'Role', 'Business Type', 'Referred By', 'UTM Source', 'UTM Medium', 'UTM Campaign', 'UTM Content'];
      var csvLines = [headers.join(',')];
      rows.forEach(function (r) {
        var line = [
          r.created_at || '',
          r.full_name || '',
          r.email || '',
          r.mobile_number || '',
          r.describes_you || '',
          r.business_type || '',
          r.referred_by || '',
          r.utm_source || '',
          r.utm_medium || '',
          r.utm_campaign || '',
          r.utm_content || ''
        ].map(csvEscape).join(',');
        csvLines.push(line);
      });
      var csv = csvLines.join('\n');
      var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      var date = new Date().toISOString().slice(0, 10);
      var filename = 'business-unlocked-participants-' + date + '.csv';
      var link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      alert('CSV download failed: ' + (err && err.message ? err.message : err));
      console.error('[admin-sales] csv download failed', err);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '📊 Download CSV (all)'; }
    }
  }

  function csvEscape(val) {
    var s = String(val == null ? '' : val);
    if (s.indexOf(',') >= 0 || s.indexOf('"') >= 0 || s.indexOf('\n') >= 0) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  function renderParticipantsTable(rows) {
    var tbody = document.querySelector('#table-recent-participants tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!rows || rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#9ca3af;padding:24px;">No participant submissions yet.</td></tr>';
      return;
    }
    rows.forEach(function (r) {
      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + (r.created_at ? new Date(r.created_at).toLocaleString('en-PH') : '') + '</td>' +
        '<td>' + escapeHtml(r.full_name) + '</td>' +
        '<td>' + escapeHtml(r.email) + '</td>' +
        '<td>' + escapeHtml(r.mobile_number) + '</td>' +
        '<td>' + escapeHtml(r.describes_you) + '</td>' +
        '<td>' + escapeHtml(r.business_type) + '</td>' +
        '<td>' + escapeHtml(r.referred_by) + '</td>';
      tbody.appendChild(tr);
    });
  }

  async function loadAll() {
    var dl = document.getElementById('btn-download-participants');
    if (dl) dl.addEventListener('click', downloadParticipantsCSV);
    try {
      await loadSyncStatus();
      var recent = await loadKPIs();
      renderPaymentsTable(recent);
      var participants = await loadParticipants();
      renderParticipantsTable(participants);
      await drawRevenueChart();
      await drawTicketsChart();
      await drawConversionChart();
    } catch (err) {
      console.error('[admin-sales] load failed', err);
    }
  }

  // Run after admin.js authenticates (it dispatches 'admin:authed' on success).
  // Fallback: also try after DOMContentLoaded + 3s in case admin.js doesn't fire it.
  var ran = false;
  function runOnce() {
    if (!ran && window.adminAuthed) {
      ran = true;
      loadAll();
    }
  }

  window.addEventListener('admin:authed', runOnce);
  window.addEventListener('DOMContentLoaded', function () { setTimeout(runOnce, 3000); });
})();
