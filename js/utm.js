// UTM tracking module
// Depends on: supabase-client.js (must load first)

const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];
const SESSION_KEY = 'crisis_summit_session_id';
const UTM_STORAGE_KEY = 'crisis_summit_utm';

// --- Helper functions ---

function getSessionId() {
  let sessionId = localStorage.getItem(SESSION_KEY);
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, sessionId);
  }
  return sessionId;
}

function getUTMParams() {
  const stored = localStorage.getItem(UTM_STORAGE_KEY);
  if (!stored) {
    return {
      utm_source: null,
      utm_medium: null,
      utm_campaign: null,
      utm_content: null,
      utm_term: null,
    };
  }
  try {
    return JSON.parse(stored);
  } catch {
    return {
      utm_source: null,
      utm_medium: null,
      utm_campaign: null,
      utm_content: null,
      utm_term: null,
    };
  }
}

function parseUTMFromURL() {
  const params = new URLSearchParams(window.location.search);
  const utmData = {};
  let hasAny = false;

  UTM_KEYS.forEach((key) => {
    const value = params.get(key);
    utmData[key] = value || null;
    if (value) hasAny = true;
  });

  return { utmData, hasAny };
}

// --- Page load ---

document.addEventListener('DOMContentLoaded', () => {
  // 1. Parse UTM params from URL
  const { utmData, hasAny } = parseUTMFromURL();

  // 2. If URL has UTM params, overwrite localStorage; otherwise read from localStorage
  if (hasAny) {
    localStorage.setItem(UTM_STORAGE_KEY, JSON.stringify(utmData));
  }

  // 3. Get final UTM values (from URL or existing localStorage)
  const utm = getUTMParams();

  // 4. Ensure session ID exists
  const sessionId = getSessionId();

  // 5. Fire-and-forget page visit log to Supabase
  if (!supabase) return;
  supabase
    .from('page_visits')
    .insert({
      utm_source: utm.utm_source,
      utm_medium: utm.utm_medium,
      utm_campaign: utm.utm_campaign,
      session_id: sessionId,
    })
    .then(({ error }) => {
      if (error) {
        console.warn('Page visit log failed:', error.message);
      }
    });

  // --- Ticket button click handlers ---

  const ticketButtons = document.querySelectorAll('.ticket-btn');

  ticketButtons.forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();

      // Debounce: ignore if already disabled
      if (btn.disabled) return;

      const tier = btn.dataset.tier || 'unknown';
      const currentUTM = getUTMParams();
      const currentSessionId = getSessionId();

      // Disable button for 2 seconds to prevent duplicates
      btn.disabled = true;
      setTimeout(() => {
        btn.disabled = false;
      }, 2000);

      // Log click to Supabase, then redirect after short delay
      if (supabase) supabase
        .from('clicks')
        .insert({
          utm_source: currentUTM.utm_source,
          utm_medium: currentUTM.utm_medium,
          utm_campaign: currentUTM.utm_campaign,
          ticket_tier: tier,
          session_id: currentSessionId,
        })
        .then(({ error }) => {
          if (error) {
            console.warn('Click log failed:', error.message);
          }
        });

      // 500ms delay to give Supabase insert time to fire
      setTimeout(() => {
        const payURL = `https://example.com/pay?tier=${encodeURIComponent(tier)}`;
        window.location.href = payURL;
      }, 500);
    });
  });
});
