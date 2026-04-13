// Supabase configuration — Business Unlocked event
const SUPABASE_URL = 'https://nvhzajpstswkmmfrgtiw.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im52aHphanBzdHN3a21tZnJndGl3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU3OTYyMTcsImV4cCI6MjA5MTM3MjIxN30.Fv_bO_jfxPloC-Nel1ezAHWBWlHZnHja8ZNTtyCkX6k';

// Table names for this event (one set of tables per event)
const TABLE_VISITS = 'new_business_normal_visits';
const TABLE_CLICKS = 'new_business_normal_clicks';
const TABLE_PURCHASES = 'new_business_normal_purchases';
const TABLE_PARTICIPANTS = 'new_business_normal_participants';

// The CDN UMD at https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2 starts with
// `var supabase = ...`, which adds `supabase` to the script VarNames. Declaring
// `const supabase` here would throw "Identifier 'supabase' has already been declared",
// killing this whole file (and with it the TABLE_* constants above). Instead, replace
// window.supabase with the initialized client — all existing `supabase.from(...)`
// call sites keep working without renames.
(function () {
  var sdk = window.supabase;
  window.supabase = sdk.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
})();
