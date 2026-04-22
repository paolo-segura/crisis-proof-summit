/* =============================================================
   /checkout — native one-page Xendit flow
   -----------------------------------------------------------------
   Responsibilities:
     1. Preselect tier from ?tier= query param
     2. Keep order summary + left-rail price synced with tier selection
     3. Log a click to Supabase (same semantics as legacy iframe path)
     4. POST the form to /api/create-invoice, then redirect browser
        to the Xendit invoice_url
     5. Fire Meta Pixel InitiateCheckout so Advantage+ can optimise
   ============================================================= */

(function () {
  'use strict';

  // Must match api/create-invoice.py TIERS
  var TIER_LABELS = {
    early_bird: { label: 'Early Bird', price: 1999 },
    regular:    { label: 'Regular',    price: 2500 },
    vip:        { label: 'VIP',        price: 5000 }
  };

  var TABLE_CLICKS = 'new_business_normal_clicks';  // matches main.js

  // ---- utilities ----

  function $(id) { return document.getElementById(id); }

  function formatPHP(amount) {
    return '₱' + Number(amount).toLocaleString('en-PH', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  function formatPHPCompact(amount) {
    return '₱' + Number(amount).toLocaleString('en-PH');
  }

  function readTierFromURL() {
    var params = new URLSearchParams(window.location.search);
    var raw = (params.get('tier') || '').toLowerCase().replace(/-/g, '_');
    return TIER_LABELS[raw] ? raw : 'early_bird';
  }

  function readFailedFlag() {
    return new URLSearchParams(window.location.search).get('failed') === '1';
  }

  function getTracking() {
    var t = window.NBN_TRACKING || {};
    return {
      sessionId: t.getSessionId ? t.getSessionId() : '',
      utm: t.getUTMParams ? t.getUTMParams() : {}
    };
  }

  // ---- UI sync (tier → price/summary) ----

  function applyTier(tier) {
    var cfg = TIER_LABELS[tier] || TIER_LABELS.early_bird;

    // Radio state
    var radio = document.querySelector('input[name="tier"][value="' + tier + '"]');
    if (radio) radio.checked = true;

    // Left-rail price
    var leftPrice = $('summary-price');
    var leftTier = $('summary-price-tier');
    if (leftPrice) leftPrice.textContent = formatPHPCompact(cfg.price);
    if (leftTier) leftTier.textContent = cfg.label + ' — Full Payment';

    // Order summary
    var itemEl = $('order-summary-item');
    var amtEl = $('order-summary-amount');
    var totalEl = $('order-summary-total-amount');
    if (itemEl) itemEl.textContent = 'Business Unlocked (Manila) — ' + cfg.label;
    if (amtEl) amtEl.textContent = formatPHP(cfg.price);
    if (totalEl) totalEl.textContent = formatPHP(cfg.price);
  }

  // ---- click logging (drop-in from main.js) ----

  function logClick(tier) {
    if (typeof supabase === 'undefined' || !supabase) return;
    var t = getTracking();
    supabase
      .from(TABLE_CLICKS)
      .insert({
        session_id: t.sessionId || null,
        ticket_tier: tier,
        utm_source:   t.utm.utm_source,
        utm_medium:   t.utm.utm_medium,
        utm_campaign: t.utm.utm_campaign,
        utm_content:  t.utm.utm_content,
        utm_term:     t.utm.utm_term
      })
      .then(function (res) {
        if (res && res.error) console.warn('Click log failed:', res.error.message);
      });
  }

  // ---- validation ----

  var EMAIL_PATTERN = /^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$/;

  function validate(payload) {
    if (!payload.full_name || payload.full_name.length < 2)   return 'Please enter your full name.';
    if (!payload.email || !EMAIL_PATTERN.test(payload.email)) return 'Please enter a valid email address.';
    var digits = (payload.mobile_number || '').replace(/\D/g, '');
    if (digits.length < 10) return 'Please enter a valid mobile number.';
    if (!TIER_LABELS[payload.tier]) return 'Please select a ticket.';
    return null;
  }

  // ---- submit handler ----

  function showError(msg) {
    var box = $('checkout-error');
    if (!box) return;
    box.textContent = msg;
    box.hidden = false;
    box.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  function hideError() {
    var box = $('checkout-error');
    if (box) box.hidden = true;
  }

  function setSubmitting(isSubmitting) {
    var btn = $('checkout-submit');
    if (!btn) return;
    btn.disabled = isSubmitting;
    var spinner = btn.querySelector('.submit-spinner');
    var label = btn.querySelector('.submit-label');
    if (spinner) spinner.hidden = !isSubmitting;
    if (label) label.textContent = isSubmitting ? 'Redirecting to secure payment…' : 'Complete Order';
  }

  function handleSubmit(e) {
    e.preventDefault();
    hideError();

    var form = e.target;
    var tier = (form.tier && form.tier.value) || 'early_bird';
    var method = (form.preferred_method && form.preferred_method.value) || '';

    // Honeypot — silently ignore bots
    if (form.website && form.website.value) {
      console.warn('Honeypot triggered, dropping submission');
      return;
    }

    var t = getTracking();
    var payload = {
      full_name:     (form.full_name.value || '').trim(),
      email:         (form.email.value || '').trim().toLowerCase(),
      mobile_number: (form.mobile_number.value || '').trim(),
      tier:          tier,
      preferred_method: method || null,
      session_id:    t.sessionId,
      utm_source:    t.utm.utm_source,
      utm_medium:    t.utm.utm_medium,
      utm_campaign:  t.utm.utm_campaign,
      utm_content:   t.utm.utm_content,
      utm_term:      t.utm.utm_term
    };

    var err = validate(payload);
    if (err) { showError(err); return; }

    setSubmitting(true);
    logClick(tier);

    // Meta Pixel — fire InitiateCheckout BEFORE redirect so it doesn't race
    // the navigation. Advantage+ uses this event for mid-funnel optimisation.
    if (typeof fbq === 'function') {
      var price = TIER_LABELS[tier].price;
      try {
        fbq('track', 'InitiateCheckout', {
          content_name: 'Business Unlocked Ticket',
          content_category: 'event',
          content_ids: [tier],
          value: price,
          currency: 'PHP'
        });
      } catch (err) { console.warn('Pixel InitiateCheckout failed:', err); }
    }

    fetch('/api/create-invoice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (res) {
        return res.json().then(function (body) { return { ok: res.ok, status: res.status, body: body }; });
      })
      .then(function (r) {
        if (!r.ok || !r.body || !r.body.invoice_url) {
          var msg = (r.body && r.body.error) ? r.body.error
            : 'Could not reach the payment service. Please try again in a moment.';
          showError(msg);
          setSubmitting(false);
          return;
        }
        // Redirect the browser to Xendit's hosted invoice page.
        // Use replace so back-button doesn't re-POST the form.
        window.location.replace(r.body.invoice_url);
      })
      .catch(function (err) {
        console.error('create-invoice error:', err);
        showError('Network error. Please check your connection and try again.');
        setSubmitting(false);
      });
  }

  // ---- init ----

  document.addEventListener('DOMContentLoaded', function () {
    // Failure banner if Xendit sent us back after a failed payment
    if (readFailedFlag()) {
      var banner = $('checkout-failed-banner');
      if (banner) banner.hidden = false;
    }

    // Preselect tier from URL
    var startTier = readTierFromURL();
    applyTier(startTier);

    // Wire tier change handler
    document.querySelectorAll('input[name="tier"]').forEach(function (radio) {
      radio.addEventListener('change', function () {
        if (radio.checked) applyTier(radio.value);
      });
    });

    // Wire submit
    var form = $('checkout-form');
    if (form) form.addEventListener('submit', handleSubmit);
  });
})();
