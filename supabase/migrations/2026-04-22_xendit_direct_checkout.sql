-- Xendit direct checkout — migration for nvhzajpstswkmmfrgtiw
-- Applied 2026-04-22 via Supabase SQL Editor.
--
-- Supports the new native checkout page (one-page form → Xendit Invoice API →
-- our webhook). The existing purchases table already has order_id, payment_status,
-- payment_provider, paid_at, etc. from the 2026-04-14 sync migration. We only
-- need to add a few Xendit-specific fields so the webhook + create-invoice
-- endpoints can round-trip everything cleanly.
--
-- All changes are additive and idempotent.

-- 1. Columns for the Xendit flow
alter table new_business_normal_purchases
  add column if not exists session_id        text,
  add column if not exists xendit_invoice_id text,
  add column if not exists invoice_url       text,
  add column if not exists payment_channel   text,   -- e.g. GCASH, MAYA, CREDIT_CARD
  add column if not exists preferred_method  text;   -- what the user picked on our page

-- 2. Indexes for matcher + debugging lookups
create index if not exists idx_purchases_session_id
  on new_business_normal_purchases (session_id);
create index if not exists idx_purchases_xendit_invoice_id
  on new_business_normal_purchases (xendit_invoice_id);
