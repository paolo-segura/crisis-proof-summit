-- Fix /api/report?action=clicks_over_time (Apr 23, 2026).
--
-- Two problems in the old handler (api/report.py:handle_clicks_over_time):
--   1. It queried a column named `clicked_at`, but the clicks table's
--      timestamp column is actually `created_at` — so every call returned
--      502 "Supabase request failed: HTTP Error 400". Schema verified by
--      fetching one row: {id, created_at, session_id, ticket_tier, utm_*}.
--   2. Even once the column name was right, it pulled every row in the
--      30-day window into Python to count. That would eventually time out
--      as the table grew.
--
-- This migration adds an index on created_at (range-scan filter) and a
-- Postgres RPC that does the daily aggregation server-side. The RPC
-- returns ~30 rows regardless of table size.
--
-- All changes are additive and idempotent (safe to re-run).

-- 1. Range-scan index on created_at
create index if not exists idx_clicks_created_at
  on new_business_normal_clicks (created_at);

-- 2. Daily click-count RPC.
--    Buckets dates in UTC to match the previous Python behaviour
--    (handle_clicks_over_time used the first 10 chars of the ISO string).
--    `stable` lets PostgREST accept GET requests on /rpc/… with query params,
--    keeping the existing supabase_get() helper in api/report.py usable.
create or replace function new_business_normal_clicks_daily(p_days int default 30)
returns table (date date, count bigint)
language sql
stable
as $$
  select
    (created_at at time zone 'UTC')::date as date,
    count(*)::bigint                      as count
  from new_business_normal_clicks
  where created_at >= (current_date - p_days)
  group by 1
  order by 1;
$$;
