# Business Unlocked — Payment Sync & UTM Attribution

**Date:** 2026-04-14
**Owner:** Paolo
**Status:** Design approved, pending implementation plan

## Problem

Scale Your Org (via Xendit) processes Business Unlocked ticket payments and exposes them as a view-only Google Sheet. The Business Unlocked sales page already captures participant details + UTM tags into Supabase (`participants` table) via `api/submit-participant.py`. The gap: nothing links "who paid" back to "which UTM brought them in," so the `admin.html` dashboard cannot show revenue or conversion by UTM source.

Goal: every 15 minutes, mirror the payment sheet into Supabase, join to `participants` by email (mobile as fallback), and surface sales / revenue / conversion per UTM source on the existing admin dashboard. Tracking accuracy is the top priority.

## Non-Goals

- Replacing Scale Your Org / Xendit as the payment source of truth
- Writing payment data back to the Scale Your Org sheet
- Real-time (< 15 min) payment visibility
- Handling multi-currency (all transactions in PHP)

## Architecture

```
Scale Your Org sheet (view-only, owned by Scale Your Org)
        │ IMPORTRANGE (auto-refresh ~hourly)
        ▼
BU Payments Bridge sheet (Paolo owns, in his Drive)
        │ Sheets API read (service account)
        ▼
Vercel cron /api/sync-payments.py (every 15 min, Pro tier)
        │ UPSERT by transaction_id
        ▼
Supabase: payments ◄── joined on email/mobile ──► participants
        │
        ▼
admin.html — new KPIs, charts, payments table
```

### Why a bridge sheet

Paolo has view-only access to the Scale Your Org sheet, so a service account cannot be added directly. The bridge sheet is a pure read-through that Paolo owns; the service account is granted Viewer on the bridge sheet.

### Why Vercel cron (not Railway)

Paolo is now on Vercel Pro. Keeping the cron next to the existing serverless endpoints (`report.py`, `submit-participant.py`) means one repo, one deploy, one source of logs.

## Data Flow

1. **Force bridge refresh.** The cron handler opens the bridge sheet programmatically via Sheets API (which triggers IMPORTRANGE re-evaluation), waits 30 seconds, then reads. Worst-case payment-to-dashboard latency drops from ~75 min to ~15 min.

2. **Parse each row** from the Scale Your Org format:
   - Row layout (headerless): `event_type | status | full_name | email | mobile | product | amount | quantity | total | txn_id | txn_id (dup) | internal_id | provider | payment_type | payment_status | paid_at | status`
   - `tier` is extracted by splitting `product` on `|` and taking the last segment (e.g., `"THE NEW BUSINESS NORMAL | VIP"` → `"VIP"`)

3. **Normalize before matching:**
   - `email`: `str.strip().lower()` on both payment and participant sides
   - `mobile`: strip non-digits, drop leading `63` or `0`, compare last 10 digits

4. **UPSERT** into `payments` on `transaction_id` (primary key). Idempotent — re-running the sync never double-counts.

5. **Re-match pass** — for every `payments` row where `participant_id IS NULL` and `paid_at > now() - interval '7 days'`:
   - Try email match against `participants`
   - If no hit, try mobile match
   - If multiple candidates, pick the most recent where `submitted_at < paid_at`
   - If still nothing, set `match_method = 'direct'` (revenue still counted, bucketed separately)

6. **Audit log** — write one row to `payment_sync_log` with counts and errors.

## Schema

```sql
create table payments (
  transaction_id   text primary key,
  email            text,                        -- normalized: lower, trimmed
  mobile           text,                        -- normalized: digits only, last 10
  full_name        text,
  tier             text,                        -- 'Early Bird' | 'Regular' | 'VIP'
  amount           numeric(10,2),
  quantity         int,
  total            numeric(10,2),
  payment_provider text,                        -- 'xendit'
  payment_status   text,                        -- 'PAID' | 'FULLY_PAID' | 'REFUNDED' | ...
  paid_at          timestamptz,
  participant_id   uuid references participants(id),
  match_method     text,                        -- 'email' | 'mobile' | 'direct'
  raw_row          jsonb,
  synced_at        timestamptz default now()
);
create index on payments (email);
create index on payments (mobile);
create index on payments (participant_id);
create index on payments (paid_at);

create table payment_sync_log (
  id              uuid primary key default gen_random_uuid(),
  started_at      timestamptz,
  finished_at     timestamptz,
  rows_read       int,
  rows_upserted   int,
  rows_matched    int,
  rows_unmatched  int,
  errors          jsonb,
  success         boolean
);
```

RLS: both tables are service-role write, anon read-denied. The admin dashboard reads via the existing `api/report.py` endpoint (service-role key server-side), never from the browser directly.

## Accuracy Defenses

| # | Risk | Defense |
|---|---|---|
| 1 | Same payment inserted twice on re-run | `transaction_id` is PK; UPSERT semantics |
| 2 | IMPORTRANGE lag (~hourly refresh) | Programmatic sheet open forces refresh; 30s wait before read |
| 3 | Email case/whitespace mismatch | Normalize both sides: `.strip().lower()` |
| 4 | Mobile format mismatch (`63…` vs `+63…` vs `09…`) | Normalize: digits only, drop leading `63`/`0`, compare last 10 |
| 5 | Payment before form submit | 7-day re-match window on every sync |
| 6 | Refunds counted as revenue | Dashboard filters `payment_status IN ('PAID','FULLY_PAID')` |
| 7 | Same email with multiple participant rows | Link to most recent participant where `submitted_at < paid_at` |
| 8 | Payment with no matching participant | Store with `match_method = 'direct'`; show as separate UTM bucket |
| 9 | Silent sync failure | `payment_sync_log` row per run; dashboard shows "Last sync: Xm ago ✅/❌" |

## Dashboard Additions (admin.html)

**KPI cards (top strip):**
- Total Revenue (₱, `FULLY_PAID` / `PAID` only)
- Total Tickets Sold
- Visitor → Paid Conversion %
- Last sync timestamp + success indicator

**Charts (Chart.js):**
- Revenue by UTM source — horizontal bar, descending, includes `direct` bucket
- Tickets sold by UTM source × tier — stacked bar (Early Bird / Regular / VIP)
- Conversion funnel by UTM source — visits → form submits → paid, as % of each stage

**Payments table (bottom):**
Last 50 payments: `paid_at | full_name | email | tier | amount | utm_source | match_method`. The `match_method` column is the primary attribution-health signal.

**Date-range filter** at the top (default last 7 days) applies to all of the above.

## Components & Files

New:
- `docs/superpowers/specs/2026-04-14-payment-sync-utm-attribution-design.md` — this doc
- `api/sync-payments.py` — Vercel cron handler, the sync job
- `supabase/migrations/2026-04-14-payments-tables.sql` — schema migration
- `js/admin-sales.js` — new dashboard charts (keeps `admin.js` focused on existing logic)

Changed:
- `admin.html` — KPI strip, three new chart canvases, payments table
- `api/report.py` — add endpoints for revenue-by-UTM, sales-by-UTM, conversion-by-UTM, recent-payments, last-sync-status
- `vercel.json` — add cron entry for `/api/sync-payments` every 15 min
- `.env.example` — add `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON`, `BRIDGE_SHEET_ID`, `BRIDGE_SHEET_TAB`

External setup (manual, documented in a SETUP doc during implementation):
- Create bridge sheet in Paolo's Drive with `IMPORTRANGE` formula
- Create Google Cloud service account, enable Sheets API, download JSON key
- Share bridge sheet with service account email (Viewer)

## Error Handling

- **Bridge sheet unreachable** — sync logs error, exits cleanly; next run retries. No partial writes.
- **Malformed row** — logged to `payment_sync_log.errors`, other rows still processed.
- **Supabase write fails mid-batch** — UPSERT is row-level, so a single bad row doesn't abort the batch. Error captured in log.
- **Matching a refunded payment** — if `payment_status` flips from `PAID` to `REFUNDED` on a later sync, UPSERT updates the row; dashboard revenue recalculates automatically.

## Testing

- **Unit:** email + mobile normalizers, tier parser, participant matcher (all pure functions)
- **Integration:** run sync against a fixture bridge sheet + ephemeral Supabase branch; assert `payment_sync_log` counts match fixture expectations
- **Manual:** submit a form with UTMs, make a test payment via Scale Your Org, verify it appears in admin.html within 15 min with correct `utm_source` and `match_method = 'email'`

## Open Questions

None blocking. Implementation plan will cover deploy sequencing.
