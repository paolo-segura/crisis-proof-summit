// Registration form — validates, POSTs to /api/register-free, redirects to /free/thank-you.
// /api/register-free handles: Google Sheets append + Brevo confirmation email.
(function () {
  const form = document.getElementById('reg-form');
  const errorEl = document.getElementById('form-error');
  const submitBtn = document.getElementById('submit-btn');
  if (!form) return;

  const ENDPOINT = '/api/register-free';

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.hidden = false;
  }

  function hideError() {
    errorEl.hidden = true;
    errorEl.textContent = '';
  }

  function normalizePhone(raw) {
    const digits = raw.replace(/[^\d+]/g, '');
    if (digits.startsWith('+63')) return digits;
    if (digits.startsWith('63')) return '+' + digits;
    if (digits.startsWith('09')) return '+63' + digits.slice(1);
    if (digits.startsWith('9') && digits.length === 10) return '+63' + digits;
    return digits;
  }

  function getUTMParams() {
    const params = new URLSearchParams(window.location.search);
    return {
      utm_source: params.get('utm_source') || null,
      utm_medium: params.get('utm_medium') || null,
      utm_campaign: params.get('utm_campaign') || null,
      utm_content: params.get('utm_content') || null,
      utm_term: params.get('utm_term') || null,
    };
  }

  async function handleSubmit(event) {
    event.preventDefault();
    hideError();

    const name = form.name.value.trim();
    const email = form.email.value.trim().toLowerCase();
    const phoneRaw = form.phone.value.trim();
    const consent = form.consent.checked;

    if (!name || name.length < 2) {
      return showError('Please enter your full name.');
    }
    if (!email || !/^\S+@\S+\.\S+$/.test(email)) {
      return showError('Please enter a valid email address.');
    }
    const phone = normalizePhone(phoneRaw);
    if (phone.replace(/\D/g, '').length < 10) {
      return showError('Please enter a valid contact number.');
    }
    if (!consent) {
      return showError('Please agree to receive webinar reminders and marketing messages.');
    }

    submitBtn.disabled = true;
    const originalLabel = submitBtn.textContent;
    submitBtn.textContent = 'Registering...';

    const payload = {
      name,
      email,
      phone,
      marketing_consent: true,
      ...getUTMParams(),
      user_agent: navigator.userAgent,
      referrer: document.referrer || null,
    };

    try {
      const res = await fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        console.error('Registration error:', body);
        submitBtn.disabled = false;
        submitBtn.textContent = originalLabel;
        return showError(
          body.error || 'We couldn\'t register you right now. Please try again in a moment.'
        );
      }

      window.location.href = `/free/thank-you?email=${encodeURIComponent(email)}`;
    } catch (err) {
      console.error('Unexpected error:', err);
      submitBtn.disabled = false;
      submitBtn.textContent = originalLabel;
      showError('Something went wrong. Please refresh and try again.');
    }
  }

  form.addEventListener('submit', handleSubmit);
})();
