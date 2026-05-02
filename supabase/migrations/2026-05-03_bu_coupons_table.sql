-- Admin-managed coupon codes — migration for nvhzajpstswkmmfrgtiw
-- Apply via Supabase SQL Editor (the local MCP points at a different project).
--
-- Replaces the hardcoded COUPONS dict in api/create-invoice.py with a DB
-- table so anyone with admin access can add/disable codes via /admin/coupons
-- without redeploying. The hardcoded dict stays in code as a hot fallback —
-- if this table is unreachable for any reason, KATH still works.
--
-- All changes are additive and idempotent (safe to re-run).

-- 1. Coupons table
create table if not exists bu_coupons (
  code         text primary key,
  base_tier    text not null check (base_tier in ('early_bird', 'regular', 'vip')),
  amount       numeric(10, 2) not null check (amount > 0),
  label        text not null,
  active       boolean not null default true,
  created_at   timestamptz default now(),
  created_by   text
);

-- 2. Index for the hot path: lookup an active coupon by code
create index if not exists idx_bu_coupons_active
  on bu_coupons (code)
  where active = true;

-- 3. RLS — service-role only (admin endpoints use the service key)
alter table bu_coupons enable row level security;
drop policy if exists "bu_coupons_no_anon" on bu_coupons;
create policy "bu_coupons_no_anon"
  on bu_coupons
  for all to anon using (false) with check (false);

-- 4. Seed the existing live coupon so DB matches what's already in the
--    hardcoded fallback (avoid "DB and code disagree on KATH" surprises).
insert into bu_coupons (code, base_tier, amount, label, active, created_by)
values ('KATH', 'regular', 1999, 'Kath x BU', true, 'seed')
on conflict (code) do nothing;
