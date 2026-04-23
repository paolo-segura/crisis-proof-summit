/* Inline Xendit checkout — sits in #pricing, below the 2 pricing cards.
   Flow:
     tier + details + payment method → POST /api/create-invoice
     → get invoice_url → redirect browser to Xendit's hosted page.
   Keeps UTM + session_id from utm.js (localStorage).
   Fires Meta Pixel InitiateCheckout on submit; Purchase event fires on
   /thank-you when the user returns from Xendit. */
(function () {
  'use strict';

  var form = document.getElementById('inline-checkout-form');
  if (!form) return;

  // Keep in sync with api/create-invoice.py TIERS. Zoom tiers mirror the
  // in-person price; the UI derives _zoom suffix from the access_mode radio.
  var PRICES = {
    early_bird: 1999, regular: 2500, vip: 5000,
    early_bird_zoom: 1999, regular_zoom: 2500
  };
  var CATEGORY_LABELS = { ewallet: 'e-wallet', card: 'card', qr: 'QR Ph' };
  var EMAIL_PATTERN = /^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$/;
  var TABLE_CLICKS = 'new_business_normal_clicks';  // same table main.js uses

  var qty = 1;

  function $(id) { return document.getElementById(id); }
  function fmt(n) { return '₱' + Number(n).toLocaleString('en-PH'); }

  function currentAccessMode() {
    var r = form.querySelector('input[name="access_mode"]:checked');
    return r ? r.value : 'in_person';
  }

  // Derived tier = base radio value + _zoom suffix when access_mode=zoom,
  // except for VIP which is in-person-only. Sent to /api/create-invoice.
  function currentTier() {
    var r = form.querySelector('input[name="tier"]:checked');
    var base = r ? r.value : 'early_bird';
    if (base === 'vip') return 'vip';
    if (currentAccessMode() === 'zoom' && (base === 'early_bird' || base === 'regular')) {
      return base + '_zoom';
    }
    return base;
  }

  function currentMethod() {
    var r = form.querySelector('input[name="preferred_method"]:checked');
    return r ? r.value : '';
  }

  function currentCategory() {
    var t = form.querySelector('.ic-pm-tab.active');
    return t ? t.dataset.cat : 'ewallet';
  }

  function getTracking() {
    var t = window.NBN_TRACKING || {};
    return {
      sessionId: t.getSessionId ? t.getSessionId() : '',
      utm: t.getUTMParams ? t.getUTMParams() : {}
    };
  }

  function updateTotal() {
    var total = PRICES[currentTier()] * qty;
    var tv = $('ic-total-val');
    var qv = $('ic-qty-val');
    var qi = $('ic-qty-input');
    if (tv) tv.textContent = fmt(total);
    if (qv) qv.textContent = qty;
    if (qi) qi.value = String(qty);
  }

  // ---- tier changes ----
  form.querySelectorAll('input[name="tier"]').forEach(function (r) {
    r.addEventListener('change', updateTotal);
  });

  // ---- access mode (In-Person / Zoom) ----
  // Zoom hides/disables VIP since VIP is in-person-only. If VIP was selected
  // when user switches to Zoom, fall back to Early Bird so we never submit an
  // impossible combo.
  function applyAccessMode() {
    var mode = currentAccessMode();
    // Toggle `.active` class on the labels for styling
    form.querySelectorAll('.ic-access-mode-option').forEach(function (lbl) {
      var inp = lbl.querySelector('input[name="access_mode"]');
      lbl.classList.toggle('active', !!(inp && inp.checked));
    });
    var vipTile = form.querySelector('[data-vip-tile]');
    var vipNote = form.querySelector('[data-vip-note]');
    var vipRadio = form.querySelector('input[name="tier"][value="vip"]');
    var ebRadio = form.querySelector('input[name="tier"][value="early_bird"]');
    if (mode === 'zoom') {
      if (vipTile) vipTile.classList.add('disabled');
      if (vipNote) vipNote.hidden = false;
      if (vipRadio) vipRadio.disabled = true;
      if (vipRadio && vipRadio.checked && ebRadio) {
        ebRadio.checked = true;
      }
    } else {
      if (vipTile) vipTile.classList.remove('disabled');
      if (vipNote) vipNote.hidden = true;
      if (vipRadio) vipRadio.disabled = false;
    }
    updateTotal();
  }
  form.querySelectorAll('input[name="access_mode"]').forEach(function (r) {
    r.addEventListener('change', applyAccessMode);
  });

  // ---- quantity stepper ----
  form.querySelectorAll('.ic-qty-btn').forEach(function (b) {
    b.addEventListener('click', function () {
      qty = Math.max(1, Math.min(10, qty + (b.dataset.op === '+' ? 1 : -1)));
      updateTotal();
    });
  });

  // ---- payment method tab switching ----
  function setCategory(cat) {
    form.querySelectorAll('.ic-pm-tab').forEach(function (t) {
      t.classList.toggle('active', t.dataset.cat === cat);
    });
    form.querySelectorAll('.ic-pm-list').forEach(function (list) {
      list.hidden = list.dataset.group !== cat;
    });
    form.querySelectorAll('input[name="preferred_method"]').forEach(function (r) { r.checked = false; });
    refreshStatus(cat);
  }
  form.querySelectorAll('.ic-pm-tab').forEach(function (t) {
    t.addEventListener('click', function () { setCategory(t.dataset.cat); });
  });

  function refreshStatus(cat) {
    var picked = form.querySelector('input[name="preferred_method"]:checked');
    var status = $('ic-pm-status');
    var text = $('ic-pm-status-text');
    var btn = $('ic-btn-pay');
    if (!status || !text || !btn) return;
    if (picked) {
      status.classList.add('ready');
      var name = picked.parentElement.querySelector('.ic-pm-row-name').textContent;
      text.textContent = name + ' is ready to use!';
      btn.disabled = false;
    } else {
      status.classList.remove('ready');
      text.textContent = 'Waiting for ' + (CATEGORY_LABELS[cat] || 'payment') + ' selection...';
      btn.disabled = true;
    }
  }
  form.addEventListener('change', function (e) {
    if (e.target && e.target.name === 'preferred_method') {
      refreshStatus(currentCategory());
    }
  });

  // ---- validation + submit ----
  function showError(msg) {
    var box = $('ic-error');
    if (!box) return;
    box.textContent = msg;
    box.hidden = false;
    box.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  function hideError() { var box = $('ic-error'); if (box) box.hidden = true; }

  function setSubmitting(on) {
    var btn = $('ic-btn-pay');
    if (!btn) return;
    btn.disabled = on;
    var label = btn.querySelector('.ic-btn-label');
    var spin = btn.querySelector('.ic-btn-spinner');
    if (label) label.style.display = on ? 'none' : '';
    if (spin) spin.hidden = !on;
  }

  function logClick(tier) {
    if (typeof supabase === 'undefined' || !supabase) return;
    var t = getTracking();
    supabase.from(TABLE_CLICKS).insert({
      session_id: t.sessionId || null,
      ticket_tier: tier,
      utm_source: t.utm.utm_source,
      utm_medium: t.utm.utm_medium,
      utm_campaign: t.utm.utm_campaign,
      utm_content: t.utm.utm_content,
      utm_term: t.utm.utm_term
    }).then(function (res) {
      if (res && res.error) console.warn('Click log failed:', res.error.message);
    });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    hideError();

    // Honeypot — silently drop bot submissions
    var hp = form.querySelector('input[name="website"]');
    if (hp && hp.value) { console.warn('Honeypot triggered'); return; }

    var tier = currentTier();
    var fullName = (form.querySelector('input[name="full_name"]').value || '').trim();
    var email = (form.querySelector('input[name="email"]').value || '').trim().toLowerCase();
    var mobile = (form.querySelector('input[name="mobile_number"]').value || '').trim();
    var method = currentMethod();

    if (!fullName || fullName.length < 2) return showError('Please enter your full name.');
    if (!email || !EMAIL_PATTERN.test(email)) return showError('Please enter a valid email address.');
    if (mobile.replace(/\D/g, '').length < 10) return showError('Please enter a valid mobile number.');
    if (!method) return showError('Please choose a payment method.');

    var t = getTracking();
    var payload = {
      full_name: fullName,
      email: email,
      mobile_number: mobile,
      tier: tier,
      quantity: qty,
      preferred_method: method,
      session_id: t.sessionId,
      utm_source: t.utm.utm_source,
      utm_medium: t.utm.utm_medium,
      utm_campaign: t.utm.utm_campaign,
      utm_content: t.utm.utm_content,
      utm_term: t.utm.utm_term
    };

    setSubmitting(true);
    logClick(tier);

    // Fire InitiateCheckout BEFORE redirect so the navigation doesn't race it
    if (typeof fbq === 'function') {
      try {
        fbq('track', 'InitiateCheckout', {
          content_name: 'Business Unlocked Ticket',
          content_category: 'event',
          content_ids: [tier],
          num_items: qty,
          value: PRICES[tier] * qty,
          currency: 'PHP'
        });
      } catch (_) { /* non-fatal */ }
    }

    fetch('/api/create-invoice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (res) { return res.json().then(function (b) { return { ok: res.ok, body: b }; }); })
      .then(function (r) {
        if (!r.ok || !r.body || !r.body.invoice_url) {
          showError((r.body && r.body.error) || 'Could not reach the payment service. Please try again.');
          setSubmitting(false);
          return;
        }
        // Redirect to Xendit. replace() so back-button doesn't re-POST.
        window.location.replace(r.body.invoice_url);
      })
      .catch(function (err) {
        console.error('create-invoice error:', err);
        showError('Network error. Please check your connection and try again.');
        setSubmitting(false);
      });
  });

  // ---- ticket-button hook: when user clicks "Unlock Now" / "Go VIP" on the
  // existing pricing cards, preselect the tier in our form and scroll to it.
  // Uses capture phase to run BEFORE main.js's old iframe handler, then stops
  // propagation so the iframe doesn't open.
  document.querySelectorAll('.ticket-btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      var tier = btn.dataset.tier || 'early_bird';
      e.preventDefault();
      e.stopImmediatePropagation();
      var radio = form.querySelector('input[name="tier"][value="' + tier + '"]')
                || form.querySelector('input[name="tier"][value="regular"]');
      if (radio) { radio.checked = true; updateTotal(); }
      var top = form.getBoundingClientRect().top + window.scrollY - 80;
      window.scrollTo({ top: top, behavior: 'smooth' });
      // Briefly focus the name input to nudge the user into the flow
      setTimeout(function () {
        var nameEl = form.querySelector('input[name="full_name"]');
        if (nameEl) nameEl.focus({ preventScroll: true });
      }, 700);
    }, true); // capture = beats main.js's bubble-phase handler
  });

  // ---- /thank-you redirect may come back with ?checkout=failed — banner ---
  var qs = new URLSearchParams(window.location.search);
  if (qs.get('checkout') === 'failed') {
    showError('Your previous payment was not completed. No worries — try again below.');
  }

  // ---- initial paint ----
  applyAccessMode();
  updateTotal();
  refreshStatus('ewallet');
})();
