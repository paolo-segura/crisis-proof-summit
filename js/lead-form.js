/**
 * Business Unlocked — Lead Acquisition Form
 * Handles the lead form on /business-unlocked, POSTs to /api/register-lead,
 * redirects to /business-unlocked/thank-you on success.
 */
(function () {
  'use strict';

  var form = document.getElementById('lead-form');
  if (!form) return;

  var submitBtn = document.getElementById('lead-submit-btn');
  var errorEl = document.getElementById('lead-error');

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.hidden = false;
    errorEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function clearError() {
    errorEl.textContent = '';
    errorEl.hidden = true;
  }

  function setLoading(loading) {
    submitBtn.disabled = loading;
    submitBtn.textContent = loading
      ? 'Sending...'
      : 'Inquire Now →';
  }

  // Collect UTM params from the current URL
  function getUTMs() {
    var params = new URLSearchParams(window.location.search);
    return {
      utm_source: params.get('utm_source') || '',
      utm_medium: params.get('utm_medium') || '',
      utm_campaign: params.get('utm_campaign') || '',
      utm_content: params.get('utm_content') || '',
      utm_term: params.get('utm_term') || '',
    };
  }

  // Simple session ID — reuse from sessionStorage or generate fresh
  function getSessionId() {
    var key = 'bu_session_id';
    var existing = sessionStorage.getItem(key);
    if (existing) return existing;
    var id = 'sess_' + Math.random().toString(36).slice(2) + '_' + Date.now();
    try { sessionStorage.setItem(key, id); } catch (_) {}
    return id;
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearError();

    var data = new FormData(form);
    var fullName = (data.get('full_name') || '').trim();
    var email = (data.get('email') || '').trim();
    var mobile = (data.get('mobile_number') || '').trim();
    var bestTime = (data.get('best_time_to_call') || '').trim();
    var honeypot = (data.get('website') || '').trim();

    // Client-side validation
    if (!fullName || fullName.length < 2) {
      return showError('Please enter your full name.');
    }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return showError('Please enter a valid email address.');
    }
    if (!mobile || mobile.replace(/\D/g, '').length < 7) {
      return showError('Please enter a valid mobile number.');
    }

    setLoading(true);

    var payload = Object.assign(
      {
        full_name: fullName,
        email: email.toLowerCase(),
        mobile_number: mobile,
        best_time_to_call: bestTime,
        website: honeypot, // honeypot — server ignores if non-empty
        session_id: getSessionId(),
      },
      getUTMs()
    );

    fetch('/api/register-lead', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        return res.json().then(function (json) {
          return { status: res.status, body: json };
        });
      })
      .then(function (result) {
        if (result.body && result.body.ok) {
          // Fire pixel event before redirect
          if (typeof fbq === 'function') {
            fbq('track', 'Lead', { content_name: 'BU Lead Form' });
          }
          window.location.href = '/business-unlocked/thank-you';
        } else {
          var msg =
            (result.body && result.body.error) ||
            'Something went wrong. Please try again.';
          showError(msg);
          setLoading(false);
        }
      })
      .catch(function () {
        showError(
          'Network error. Please check your connection and try again.'
        );
        setLoading(false);
      });
  });
})();
