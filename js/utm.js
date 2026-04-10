// UTM tracking module — The New Business Normal event
// Depends on: supabase-client.js (must load first)

const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];
const SESSION_KEY = 'nbn_session_id';
const UTM_STORAGE_KEY = 'nbn_utm';

// --- Helper functions (exposed on window for main.js to reuse) ---

function getSessionId() {
  let sessionId = localStorage.getItem(SESSION_KEY);
  if (!sessionId) {
    sessionId = (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now()) + '-' + Math.random().toString(36).slice(2);
    localStorage.setItem(SESSION_KEY, sessionId);
  }
  return sessionId;
}

function getUTMParams() {
  const empty = { utm_source: null, utm_medium: null, utm_campaign: null, utm_content: null, utm_term: null };
  const stored = localStorage.getItem(UTM_STORAGE_KEY);
  if (!stored) return empty;
  try { return Object.assign(empty, JSON.parse(stored)); } catch { return empty; }
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

// Expose for main.js
window.NBN_TRACKING = {
  getSessionId: getSessionId,
  getUTMParams: getUTMParams,
};

// --- Page load: log a visit ---

document.addEventListener('DOMContentLoaded', () => {
  // 1. Parse UTM params from URL; persist if present
  const { utmData, hasAny } = parseUTMFromURL();
  if (hasAny) {
    localStorage.setItem(UTM_STORAGE_KEY, JSON.stringify(utmData));
  }

  const utm = getUTMParams();
  const sessionId = getSessionId();

  // 2. Fire-and-forget page visit log to Supabase
  if (!supabase) return;
  supabase
    .from(TABLE_VISITS)
    .insert({
      session_id: sessionId,
      utm_source: utm.utm_source,
      utm_medium: utm.utm_medium,
      utm_campaign: utm.utm_campaign,
      utm_content: utm.utm_content,
      utm_term: utm.utm_term,
      page_path: window.location.pathname,
      referrer: document.referrer || null,
    })
    .then(({ error }) => {
      if (error) console.warn('Visit log failed:', error.message);
    });
});
