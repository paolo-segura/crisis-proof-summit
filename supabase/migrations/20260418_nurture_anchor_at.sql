-- Adds a nurture_anchor_at column that the send-nurture cron uses as the
-- "day 0" reference instead of paid_at, when set. This exists because
-- sync_payments re-syncs paid_at every 15 min from the Google Sheets bridge,
-- which overwrites any manual paid_at edits intended to pace a customer's
-- email sequence. nurture_anchor_at is local to this DB and never touched
-- by sync_payments.
--
-- Behavior in api/send_nurture.py:
--   - If nurture_anchor_at IS NOT NULL → use it as the schedule anchor.
--   - If nurture_anchor_at IS NULL     → fall back to paid_at (default).
--
-- To reset a customer's drip schedule to start "now" (e.g., for a late
-- purchase or a paced VIP flow):
--   UPDATE new_business_normal_purchases
--      SET nurture_anchor_at = now()
--    WHERE email = 'customer@example.com';

ALTER TABLE new_business_normal_purchases
  ADD COLUMN IF NOT EXISTS nurture_anchor_at timestamptz;

COMMENT ON COLUMN new_business_normal_purchases.nurture_anchor_at IS
  'Override anchor for nurture email scheduling. If set, send_nurture uses this instead of paid_at. Not touched by sync_payments.';
