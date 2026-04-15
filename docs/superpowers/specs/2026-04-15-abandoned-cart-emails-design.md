# Abandoned Cart Email Sequence — Design Spec

**Date:** 2026-04-15
**Owner:** Paolo
**Status:** Design approved, pending implementation plan

## Problem

The Business Unlocked sales page captures participant details (`new_business_normal_participants`) before payment. Some people fill the form but never complete checkout. There's currently no chase mechanism — they go cold.

Goal: a 3-email sequence delivered via Brevo to participants who filled the form but have no matching paid purchase, with the cron pushing qualifying contacts into Brevo and Brevo handling the actual sends.

## Non-Goals

- Building a Brevo automation engine ourselves (Brevo handles timing/sending)
- Drafting email content in this repo at runtime (templates live in Brevo)
- Reaching abandoned form-fillers on channels other than email (no SMS/Messenger v1)
- Walk-up "abandoned" handling (event-day no-shows are a separate flow)

## Send Mechanism

**Option A from brainstorm:** Cron pushes contacts to a Brevo list. A pre-configured Brevo automation triggers off the list-add event and sends the 3 emails on a schedule, with an exclusion list to skip people who pay mid-sequence.

Why: warm Brevo IP reputation (already used by existing nurture series), pause/edit emails in Brevo dashboard without a deploy, Brevo handles dedup + retries + bounce handling.

## Cadence

| Email | Wait after form-fill | Style |
|---|---|---|
| 1 | 3 hours | Light "saw you started — questions?" check-in |
| 2 | +3 days | "What changes when you actually attend" — emphasize transformation |
| 3 | +7 days | Last-call urgency + scarcity — "doors closing" |

**Hard cutoff:** stop pushing new contacts to the list after **May 7, 2026** (2 days before the May 9 event). Anyone still abandoned after that is a no-show lead, not a buyer lead.

## Architecture

```
Vercel cron /api/abandoned-cart (every 15 min)
        │
        ▼
1. Find abandoned: participants where
   • created_at < NOW - 3 hours
   • email NOT in any PAID/FULLY_PAID purchase
   • mobile NOT in any PAID/FULLY_PAID purchase
   • brevo_abandoned_pushed_at IS NULL
   • created_at > NOW - 14 days
   • Today < May 7, 2026
        │
        ▼
2. POST each to Brevo `BU Abandoned Cart` list via Contacts API
   Mark participant.brevo_abandoned_pushed_at = NOW
        │
        ▼
3. Find newly paid: participants whose email/mobile matches a PAID/FULLY_PAID
   purchase AND brevo_excluded_pushed_at IS NULL
        │
        ▼
4. POST each to Brevo `BU Paid — Exclude` list
   Mark participant.brevo_excluded_pushed_at = NOW

Audit row to new_business_normal_brevo_log on every run
```

Brevo side (configured once by Paolo, manual):
- `BU Abandoned Cart` list — cron writes to this
- `BU Paid — Exclude` list — cron writes to this
- Automation triggered on add to `BU Abandoned Cart`:
  - Step 1: send Email 1 (no extra wait — 3 hours has already elapsed)
  - Step 2: wait 3 days, exclude-check (skip if in `BU Paid — Exclude`), send Email 2
  - Step 3: wait 4 days, exclude-check, send Email 3

## Schema

```sql
alter table new_business_normal_participants
  add column if not exists brevo_abandoned_pushed_at timestamptz,
  add column if not exists brevo_excluded_pushed_at  timestamptz;

create index if not exists idx_participants_brevo_abandoned
  on new_business_normal_participants (brevo_abandoned_pushed_at);
create index if not exists idx_participants_brevo_excluded
  on new_business_normal_participants (brevo_excluded_pushed_at);

create table if not exists new_business_normal_brevo_log (
  id uuid primary key default gen_random_uuid(),
  started_at timestamptz, finished_at timestamptz,
  abandoned_pushed int default 0,
  excluded_pushed  int default 0,
  errors jsonb,
  success boolean
);
create index if not exists idx_brevo_log_started_at
  on new_business_normal_brevo_log (started_at desc);

alter table new_business_normal_brevo_log enable row level security;
drop policy if exists "brevo_log_no_anon" on new_business_normal_brevo_log;
create policy "brevo_log_no_anon" on new_business_normal_brevo_log
  for all to anon using (false) with check (false);
```

## Files

**Create:**
- `api/abandoned_cart.py` — pure module: `find_abandoned_participants`, `find_newly_paid_participants`, `brevo_add_to_list`, `run_abandoned_cart` (orchestrator with dependency injection — same pattern as `sync_payments.py`)
- `api/abandoned-cart.py` — Vercel cron handler (thin wrapper, mirrors `sync-payments.py`)
- `tests/test_abandoned_cart.py` — unit tests for normalizers, query builders, orchestrator (TDD'd)
- `emails/abandoned-1-still-thinking.html` — Email 1 draft, dark theme + Poppins to match existing nurture
- `emails/abandoned-2-what-changes.html` — Email 2 draft
- `emails/abandoned-3-last-call.html` — Email 3 draft
- `supabase/migrations/2026-04-15_brevo_tracking.sql` — migration (Paolo runs in Supabase SQL Editor)

**Modify:**
- `vercel.json` — add cron entry `{ "path": "/api/abandoned-cart", "schedule": "*/15 * * * *" }`
- `.env.example` — add `BREVO_API_KEY=`, `BREVO_ABANDONED_LIST_ID=`, `BREVO_EXCLUDE_LIST_ID=`
- `api/report.py` — add `handle_abandoned_log` action so the dashboard can show "Last abandoned-cart run: 5m ago ✅ pushed 3"
- `js/admin-sales.js` — show that status next to the existing "Last sync" indicator

## Brevo API Contract

`POST https://api.brevo.com/v3/contacts`
Headers: `api-key: <BREVO_API_KEY>`, `accept: application/json`, `content-type: application/json`
Body:
```json
{
  "email": "wyne_ramos@yahoo.com",
  "attributes": { "FNAME": "Wynes", "LNAME": "Ramos" },
  "listIds": [<int_list_id>],
  "updateEnabled": true
}
```

Idempotent — if contact already exists, `updateEnabled: true` updates instead of erroring. If already in the list, the response is still 204.

## Error Handling

- **Brevo API down or 5xx**: log to `new_business_normal_brevo_log.errors`, do NOT mark `brevo_abandoned_pushed_at` (so they get retried next cron). Continue processing other contacts.
- **Brevo rate limit (429)**: same as above — retry next cycle. Brevo's free tier allows 400 emails/day; paid plans support 600+ requests/min, well above our scale.
- **Supabase unreachable**: log error, exit cleanly. Next cron tries again.
- **Bad email format already in DB**: skip with logged error. Server-side validation (added to `submit-participant.py` in commit `a89e166`) prevents new bad ones.
- **Brevo log write fails**: silent — never fail the cron just because the log failed (matches `sync_payments.py` pattern).

## Hard Cutoff Logic

The cutoff (May 7, 2026 23:59 UTC) is enforced in code:

```python
EVENT_DATE = datetime(2026, 5, 9, tzinfo=timezone.utc)
PUSH_CUTOFF = EVENT_DATE - timedelta(days=2)

if datetime.now(timezone.utc) > PUSH_CUTOFF:
    return {"abandoned_pushed": 0, "skipped_reason": "past push cutoff"}
```

The exclude-list push (step 3) keeps running indefinitely so people who pay last-minute are correctly removed from any in-flight automation.

## Testing

- **Unit tests:** `find_abandoned_participants` query construction, `find_newly_paid_participants`, `brevo_add_to_list` payload format, hard-cutoff logic, orchestrator phase boundaries, error capture per phase
- **Integration:** stub Brevo + Supabase, verify the orchestrator pushes the right contacts and writes the audit log
- **Manual smoke:** trigger the endpoint via Vercel dashboard, verify the brevo_log row appears, check the contact lands in Brevo's `BU Abandoned Cart` list

## Manual Setup Required (Paolo's work)

Documented separately in `docs/sync-setup.md` (appended). Summary:
1. Brevo → Contacts → Lists → create "BU Abandoned Cart" and "BU Paid — Exclude". Note their IDs.
2. Brevo → Templates → upload the 3 HTML files from `emails/abandoned-*.html`.
3. Brevo → Automations → create a new workflow:
   - Trigger: contact added to "BU Abandoned Cart"
   - Step 1: Send template `abandoned-1` (no wait)
   - Step 2: Wait 3 days → check if contact is in "BU Paid — Exclude" → if yes EXIT → send `abandoned-2`
   - Step 3: Wait 4 days → exclude check → send `abandoned-3`
4. Vercel env vars:
   - `BREVO_API_KEY` (Brevo → SMTP & API → API Keys → reveal)
   - `BREVO_ABANDONED_LIST_ID` (integer from step 1)
   - `BREVO_EXCLUDE_LIST_ID` (integer from step 1)

## Open Questions

None blocking.
