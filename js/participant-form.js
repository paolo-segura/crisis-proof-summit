/* participant-form.js
   Handles the Crisis-Proof Summit participant interview form.
   - Shows/hides "Other" fill-ins
   - Validates required fields
   - Inserts directly into Supabase (TABLE_PARTICIPANTS) via the anon key
   Depends on: supabase-client.js, utm.js (loaded before this file)
*/

(function () {
  'use strict';

  var form = document.getElementById('participant-form');
  if (!form) return;

  var submitBtn = document.getElementById('submit-btn');
  var errorBox = document.getElementById('form-error');
  var successCard = document.getElementById('form-success');

  // --- Show/hide "Other" text inputs when an "Other" radio is selected ---
  form.addEventListener('change', function (e) {
    if (e.target && e.target.type === 'radio') {
      var groupName = e.target.name;
      // Find all radios in this group — if any has data-other-target and is checked, show its input
      var groupRadios = form.querySelectorAll('input[type="radio"][name="' + groupName + '"]');
      groupRadios.forEach(function (radio) {
        var targetId = radio.getAttribute('data-other-target');
        if (!targetId) return;
        var targetInput = document.getElementById(targetId);
        if (!targetInput) return;
        if (radio.checked) {
          targetInput.hidden = false;
          targetInput.required = true;
          if (e.target === radio) targetInput.focus();
        } else {
          targetInput.hidden = true;
          targetInput.required = false;
          targetInput.value = '';
        }
      });
    }
  });

  // --- Helpers ---
  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
    errorBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function clearError() {
    errorBox.hidden = true;
    errorBox.textContent = '';
  }

  function getRadioValue(name) {
    var el = form.querySelector('input[type="radio"][name="' + name + '"]:checked');
    return el ? el.value : '';
  }

  function getStoredUTM() {
    try {
      return JSON.parse(localStorage.getItem('nbn_utm') || '{}');
    } catch (e) {
      return {};
    }
  }

  function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  // --- Submit handler ---
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearError();

    // Honeypot
    if (form.website && form.website.value) {
      // Silently "succeed" for bots
      form.hidden = true;
      successCard.hidden = false;
      return;
    }

    var fullName = form.full_name.value.trim();
    var mobile = form.mobile_number.value.trim();
    var email = form.email.value.trim();
    var describesYou = getRadioValue('describes_you');
    var describesYouOther = form.describes_you_other.value.trim();
    var businessType = getRadioValue('business_type');
    var businessTypeOther = form.business_type_other.value.trim();
    var referredBy = getRadioValue('referred_by');
    var referredByOther = form.referred_by_other.value.trim();

    // Validation
    if (!fullName) return showError('Please enter your full name.');
    if (!mobile) return showError('Please enter your mobile number.');
    if (!email || !isValidEmail(email)) return showError('Please enter a valid email address.');
    if (!describesYou) return showError('Please select which best describes you.');
    if (describesYou === 'Other' && !describesYouOther) return showError('Please specify how you would describe yourself.');
    if (!businessType) return showError('Please select your business/company type.');
    if (businessType === 'Other' && !businessTypeOther) return showError('Please specify your business type.');
    if (!referredBy) return showError('Please select who referred you.');
    if (referredBy === 'Other' && !referredByOther) return showError('Please enter who referred you.');

    if (typeof supabase === 'undefined' || !supabase || !supabase.from) {
      return showError('Connection to the server is unavailable. Please refresh and try again.');
    }

    var utm = getStoredUTM();
    var urlParams = new URLSearchParams(window.location.search);
    var sessionId = (window.NBN_TRACKING && window.NBN_TRACKING.getSessionId)
      ? window.NBN_TRACKING.getSessionId()
      : (localStorage.getItem('nbn_session_id') || null);

    var row = {
      session_id: sessionId,
      full_name: fullName,
      email: email.toLowerCase(),
      mobile_number: mobile,
      describes_you: describesYou === 'Other' ? 'Other: ' + describesYouOther : describesYou,
      business_type: businessType === 'Other' ? 'Other: ' + businessTypeOther : businessType,
      referred_by: referredBy === 'Other' ? 'Other: ' + referredByOther : referredBy,
      utm_source: urlParams.get('utm_source') || utm.utm_source || null,
      utm_medium: urlParams.get('utm_medium') || utm.utm_medium || null,
      utm_campaign: urlParams.get('utm_campaign') || utm.utm_campaign || null,
      utm_content: urlParams.get('utm_content') || utm.utm_content || null,
      utm_term: urlParams.get('utm_term') || utm.utm_term || null,
      page_url: window.location.href,
      user_agent: navigator.userAgent
    };

    submitBtn.disabled = true;
    var originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = 'Submitting…';

    supabase
      .from(TABLE_PARTICIPANTS)
      .insert(row)
      .then(function (res) {
        if (res && res.error) {
          throw new Error(res.error.message || 'Submission failed. Please try again.');
        }
        form.hidden = true;
        successCard.hidden = false;
        window.scrollTo({ top: 0, behavior: 'smooth' });
      })
      .catch(function (err) {
        console.error('[participant-form]', err);
        showError(err.message || 'Something went wrong. Please try again.');
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
      });
  });
})();
