-- Coupon codes — migration for nvhzajpstswkmmfrgtiw
-- Apply via Supabase SQL Editor (the local MCP points at a different project).
--
-- Adds a single optional `coupon_code` column to new_business_normal_purchases
-- so /api/create-invoice can record which promo a buyer used (KATHEB, KATH,
-- KATHVIP, etc.). Coupon definitions themselves live in code (api/create-invoice.py
-- COUPONS dict) — the database only stores which code was applied per purchase.
--
-- All changes are additive and idempotent (safe to re-run).

-- 1. Optional coupon code on each purchase
alter table new_business_normal_purchases
  add column if not exists coupon_code text;

-- 2. Index for "list purchases by coupon" queries (e.g. attribution per influencer)
create index if not exists idx_purchases_coupon_code
  on new_business_normal_purchases (coupon_code)
  where coupon_code is not null;
