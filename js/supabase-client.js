// Supabase configuration
// Replace these with actual values before deployment
const SUPABASE_URL = 'YOUR_SUPABASE_URL';
const SUPABASE_ANON_KEY = 'YOUR_SUPABASE_ANON_KEY';

const SUPABASE_CONFIGURED = SUPABASE_URL !== 'YOUR_SUPABASE_URL' && SUPABASE_ANON_KEY !== 'YOUR_SUPABASE_ANON_KEY';

if (!SUPABASE_CONFIGURED) {
  console.warn('[Crisis-Proof Summit] Supabase not configured — UTM tracking disabled. Replace SUPABASE_URL and SUPABASE_ANON_KEY in js/supabase-client.js');
}

const supabase = SUPABASE_CONFIGURED
  ? window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
  : null;
