-- Payment sync + UTM attribution — migration for nvhzajpstswkmmfrgtiw
-- Applied 2026-04-14 via Supabase SQL Editor (MCP is wired to a different project)
--
-- Extends the existing new_business_normal_purchases table with the columns the
-- sync job needs (payment_status, paid_at, participant_id, match_method, mobile,
-- full_name, quantity, total, payment_provider, raw_row, synced_at), adds a
-- partial UNIQUE index on order_id so the sync can safely upsert by Xendit
-- transaction id, and creates the new_business_normal_sync_log audit table.
--
-- All changes are additive and idempotent (safe to re-run).

-- 1. Extend purchases table with missing columns
alter table new_business_normal_purchases
  add column if not exists full_name        text,
  add column if not exists mobile           text,
  add column if not exists quantity         int,
  add column if not exists total            numeric(10,2),
  add column if not exists payment_provider text,
  add column if not exists payment_status   text,
  add column if not exists paid_at          timestamptz,
  add column if not exists participant_id   bigint
    references new_business_normal_participants(id),
  add column if not exists match_method     text,
  add column if not exists raw_row          jsonb,
  add column if not exists synced_at        timestamptz default now();

-- 2. Dedupe key for sync upserts (partial unique index — NULLs allowed)
create unique index if not exists uniq_purchases_order_id
  on new_business_normal_purchases (order_id)
  where order_id is not null;

-- 3. Indexes for dashboard queries + match lookups
create index if not exists idx_purchases_email
  on new_business_normal_purchases (email);
create index if not exists idx_purchases_mobile
  on new_business_normal_purchases (mobile);
create index if not exists idx_purchases_participant_id
  on new_business_normal_purchases (participant_id);
create index if not exists idx_purchases_paid_at
  on new_business_normal_purchases (paid_at);
create index if not exists idx_purchases_payment_status
  on new_business_normal_purchases (payment_status);

-- 4. RLS — service-role only for purchases
alter table new_business_normal_purchases enable row level security;
drop policy if exists "purchases_no_anon" on new_business_normal_purchases;
create policy "purchases_no_anon"
  on new_business_normal_purchases
  for all to anon using (false) with check (false);

-- 5. Audit log table
create table if not exists new_business_normal_sync_log (
  id              uuid primary key default gen_random_uuid(),
  started_at      timestamptz,
  finished_at     timestamptz,
  rows_read       int default 0,
  rows_upserted   int default 0,
  rows_matched    int default 0,
  rows_unmatched  int default 0,
  errors          jsonb,
  success         boolean
);
create index if not exists idx_sync_log_started_at
  on new_business_normal_sync_log (started_at desc);

alter table new_business_normal_sync_log enable row level security;
drop policy if exists "sync_log_no_anon" on new_business_normal_sync_log;
create policy "sync_log_no_anon"
  on new_business_normal_sync_log
  for all to anon using (false) with check (false);
