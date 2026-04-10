// Supabase configuration — The New Business Normal event
const SUPABASE_URL = 'https://nvhzajpstswkmmfrgtiw.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_nfR24UUlxiSbna1oIfhbIQ_TnFODF46';

// Table names for this event (one set of tables per event)
const TABLE_VISITS = 'new_business_normal_visits';
const TABLE_CLICKS = 'new_business_normal_clicks';
const TABLE_PURCHASES = 'new_business_normal_purchases';

const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
