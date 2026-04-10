// Supabase configuration — The New Business Normal event
const SUPABASE_URL = 'https://nvhzajpstswkmmfrgtiw.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im52aHphanBzdHN3a21tZnJndGl3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU3OTYyMTcsImV4cCI6MjA5MTM3MjIxN30.Fv_bO_jfxPloC-Nel1ezAHWBWlHZnHja8ZNTtyCkX6k';

// Table names for this event (one set of tables per event)
const TABLE_VISITS = 'new_business_normal_visits';
const TABLE_CLICKS = 'new_business_normal_clicks';
const TABLE_PURCHASES = 'new_business_normal_purchases';

const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
