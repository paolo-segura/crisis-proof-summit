/* /admin/coupons — manage the bu_coupons table.
   Auth: same ADMIN_PASSWORD bearer as /admin (sessionStorage admin_pw).
   Endpoints: GET / POST / PATCH /api/coupons. Server is the source of truth;
   anything submitted here is re-validated server-side. */
(function () {
  'use strict';

  var ENDPOINT = '/api/coupons';

  // ─── State ─────────────────────────────────────────────────────────────────
  var password = '';

  // ─── DOM ───────────────────────────────────────────────────────────────────
  var loginScreen   = document.getElementById('login-screen');
  var dashboard     = document.getElementById('dashboard');
  var passwordInput = document.getElementById('password-input');
  var loginBtn      = document.getElementById('login-btn');
  var loginError    = document.getElementById('login-error');
  var addForm       = document.getElementById('add-form');
  var addBtn        = document.getElementById('add-btn');
  var formMsg       = document.getElementById('form-msg');
  var couponsBody   = document.getElementById('coupons-body');

  // ─── Helpers ───────────────────────────────────────────────────────────────
  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }
  function peso(n) {
    if (n == null || isNaN(n)) return '₱0';
    return '₱' + Number(n).toLocaleString('en-PH', { maximumFractionDigits: 0 });
  }
  function formatDate(s) {
    if (!s) return '';
    var d = new Date(s);
    if (isNaN(d.getTime())) return s;
    return d.toLocaleDateString('en-PH', { month: 'short', day: 'numeric', year: 'numeric' });
  }
  function tierLabel(t) {
    return ({ early_bird: 'Early Bird', regular: 'Regular', vip: 'VIP' })[t] || t;
  }

  function setFormMsg(msg, kind) {
    formMsg.textContent = msg || '';
    formMsg.className = 'form-msg' + (kind ? ' ' + kind : '');
  }

  function authHeaders(extra) {
    var h = { 'Authorization': 'Bearer ' + password };
    if (extra) Object.keys(extra).forEach(function (k) { h[k] = extra[k]; });
    return h;
  }

  // ─── Auth flow (mirrors /admin) ────────────────────────────────────────────
  function showDashboard() {
    loginScreen.style.display = 'none';
    dashboard.style.display = 'block';
    loadList();
  }

  function attemptLogin(pw) {
    return fetch(ENDPOINT, { headers: { 'Authorization': 'Bearer ' + pw } })
      .then(function (res) {
        // 200 = success (lists coupons), 401 = bad password, anything else = treat
        // as "auth not the problem" so we can surface a server error if needed.
        if (res.ok) return true;
        if (res.status === 401) return false;
        // Non-401 errors shouldn't gate login — let it through and the list
        // section will show the actual error.
        return true;
      })
      .catch(function () { return false; });
  }

  function handleLogin() {
    var pw = (passwordInput.value || '').trim();
    if (!pw) return;
    loginBtn.disabled = true;
    loginBtn.textContent = 'Logging in…';
    loginError.style.display = 'none';

    attemptLogin(pw).then(function (ok) {
      if (ok) {
        password = pw;
        try { sessionStorage.setItem('admin_pw', pw); } catch (_) {}
        showDashboard();
      } else {
        loginError.style.display = 'block';
        loginBtn.disabled = false;
        loginBtn.textContent = 'Log In';
        passwordInput.focus();
      }
    });
  }

  loginBtn.addEventListener('click', handleLogin);
  passwordInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') handleLogin();
  });

  // Auto-resume if /admin already logged in this session
  try {
    var stashed = sessionStorage.getItem('admin_pw');
    if (stashed) {
      password = stashed;
      // Validate the stashed pw actually works before unhiding the dashboard
      attemptLogin(stashed).then(function (ok) {
        if (ok) showDashboard();
      });
    }
  } catch (_) {}

  // ─── List + render ─────────────────────────────────────────────────────────
  function renderList(rows) {
    if (!rows || rows.length === 0) {
      couponsBody.innerHTML = '<tr><td colspan="8" class="empty-state">No coupons yet. Add one above.</td></tr>';
      return;
    }
    var html = '';
    rows.forEach(function (r) {
      var statusPill = r.active
        ? '<span class="pill pill-active">ACTIVE</span>'
        : '<span class="pill pill-inactive">OFF</span>';
      var toggleLabel = r.active ? 'Disable' : 'Enable';
      html += '<tr>'
        + '<td class="code-cell">' + escapeHtml(r.code) + '</td>'
        + '<td>' + escapeHtml(tierLabel(r.base_tier)) + '</td>'
        + '<td class="amount-cell">' + peso(r.amount) + '</td>'
        + '<td>' + escapeHtml(r.label) + '</td>'
        + '<td>' + statusPill + '</td>'
        + '<td>' + escapeHtml(formatDate(r.created_at)) + '</td>'
        + '<td>' + escapeHtml(r.created_by || '—') + '</td>'
        + '<td><button class="row-toggle" data-code="' + escapeHtml(r.code) + '" data-active="' + (!r.active) + '">'
        + toggleLabel + '</button></td>'
        + '</tr>';
    });
    couponsBody.innerHTML = html;
    Array.prototype.forEach.call(
      couponsBody.querySelectorAll('.row-toggle'),
      function (btn) {
        btn.addEventListener('click', function () {
          var code = btn.dataset.code;
          var nextActive = btn.dataset.active === 'true';
          toggleActive(code, nextActive, btn);
        });
      }
    );
  }

  function loadList() {
    couponsBody.innerHTML = '<tr><td colspan="8" class="empty-state">Loading…</td></tr>';
    fetch(ENDPOINT, { headers: authHeaders() })
      .then(function (res) { return res.json().then(function (b) { return { ok: res.ok, body: b }; }); })
      .then(function (r) {
        if (!r.ok) {
          couponsBody.innerHTML = '<tr><td colspan="8" class="empty-state" style="color:var(--error)">'
            + escapeHtml((r.body && r.body.error) || 'Failed to load coupons.')
            + '</td></tr>';
          return;
        }
        renderList(Array.isArray(r.body) ? r.body : []);
      })
      .catch(function () {
        couponsBody.innerHTML = '<tr><td colspan="8" class="empty-state" style="color:var(--error)">Network error. Refresh and try again.</td></tr>';
      });
  }

  // ─── Create ────────────────────────────────────────────────────────────────
  addForm.addEventListener('submit', function (e) {
    e.preventDefault();
    setFormMsg('', '');
    var data = new FormData(addForm);
    var payload = {
      code: (data.get('code') || '').toString().trim().toUpperCase(),
      base_tier: (data.get('base_tier') || '').toString(),
      amount: Number(data.get('amount')),
      label: (data.get('label') || '').toString().trim(),
      created_by: (data.get('created_by') || '').toString().trim() || null
    };
    if (!payload.code || !payload.base_tier || !payload.amount || !payload.label) {
      setFormMsg('Fill in code, tier, price, and label.', 'err');
      return;
    }
    addBtn.disabled = true;
    addBtn.textContent = 'Saving…';
    fetch(ENDPOINT, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    })
      .then(function (res) { return res.json().then(function (b) { return { ok: res.ok, status: res.status, body: b }; }); })
      .then(function (r) {
        if (!r.ok) {
          setFormMsg((r.body && r.body.error) || 'Could not save (HTTP ' + r.status + ').', 'err');
          return;
        }
        setFormMsg('✓ ' + payload.code + ' added.', 'ok');
        addForm.reset();
        loadList();
      })
      .catch(function () {
        setFormMsg('Network error. Try again.', 'err');
      })
      .then(function () {
        addBtn.disabled = false;
        addBtn.textContent = 'Add Coupon';
      });
  });

  // ─── Toggle active ─────────────────────────────────────────────────────────
  function toggleActive(code, nextActive, btn) {
    btn.disabled = true;
    var prev = btn.textContent;
    btn.textContent = '…';
    fetch(ENDPOINT + '?code=' + encodeURIComponent(code), {
      method: 'PATCH',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ active: nextActive })
    })
      .then(function (res) { return res.json().then(function (b) { return { ok: res.ok, body: b }; }); })
      .then(function (r) {
        if (!r.ok) {
          btn.textContent = prev;
          btn.disabled = false;
          alert((r.body && r.body.error) || 'Failed to update. Try again.');
          return;
        }
        loadList();
      })
      .catch(function () {
        btn.textContent = prev;
        btn.disabled = false;
        alert('Network error. Try again.');
      });
  }
})();
