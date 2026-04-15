# Payment Sync & UTM Attribution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mirror the Scale Your Org payments Google Sheet into Supabase every 15 minutes, join by email/mobile to the existing `new_business_normal_participants` table, and surface sales/revenue/conversion per UTM source on `admin.html`.

**Architecture:** Vercel cron (15-min) → Google Sheets API (reads a bridge sheet that IMPORTRANGE-mirrors the view-only payments sheet) → upsert into Supabase `new_business_normal_purchases` by `transaction_id` → re-match unmatched rows against participants on email/mobile → audit every run in `new_business_normal_sync_log`. Dashboard adds KPIs, three charts, a payments table, and a last-sync indicator.

**Tech Stack:** Python 3 (Vercel serverless, stdlib-first; `google-auth` + `google-api-python-client` for Sheets; no Supabase SDK — use `urllib` PostgREST calls like `api/report.py` does), PostgreSQL via Supabase, Chart.js (already in `admin.html`), pytest for unit tests.

**Reference spec:** `docs/superpowers/specs/2026-04-14-payment-sync-utm-attribution-design.md`

---

## File Structure

**Create:**
- `supabase/migrations/2026-04-14_purchases_and_sync_log.sql` — schema
- `api/sync-payments.py` — Vercel cron handler (self-contained, follows `api/report.py` shape)
- `tests/__init__.py` — empty package marker
- `tests/conftest.py` — adds `api/` to `sys.path` for imports
- `tests/test_sync_payments.py` — pytest unit tests for normalizers, parser, matcher
- `js/admin-sales.js` — new dashboard fetch + chart logic
- `docs/sync-setup.md` — manual setup walkthrough (bridge sheet, service account)
- `requirements.txt` — pins for google-auth + google-api-python-client + pytest

**Modify:**
- `api/report.py` — add 5 new actions (`revenue_by_utm`, `tickets_by_utm_tier`, `conversion_by_utm`, `recent_payments`, `last_sync`); fix existing actions that query non-existent table names (`sales`, `page_visits`, `clicks`) to use actual prefixed table names
- `admin.html` — add KPI strip, 3 chart canvases, payments table, date-range filter, last-sync indicator; include `js/admin-sales.js`
- `vercel.json` — add `crons` entry pointing at `/api/sync-payments` every 15 min
- `.env.example` — add `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON`, `BRIDGE_SHEET_ID`, `BRIDGE_SHEET_TAB`

**Responsibility split:** All sync logic lives in `api/sync-payments.py` as module-level functions (normalizers, parser, matcher, sheet reader, supabase client, orchestrator) plus the `handler` class at the bottom. This matches the existing `api/report.py` pattern — no new `lib/` folder, no cross-file imports to set up on Vercel.

---

## Task 1: Add `requirements.txt` and set up pytest

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `requirements.txt`**

```text
google-auth==2.35.0
google-api-python-client==2.147.0
pytest==8.3.3
```

- [ ] **Step 2: Create empty `tests/__init__.py`**

```python
```

- [ ] **Step 3: Create `tests/conftest.py`**

```python
import os
import sys

# Add the project's `api/` folder to sys.path so tests can `import sync_payments`.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(ROOT, "api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)
```

- [ ] **Step 4: Create venv and install deps**

Run:
```bash
cd /Users/paolosegura/Documents/Claude\ Builds/crisis-proof-summit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: installs complete without errors.

- [ ] **Step 5: Verify pytest runs (no tests yet)**

Run: `pytest tests/ -v`
Expected: `no tests ran` (exit 5 is OK — no test files yet).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt tests/__init__.py tests/conftest.py
git commit -m "chore: add requirements.txt and pytest harness"
```

---

## Task 2: Supabase migration — extend `_purchases` and add `_sync_log`

**Files:**
- Create: `supabase/migrations/2026-04-14_purchases_and_sync_log.sql`

Note: `new_business_normal_purchases` already exists (referenced in `js/supabase-client.js` as `TABLE_PURCHASES`) but its columns are unknown. This migration uses `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` so it's safe to run whatever the current state is.

- [ ] **Step 1: Create the migration file**

```sql
-- 2026-04-14_purchases_and_sync_log.sql
-- Extends new_business_normal_purchases for Scale Your Org sync,
-- and creates new_business_normal_sync_log for audit trails.

-- ---------- Purchases table ----------
create table if not exists new_business_normal_purchases (
  transaction_id   text primary key
);

alter table new_business_normal_purchases
  add column if not exists email            text,
  add column if not exists mobile           text,
  add column if not exists full_name        text,
  add column if not exists tier             text,
  add column if not exists amount           numeric(10,2),
  add column if not exists quantity         int,
  add column if not exists total            numeric(10,2),
  add column if not exists payment_provider text,
  add column if not exists payment_status   text,
  add column if not exists paid_at          timestamptz,
  add column if not exists participant_id   uuid,
  add column if not exists match_method     text,
  add column if not exists utm_source       text,
  add column if not exists utm_medium       text,
  add column if not exists utm_campaign     text,
  add column if not exists utm_content      text,
  add column if not exists raw_row          jsonb,
  add column if not exists synced_at        timestamptz default now();

create index if not exists idx_purchases_email          on new_business_normal_purchases (email);
create index if not exists idx_purchases_mobile         on new_business_normal_purchases (mobile);
create index if not exists idx_purchases_participant_id on new_business_normal_purchases (participant_id);
create index if not exists idx_purchases_paid_at        on new_business_normal_purchases (paid_at);
create index if not exists idx_purchases_utm_source     on new_business_normal_purchases (utm_source);

-- RLS: service-role only for writes; no anon access.
alter table new_business_normal_purchases enable row level security;

drop policy if exists "purchases_no_anon" on new_business_normal_purchases;
create policy "purchases_no_anon" on new_business_normal_purchases
  for all to anon using (false) with check (false);

-- ---------- Sync log table ----------
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

create index if not exists idx_sync_log_started_at on new_business_normal_sync_log (started_at desc);

alter table new_business_normal_sync_log enable row level security;

drop policy if exists "sync_log_no_anon" on new_business_normal_sync_log;
create policy "sync_log_no_anon" on new_business_normal_sync_log
  for all to anon using (false) with check (false);
```

- [ ] **Step 2: Apply the migration via the Supabase MCP**

Use the `mcp__supabase__apply_migration` tool with `name: "2026_04_14_purchases_and_sync_log"` and `query` = the full SQL above.

If the MCP isn't configured, fall back to manual: open Supabase dashboard → SQL Editor → paste the SQL → Run.

- [ ] **Step 3: Verify tables exist via MCP**

Call `mcp__supabase__list_tables` and confirm both `new_business_normal_purchases` and `new_business_normal_sync_log` appear with the expected columns.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/2026-04-14_purchases_and_sync_log.sql
git commit -m "feat: extend purchases schema and add sync_log table"
```

---

## Task 3: Write the manual setup guide (bridge sheet + service account)

**Files:**
- Create: `docs/sync-setup.md`

- [ ] **Step 1: Create `docs/sync-setup.md`**

```markdown
# Payment Sync — One-Time Manual Setup

These steps must be completed before the cron job can read from the Scale Your Org sheet. ~15 minutes total.

## 1. Create the bridge Google Sheet

1. Open <https://sheets.new> in your Google account (the one that has View access to the Scale Your Org payments sheet).
2. Name it: **BU Payments Bridge**
3. Rename the first tab to **payments**.
4. In cell **A1**, paste:

   ```
   =IMPORTRANGE("<SCALE_YOUR_ORG_SHEET_URL>", "<SOURCE_TAB>!A:Z")
   ```

   Replace `<SCALE_YOUR_ORG_SHEET_URL>` with the full URL of the view-only payments sheet, and `<SOURCE_TAB>` with the tab name (e.g., `Sheet1`).
5. Click the cell → "Allow access" when the popup appears.
6. Copy the bridge sheet's URL. The sheet ID is the long string between `/d/` and `/edit`. Save it — you'll need it for `BRIDGE_SHEET_ID`.

## 2. Create a Google Cloud service account

1. Go to <https://console.cloud.google.com/>.
2. Create a new project: **business-unlocked-sync** (or reuse an existing project).
3. Enable the Sheets API: **APIs & Services → Library → Google Sheets API → Enable**.
4. Create a service account: **IAM & Admin → Service Accounts → Create**.
   - Name: `bu-payments-sync`
   - Skip role assignment (Sheets access is granted per-sheet, not via IAM).
5. Open the new service account → **Keys → Add key → Create new key → JSON**. Save the JSON file.
6. Copy the service account's email (looks like `bu-payments-sync@<project>.iam.gserviceaccount.com`).

## 3. Share the bridge sheet with the service account

1. Open the bridge sheet → **Share**.
2. Paste the service account email. Role: **Viewer**. Uncheck "Notify". Share.

## 4. Add the secrets to Vercel

In Vercel project settings → **Environment Variables**, add:

| Name | Value |
|---|---|
| `BRIDGE_SHEET_ID` | The sheet ID from step 1.6 |
| `BRIDGE_SHEET_TAB` | `payments` |
| `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON` | The entire contents of the service account JSON file (paste as a single-line string) |

Existing vars that must also be present: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ADMIN_PASSWORD`.

## 5. Done

The cron job will pick up the new env vars on the next deploy.
```

- [ ] **Step 2: Update `.env.example`**

Append these lines to `.env.example` (create the file if missing):

```
# Payment sync — see docs/sync-setup.md for how to obtain
GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON=
BRIDGE_SHEET_ID=
BRIDGE_SHEET_TAB=payments
```

- [ ] **Step 3: Commit**

```bash
git add docs/sync-setup.md .env.example
git commit -m "docs: add payment-sync manual setup guide"
```

---

## Task 4: TDD — Email and mobile normalizers

**Files:**
- Create: `api/sync-payments.py`
- Test: `tests/test_sync_payments.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sync_payments.py`:

```python
import sync_payments as sp


# ---------- normalize_email ----------

def test_normalize_email_lowercases_and_trims():
    assert sp.normalize_email("  Paolo@Example.COM ") == "paolo@example.com"

def test_normalize_email_handles_none():
    assert sp.normalize_email(None) == ""

def test_normalize_email_handles_empty():
    assert sp.normalize_email("") == ""


# ---------- normalize_mobile ----------

def test_normalize_mobile_strips_country_code_63():
    assert sp.normalize_mobile("639178334375") == "9178334375"

def test_normalize_mobile_strips_leading_zero():
    assert sp.normalize_mobile("09178334375") == "9178334375"

def test_normalize_mobile_strips_plus_sign():
    assert sp.normalize_mobile("+639178334375") == "9178334375"

def test_normalize_mobile_strips_formatting():
    assert sp.normalize_mobile("+63 917 833 4375") == "9178334375"

def test_normalize_mobile_already_normalized():
    assert sp.normalize_mobile("9178334375") == "9178334375"

def test_normalize_mobile_handles_none():
    assert sp.normalize_mobile(None) == ""

def test_normalize_mobile_returns_empty_if_too_short():
    # Less than 10 digits → ambiguous, return empty so it never matches
    assert sp.normalize_mobile("1234") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/test_sync_payments.py -v`
Expected: `ModuleNotFoundError: No module named 'sync_payments'` or similar.

- [ ] **Step 3: Create `api/sync-payments.py` with normalizers**

```python
"""
/api/sync-payments — Vercel cron handler.

Every 15 minutes:
  1. Reads the BU Payments Bridge Google Sheet via Sheets API
  2. Parses each row into a purchase record
  3. Upserts into new_business_normal_purchases (by transaction_id)
  4. Re-matches unmatched purchases (last 7 days) against participants
  5. Logs the run to new_business_normal_sync_log

Triggered by Vercel cron (see vercel.json). Protected by CRON_SECRET header.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import re


# ---------------------------------------------------------------------------
# Normalizers (pure functions, TDD-covered)
# ---------------------------------------------------------------------------

def normalize_email(raw):
    """Lowercase + trim. Returns '' for None/empty."""
    if not raw:
        return ""
    return str(raw).strip().lower()


def normalize_mobile(raw):
    """
    Strip non-digits, drop leading 63 or 0, return last 10 digits.
    Returns '' if fewer than 10 digits (ambiguous — we refuse to match).
    """
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) < 10:
        return ""
    # Take the last 10 digits — handles '63xxx', '0xxx', '+63xxx', 'xxx' uniformly
    return digits[-10:]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sync_payments.py -v`
Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/sync-payments.py tests/test_sync_payments.py
git commit -m "feat(sync): add email and mobile normalizers with tests"
```

---

## Task 5: TDD — Tier parser

**Files:**
- Modify: `api/sync-payments.py`
- Test: `tests/test_sync_payments.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_sync_payments.py`:

```python
# ---------- parse_tier ----------

def test_parse_tier_from_product_with_pipe():
    assert sp.parse_tier("THE NEW BUSINESS NORMAL | VIP") == "VIP"

def test_parse_tier_regular():
    assert sp.parse_tier("THE NEW BUSINESS NORMAL | Regular") == "Regular"

def test_parse_tier_early_bird():
    assert sp.parse_tier("BUSINESS UNLOCKED | Early Bird") == "Early Bird"

def test_parse_tier_no_pipe_falls_back_to_whole_string():
    assert sp.parse_tier("VIP") == "VIP"

def test_parse_tier_none_returns_empty():
    assert sp.parse_tier(None) == ""

def test_parse_tier_strips_whitespace():
    assert sp.parse_tier("  BUSINESS UNLOCKED  |  VIP  ") == "VIP"
```

- [ ] **Step 2: Run — expect failure**

Run: `pytest tests/test_sync_payments.py -v -k parse_tier`
Expected: `AttributeError: module 'sync_payments' has no attribute 'parse_tier'`.

- [ ] **Step 3: Add `parse_tier` to `api/sync-payments.py`**

Append under the normalizers section:

```python
def parse_tier(raw_product):
    """
    Extract tier from a product label like 'BUSINESS UNLOCKED | VIP'.
    Falls back to the whole string if no '|' is present.
    Returns '' for None.
    """
    if not raw_product:
        return ""
    parts = str(raw_product).split("|")
    return parts[-1].strip()
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/test_sync_payments.py -v -k parse_tier`
Expected: all 6 tier tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/sync-payments.py tests/test_sync_payments.py
git commit -m "feat(sync): add tier parser with tests"
```

---

## Task 6: TDD — Row parser (Scale Your Org row → dict)

The Scale Your Org row format (headerless, 17 columns based on the sample):

```
[0]  event_type             purchase.success
[1]  status                 success
[2]  full_name              Wynes Ramos
[3]  email                  wyne_ramos@yahoo.com
[4]  mobile                 639178334375
[5]  product                THE NEW BUSINESS NORMAL | VIP
[6]  amount                 4999.98
[7]  quantity               1
[8]  total                  4999.98
[9]  txn_id                 TXN-1775957887846-u6p9pzf4x
[10] txn_id_dup             TXN-1775957887846-u6p9pzf4x
[11] internal_id            69daf781fc29a42382638a1f
[12] payment_provider       xendit
[13] payment_type           full
[14] payment_status_raw     FULLY_PAID
[15] paid_at                2026-04-12T01:39:45.555Z
[16] status_final           PAID
```

**Files:**
- Modify: `api/sync-payments.py`
- Test: `tests/test_sync_payments.py`

- [ ] **Step 1: Append failing tests**

```python
# ---------- parse_row ----------

SAMPLE_ROW = [
    "purchase.success",
    "success",
    "Wynes Ramos",
    "wyne_ramos@yahoo.com",
    "639178334375",
    "THE NEW BUSINESS NORMAL | VIP",
    "4999.98",
    "1",
    "4999.98",
    "TXN-1775957887846-u6p9pzf4x",
    "TXN-1775957887846-u6p9pzf4x",
    "69daf781fc29a42382638a1f",
    "xendit",
    "full",
    "FULLY_PAID",
    "2026-04-12T01:39:45.555Z",
    "PAID",
]

def test_parse_row_full_sample():
    result = sp.parse_row(SAMPLE_ROW)
    assert result["transaction_id"] == "TXN-1775957887846-u6p9pzf4x"
    assert result["email"] == "wyne_ramos@yahoo.com"
    assert result["mobile"] == "9178334375"
    assert result["full_name"] == "Wynes Ramos"
    assert result["tier"] == "VIP"
    assert result["amount"] == 4999.98
    assert result["quantity"] == 1
    assert result["total"] == 4999.98
    assert result["payment_provider"] == "xendit"
    assert result["payment_status"] == "FULLY_PAID"
    assert result["paid_at"] == "2026-04-12T01:39:45.555Z"
    assert result["raw_row"] == SAMPLE_ROW

def test_parse_row_short_row_returns_none():
    # Defensive: if Scale Your Org changes schema, skip instead of crashing
    assert sp.parse_row(["only", "three", "cols"]) is None

def test_parse_row_missing_txn_id_returns_none():
    row = list(SAMPLE_ROW)
    row[9] = ""
    assert sp.parse_row(row) is None

def test_parse_row_bad_amount_defaults_to_zero():
    row = list(SAMPLE_ROW)
    row[6] = "not-a-number"
    row[7] = ""
    row[8] = ""
    result = sp.parse_row(row)
    assert result["amount"] == 0.0
    assert result["quantity"] == 0
    assert result["total"] == 0.0
```

- [ ] **Step 2: Run — expect failure**

Run: `pytest tests/test_sync_payments.py -v -k parse_row`

- [ ] **Step 3: Implement `parse_row`**

Append to `api/sync-payments.py`:

```python
# Column indexes for Scale Your Org row layout.
# Documented in docs/sync-setup.md. Changes here must also update the sample
# in tests/test_sync_payments.py.
_COL_FULL_NAME = 2
_COL_EMAIL = 3
_COL_MOBILE = 4
_COL_PRODUCT = 5
_COL_AMOUNT = 6
_COL_QUANTITY = 7
_COL_TOTAL = 8
_COL_TXN_ID = 9
_COL_PROVIDER = 12
_COL_PAYMENT_STATUS = 14
_COL_PAID_AT = 15
_MIN_COLS = 16


def _safe_float(val):
    try:
        return float(val) if val not in ("", None) else 0.0
    except (ValueError, TypeError):
        return 0.0


def _safe_int(val):
    try:
        return int(float(val)) if val not in ("", None) else 0
    except (ValueError, TypeError):
        return 0


def parse_row(row):
    """
    Parse one Scale Your Org row into a purchase dict.
    Returns None if the row is too short or missing a transaction_id.
    """
    if not row or len(row) < _MIN_COLS:
        return None

    txn_id = str(row[_COL_TXN_ID]).strip() if row[_COL_TXN_ID] else ""
    if not txn_id:
        return None

    return {
        "transaction_id":   txn_id,
        "full_name":        str(row[_COL_FULL_NAME]).strip() if row[_COL_FULL_NAME] else "",
        "email":            normalize_email(row[_COL_EMAIL]),
        "mobile":           normalize_mobile(row[_COL_MOBILE]),
        "tier":             parse_tier(row[_COL_PRODUCT]),
        "amount":           _safe_float(row[_COL_AMOUNT]),
        "quantity":         _safe_int(row[_COL_QUANTITY]),
        "total":            _safe_float(row[_COL_TOTAL]),
        "payment_provider": str(row[_COL_PROVIDER]).strip().lower() if row[_COL_PROVIDER] else "",
        "payment_status":   str(row[_COL_PAYMENT_STATUS]).strip().upper() if row[_COL_PAYMENT_STATUS] else "",
        "paid_at":          str(row[_COL_PAID_AT]).strip() if row[_COL_PAID_AT] else None,
        "raw_row":          list(row),
    }
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/test_sync_payments.py -v`
Expected: all tests pass (19 total).

- [ ] **Step 5: Commit**

```bash
git add api/sync-payments.py tests/test_sync_payments.py
git commit -m "feat(sync): add row parser for Scale Your Org format"
```

---

## Task 7: TDD — Matcher (purchase → participant_id)

**Files:**
- Modify: `api/sync-payments.py`
- Test: `tests/test_sync_payments.py`

The matcher takes:
- A purchase (with normalized `email`, `mobile`, `paid_at`)
- A list of participant rows (with `id`, `email`, `mobile_number`, `submitted_at`, UTM fields)

It returns `(participant_id_or_None, match_method)` where match_method is `'email'`, `'mobile'`, or `'direct'`.

Tie-break: if multiple participants match, pick the most recent whose `submitted_at < paid_at`. If all submissions are AFTER the payment, pick the most recent overall (handles the "paid first, form later" case — we still attribute to the closest form).

- [ ] **Step 1: Append failing tests**

```python
# ---------- match_purchase_to_participant ----------

PAID_AT = "2026-04-12T10:00:00Z"

def _pt(pid, email="", mobile="", submitted_at="", utm_source=None):
    return {
        "id": pid,
        "email": email,
        "mobile_number": mobile,
        "submitted_at": submitted_at,
        "utm_source": utm_source,
        "utm_medium": None,
        "utm_campaign": None,
        "utm_content": None,
    }

def test_match_by_email():
    participants = [
        _pt("p1", email="wyne_ramos@yahoo.com", submitted_at="2026-04-11T12:00:00Z", utm_source="pancake"),
    ]
    pid, method = sp.match_purchase_to_participant(
        {"email": "wyne_ramos@yahoo.com", "mobile": "9178334375", "paid_at": PAID_AT},
        participants,
    )
    assert pid == "p1"
    assert method == "email"

def test_match_falls_back_to_mobile():
    participants = [
        _pt("p1", email="different@example.com", mobile="9178334375",
            submitted_at="2026-04-11T12:00:00Z", utm_source="rtd"),
    ]
    pid, method = sp.match_purchase_to_participant(
        {"email": "wyne_ramos@yahoo.com", "mobile": "9178334375", "paid_at": PAID_AT},
        participants,
    )
    assert pid == "p1"
    assert method == "mobile"

def test_match_no_match_returns_direct():
    participants = [
        _pt("p1", email="someone-else@example.com", mobile="9000000000",
            submitted_at="2026-04-11T12:00:00Z"),
    ]
    pid, method = sp.match_purchase_to_participant(
        {"email": "wyne_ramos@yahoo.com", "mobile": "9178334375", "paid_at": PAID_AT},
        participants,
    )
    assert pid is None
    assert method == "direct"

def test_match_multiple_picks_most_recent_before_payment():
    participants = [
        _pt("p_old", email="x@example.com", submitted_at="2026-04-05T12:00:00Z", utm_source="old"),
        _pt("p_new", email="x@example.com", submitted_at="2026-04-11T12:00:00Z", utm_source="new"),
    ]
    pid, _ = sp.match_purchase_to_participant(
        {"email": "x@example.com", "mobile": "", "paid_at": PAID_AT},
        participants,
    )
    assert pid == "p_new"

def test_match_all_after_payment_picks_most_recent_overall():
    # Paid first, form later scenario
    participants = [
        _pt("p1", email="x@example.com", submitted_at="2026-04-13T09:00:00Z", utm_source="late"),
        _pt("p2", email="x@example.com", submitted_at="2026-04-14T09:00:00Z", utm_source="later"),
    ]
    pid, _ = sp.match_purchase_to_participant(
        {"email": "x@example.com", "mobile": "", "paid_at": PAID_AT},
        participants,
    )
    assert pid == "p2"

def test_match_empty_email_and_mobile_returns_direct():
    pid, method = sp.match_purchase_to_participant(
        {"email": "", "mobile": "", "paid_at": PAID_AT}, []
    )
    assert pid is None
    assert method == "direct"
```

- [ ] **Step 2: Run — expect failure**

Run: `pytest tests/test_sync_payments.py -v -k match_`

- [ ] **Step 3: Implement `match_purchase_to_participant`**

Append to `api/sync-payments.py`:

```python
def _pick_best_candidate(candidates, paid_at):
    """
    Given a list of participant dicts that all match on email or mobile,
    prefer the most recent submitted_at < paid_at.
    If all submissions are after paid_at, return the most recent overall.
    """
    if not candidates:
        return None

    def key(p):
        return p.get("submitted_at") or ""

    before = [p for p in candidates if paid_at and key(p) < paid_at]
    pool = before if before else candidates
    return max(pool, key=key)


def match_purchase_to_participant(purchase, participants):
    """
    Returns (participant_id, match_method) where match_method is
    'email', 'mobile', or 'direct'.
    `participants` is a list of dicts (already fetched from Supabase) containing
    at minimum: id, email, mobile_number, submitted_at.
    """
    email = purchase.get("email") or ""
    mobile = purchase.get("mobile") or ""
    paid_at = purchase.get("paid_at") or ""

    if email:
        hits = [p for p in participants if normalize_email(p.get("email")) == email]
        chosen = _pick_best_candidate(hits, paid_at)
        if chosen:
            return chosen["id"], "email"

    if mobile:
        hits = [p for p in participants if normalize_mobile(p.get("mobile_number")) == mobile]
        chosen = _pick_best_candidate(hits, paid_at)
        if chosen:
            return chosen["id"], "mobile"

    return None, "direct"
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/test_sync_payments.py -v`
Expected: all tests pass (25 total).

- [ ] **Step 5: Commit**

```bash
git add api/sync-payments.py tests/test_sync_payments.py
git commit -m "feat(sync): add participant matcher with tie-break logic"
```

---

## Task 8: Sheets API reader with forced refresh

The bridge sheet's IMPORTRANGE only refreshes when the sheet is actively open or touched. Opening it programmatically via the Sheets API triggers a recalculation.

**Files:**
- Modify: `api/sync-payments.py`

No unit test for this — it requires network. Manual verification in Task 13.

- [ ] **Step 1: Add Sheets reader to `api/sync-payments.py`**

Append:

```python
# ---------------------------------------------------------------------------
# Google Sheets reader
# ---------------------------------------------------------------------------

def _sheets_service():
    """Build an authenticated Sheets API client from the service account JSON."""
    # Lazy imports so unit tests don't require google libraries installed
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    raw_json = os.environ.get("GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON")
    if not raw_json:
        raise EnvironmentError("Missing GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON")

    info = json.loads(raw_json)
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    # cache_discovery=False avoids filesystem writes on serverless
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def read_bridge_sheet():
    """
    Read all rows from the bridge sheet. Opening it via the API forces
    IMPORTRANGE to recalculate. Returns a list of rows (each a list of strings).
    Header rows, if any, are returned as-is — the row parser skips short rows.
    """
    sheet_id = os.environ.get("BRIDGE_SHEET_ID")
    tab = os.environ.get("BRIDGE_SHEET_TAB", "payments")
    if not sheet_id:
        raise EnvironmentError("Missing BRIDGE_SHEET_ID")

    svc = _sheets_service()

    # Force refresh: a get() on the spreadsheet triggers IMPORTRANGE re-evaluation.
    # The sheets.values().get() that follows then reads the refreshed values.
    svc.spreadsheets().get(spreadsheetId=sheet_id).execute()

    # Read A:Q (17 columns — matches Scale Your Org row width)
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{tab}!A:Q",
    ).execute()

    return result.get("values", [])
```

- [ ] **Step 2: Commit**

```bash
git add api/sync-payments.py
git commit -m "feat(sync): add Sheets API reader with forced IMPORTRANGE refresh"
```

---

## Task 9: Supabase PostgREST client (upsert purchases, fetch participants, write sync log)

Following the pattern in `api/report.py` — raw `urllib` against PostgREST. No Supabase SDK.

**Files:**
- Modify: `api/sync-payments.py`

- [ ] **Step 1: Add Supabase helpers**

Append to `api/sync-payments.py`:

```python
# ---------------------------------------------------------------------------
# Supabase PostgREST helpers (stdlib only, matches api/report.py pattern)
# ---------------------------------------------------------------------------

import urllib.request
import urllib.error

PURCHASES_TABLE = "new_business_normal_purchases"
PARTICIPANTS_TABLE = "new_business_normal_participants"
SYNC_LOG_TABLE = "new_business_normal_sync_log"


def _supabase_env():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    return url.rstrip("/"), key


def _supabase_request(method, path, body=None, extra_headers=None):
    """Generic PostgREST request. Returns parsed JSON (list or dict) or [] on 204."""
    supabase_url, key = _supabase_env()
    url = f"{supabase_url}/rest/v1/{path.lstrip('/')}"

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("apikey", key)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    if extra_headers:
        for k, v in extra_headers.items():
            req.add_header(k, v)

    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
        if not raw:
            return []
        return json.loads(raw)


def supabase_upsert_purchase(purchase, participant_id, match_method, utm_fields):
    """
    Upsert one row into new_business_normal_purchases by transaction_id.
    utm_fields is a dict with utm_source/medium/campaign/content (or None).
    """
    row = {
        "transaction_id":   purchase["transaction_id"],
        "email":            purchase["email"],
        "mobile":           purchase["mobile"],
        "full_name":        purchase["full_name"],
        "tier":             purchase["tier"],
        "amount":           purchase["amount"],
        "quantity":         purchase["quantity"],
        "total":            purchase["total"],
        "payment_provider": purchase["payment_provider"],
        "payment_status":   purchase["payment_status"],
        "paid_at":          purchase["paid_at"],
        "participant_id":   participant_id,
        "match_method":     match_method,
        "utm_source":       utm_fields.get("utm_source"),
        "utm_medium":       utm_fields.get("utm_medium"),
        "utm_campaign":     utm_fields.get("utm_campaign"),
        "utm_content":      utm_fields.get("utm_content"),
        "raw_row":          purchase["raw_row"],
    }

    # PostgREST upsert: POST with Prefer: resolution=merge-duplicates
    _supabase_request(
        "POST",
        PURCHASES_TABLE,
        body=row,
        extra_headers={
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )


def supabase_fetch_participants_by_contacts(emails, mobiles):
    """
    Fetch participants whose email OR mobile_number appears in the given sets.
    Returns a list of participant dicts.
    """
    if not emails and not mobiles:
        return []

    # PostgREST `or=` filter. Values must be comma-joined and URL-safe.
    from urllib.parse import quote

    clauses = []
    if emails:
        clauses.append(f"email.in.({','.join(quote(e) for e in emails)})")
    if mobiles:
        # We match participant.mobile_number by its *normalized* form.
        # Since we can't run a function server-side, we overfetch candidates
        # by the raw mobile_number containing the last 10 digits, then
        # normalize in Python.
        clauses.append(
            "or(" + ",".join(f"mobile_number.ilike.*{m}" for m in mobiles) + ")"
        )
    filter_expr = "or=(" + ",".join(clauses) + ")" if len(clauses) > 1 else clauses[0]

    path = (
        f"{PARTICIPANTS_TABLE}"
        f"?select=id,email,mobile_number,submitted_at,utm_source,utm_medium,utm_campaign,utm_content"
        f"&{filter_expr}"
    )
    return _supabase_request("GET", path) or []


def supabase_fetch_unmatched_purchases(days=7):
    """Fetch purchases with NULL participant_id and paid_at within N days."""
    import datetime
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=days)).isoformat()
    path = (
        f"{PURCHASES_TABLE}"
        f"?select=transaction_id,email,mobile,paid_at"
        f"&participant_id=is.null"
        f"&paid_at=gte.{cutoff}"
    )
    return _supabase_request("GET", path) or []


def supabase_update_purchase_match(transaction_id, participant_id, match_method, utm_fields):
    """PATCH a purchase to attach it to a participant with UTM attribution."""
    from urllib.parse import quote
    body = {
        "participant_id": participant_id,
        "match_method":   match_method,
        "utm_source":     utm_fields.get("utm_source"),
        "utm_medium":     utm_fields.get("utm_medium"),
        "utm_campaign":   utm_fields.get("utm_campaign"),
        "utm_content":    utm_fields.get("utm_content"),
    }
    path = f"{PURCHASES_TABLE}?transaction_id=eq.{quote(transaction_id)}"
    _supabase_request(
        "PATCH",
        path,
        body=body,
        extra_headers={"Prefer": "return=minimal"},
    )


def supabase_write_sync_log(log):
    """Insert one audit row. `log` must include started_at, finished_at, counts, errors, success."""
    _supabase_request(
        "POST",
        SYNC_LOG_TABLE,
        body=log,
        extra_headers={"Prefer": "return=minimal"},
    )
```

- [ ] **Step 2: Commit**

```bash
git add api/sync-payments.py
git commit -m "feat(sync): add Supabase PostgREST helpers for purchases, participants, sync_log"
```

---

## Task 10: TDD — Orchestrator (`run_sync` pulling it all together)

`run_sync` is the top-level function. Core logic is decomposable and testable via dependency injection: we pass `read_rows` and supabase helpers as arguments so unit tests can stub them.

**Files:**
- Modify: `api/sync-payments.py`
- Test: `tests/test_sync_payments.py`

- [ ] **Step 1: Append failing tests**

```python
# ---------- run_sync (orchestrator) ----------

class _FakeSupabase:
    """In-memory stand-in for the Supabase helpers."""
    def __init__(self, participants=None, unmatched=None):
        self.participants = participants or []
        self.unmatched = unmatched or []
        self.upserted = []
        self.patched = []
        self.logs = []

    def upsert(self, purchase, participant_id, match_method, utm_fields):
        self.upserted.append({
            "purchase": purchase, "participant_id": participant_id,
            "method": match_method, "utm": utm_fields,
        })

    def fetch_participants(self, emails, mobiles):
        hits = []
        for p in self.participants:
            if (p.get("email") in emails
                    or sp.normalize_mobile(p.get("mobile_number")) in mobiles):
                hits.append(p)
        return hits

    def fetch_unmatched(self, days=7):
        return list(self.unmatched)

    def update_match(self, txn_id, pid, method, utm):
        self.patched.append({"txn_id": txn_id, "pid": pid, "method": method, "utm": utm})

    def write_log(self, log):
        self.logs.append(log)


def test_run_sync_upserts_matched_purchase_with_utm():
    fake = _FakeSupabase(participants=[
        _pt("p1", email="wyne_ramos@yahoo.com", submitted_at="2026-04-11T12:00:00Z",
            utm_source="pancake"),
    ])
    rows = [list(SAMPLE_ROW)]

    result = sp.run_sync(
        read_rows=lambda: rows,
        upsert=fake.upsert,
        fetch_participants=fake.fetch_participants,
        fetch_unmatched=fake.fetch_unmatched,
        update_match=fake.update_match,
        write_log=fake.write_log,
    )

    assert len(fake.upserted) == 1
    assert fake.upserted[0]["method"] == "email"
    assert fake.upserted[0]["utm"]["utm_source"] == "pancake"
    assert result["rows_upserted"] == 1
    assert result["rows_matched"] == 1
    assert result["rows_unmatched"] == 0
    assert result["success"] is True


def test_run_sync_unmatched_purchase_marked_direct():
    fake = _FakeSupabase(participants=[])
    rows = [list(SAMPLE_ROW)]

    sp.run_sync(
        read_rows=lambda: rows,
        upsert=fake.upsert,
        fetch_participants=fake.fetch_participants,
        fetch_unmatched=fake.fetch_unmatched,
        update_match=fake.update_match,
        write_log=fake.write_log,
    )

    assert fake.upserted[0]["method"] == "direct"
    assert fake.upserted[0]["utm"] == {
        "utm_source": None, "utm_medium": None, "utm_campaign": None, "utm_content": None,
    }


def test_run_sync_rematches_unmatched_purchases():
    fake = _FakeSupabase(
        participants=[
            _pt("p1", email="late@example.com", submitted_at="2026-04-13T09:00:00Z",
                utm_source="gencys"),
        ],
        unmatched=[
            {"transaction_id": "TXN-OLD", "email": "late@example.com",
             "mobile": "", "paid_at": "2026-04-12T10:00:00Z"},
        ],
    )

    sp.run_sync(
        read_rows=lambda: [],
        upsert=fake.upsert,
        fetch_participants=fake.fetch_participants,
        fetch_unmatched=fake.fetch_unmatched,
        update_match=fake.update_match,
        write_log=fake.write_log,
    )

    assert len(fake.patched) == 1
    assert fake.patched[0]["txn_id"] == "TXN-OLD"
    assert fake.patched[0]["method"] == "email"
    assert fake.patched[0]["utm"]["utm_source"] == "gencys"


def test_run_sync_skips_malformed_rows_and_records_errors():
    fake = _FakeSupabase(participants=[])
    rows = [
        ["only", "two"],              # too short → skipped
        list(SAMPLE_ROW),              # valid
    ]

    result = sp.run_sync(
        read_rows=lambda: rows,
        upsert=fake.upsert,
        fetch_participants=fake.fetch_participants,
        fetch_unmatched=fake.fetch_unmatched,
        update_match=fake.update_match,
        write_log=fake.write_log,
    )

    assert result["rows_read"] == 2
    assert result["rows_upserted"] == 1
    assert result["success"] is True


def test_run_sync_writes_audit_log():
    fake = _FakeSupabase()
    sp.run_sync(
        read_rows=lambda: [],
        upsert=fake.upsert,
        fetch_participants=fake.fetch_participants,
        fetch_unmatched=fake.fetch_unmatched,
        update_match=fake.update_match,
        write_log=fake.write_log,
    )
    assert len(fake.logs) == 1
    log = fake.logs[0]
    assert "started_at" in log and "finished_at" in log
    assert log["success"] is True
```

- [ ] **Step 2: Run — expect failure**

Run: `pytest tests/test_sync_payments.py -v -k run_sync`

- [ ] **Step 3: Implement `run_sync`**

Append to `api/sync-payments.py`:

```python
# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _iso_now():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _utm_from_participant(p):
    return {
        "utm_source":   p.get("utm_source"),
        "utm_medium":   p.get("utm_medium"),
        "utm_campaign": p.get("utm_campaign"),
        "utm_content":  p.get("utm_content"),
    }


_EMPTY_UTM = {
    "utm_source": None,
    "utm_medium": None,
    "utm_campaign": None,
    "utm_content": None,
}


def run_sync(
    read_rows,
    upsert,
    fetch_participants,
    fetch_unmatched,
    update_match,
    write_log,
):
    """
    Execute one sync cycle. All I/O is injected so this is unit-testable.
    Returns a dict with counts + success flag. Also writes an audit log row.
    """
    started_at = _iso_now()
    errors = []
    rows_read = 0
    rows_upserted = 0
    rows_matched = 0
    rows_unmatched = 0

    try:
        # ---- Phase 1: read + parse ----
        raw_rows = read_rows()
        rows_read = len(raw_rows)

        parsed = []
        for r in raw_rows:
            try:
                purchase = parse_row(r)
                if purchase is not None:
                    parsed.append(purchase)
            except Exception as exc:  # noqa: BLE001
                errors.append({"phase": "parse", "error": str(exc), "row_preview": str(r)[:120]})

        # ---- Phase 2: batch fetch candidate participants ----
        emails = {p["email"] for p in parsed if p["email"]}
        mobiles = {p["mobile"] for p in parsed if p["mobile"]}
        participants = fetch_participants(emails, mobiles)

        # ---- Phase 3: match + upsert each purchase ----
        for purchase in parsed:
            try:
                pid, method = match_purchase_to_participant(purchase, participants)
                if pid:
                    matched_p = next(p for p in participants if p["id"] == pid)
                    utm = _utm_from_participant(matched_p)
                    rows_matched += 1
                else:
                    utm = dict(_EMPTY_UTM)
                upsert(purchase, pid, method, utm)
                rows_upserted += 1
                if not pid:
                    rows_unmatched += 1
            except Exception as exc:  # noqa: BLE001
                errors.append({
                    "phase": "upsert",
                    "error": str(exc),
                    "txn_id": purchase.get("transaction_id"),
                })

        # ---- Phase 4: re-match older unmatched purchases ----
        unmatched = fetch_unmatched(days=7)
        if unmatched:
            r_emails = {u.get("email") for u in unmatched if u.get("email")}
            r_mobiles = {u.get("mobile") for u in unmatched if u.get("mobile")}
            rematch_pool = fetch_participants(r_emails, r_mobiles) if (r_emails or r_mobiles) else []
            for u in unmatched:
                try:
                    pid, method = match_purchase_to_participant(u, rematch_pool)
                    if pid:
                        matched_p = next(p for p in rematch_pool if p["id"] == pid)
                        update_match(u["transaction_id"], pid, method, _utm_from_participant(matched_p))
                        rows_matched += 1
                        rows_unmatched = max(0, rows_unmatched - 1)
                except Exception as exc:  # noqa: BLE001
                    errors.append({
                        "phase": "rematch",
                        "error": str(exc),
                        "txn_id": u.get("transaction_id"),
                    })

        success = len(errors) == 0

    except Exception as exc:  # noqa: BLE001
        errors.append({"phase": "top_level", "error": str(exc)})
        success = False

    finished_at = _iso_now()

    log = {
        "started_at": started_at,
        "finished_at": finished_at,
        "rows_read": rows_read,
        "rows_upserted": rows_upserted,
        "rows_matched": rows_matched,
        "rows_unmatched": rows_unmatched,
        "errors": errors if errors else None,
        "success": success,
    }
    try:
        write_log(log)
    except Exception:  # noqa: BLE001
        pass  # never fail the sync just because the log write failed

    return log
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/test_sync_payments.py -v`
Expected: all tests pass (30 total).

- [ ] **Step 5: Commit**

```bash
git add api/sync-payments.py tests/test_sync_payments.py
git commit -m "feat(sync): add orchestrator with phase separation and error capture"
```

---

## Task 11: Vercel HTTP handler + cron secret check

**Files:**
- Modify: `api/sync-payments.py`
- Modify: `vercel.json`
- Modify: `.env.example`

- [ ] **Step 1: Add the `handler` class**

Append to `api/sync-payments.py`:

```python
# ---------------------------------------------------------------------------
# Vercel serverless handler
# ---------------------------------------------------------------------------

def _send_json(h, status, payload):
    body = json.dumps(payload).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def _is_authorized_cron_request(h):
    """
    Vercel cron sends `Authorization: Bearer <CRON_SECRET>`.
    If CRON_SECRET is unset, allow — useful for local testing only.
    """
    expected = os.environ.get("CRON_SECRET")
    if not expected:
        return True
    auth = h.headers.get("Authorization", "")
    return auth == f"Bearer {expected}"


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if not _is_authorized_cron_request(self):
            _send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            result = run_sync(
                read_rows=read_bridge_sheet,
                upsert=supabase_upsert_purchase,
                fetch_participants=supabase_fetch_participants_by_contacts,
                fetch_unmatched=supabase_fetch_unmatched_purchases,
                update_match=supabase_update_purchase_match,
                write_log=supabase_write_sync_log,
            )
            _send_json(self, 200, result)
        except Exception as exc:  # noqa: BLE001
            _send_json(self, 500, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, format, *args):
        pass
```

- [ ] **Step 2: Add the cron entry to `vercel.json`**

Open `vercel.json`. Add a new top-level `crons` key. Insert it after the `headers` array. The final file should look like:

```json
{
  "trailingSlash": false,
  "redirects": [
    { "source": "/", "destination": "/the-new-business-normal", "permanent": false }
  ],
  "rewrites": [
    { "source": "/api/(.*)", "destination": "/api/$1" },
    { "source": "/the-new-business-normal", "destination": "/index.html" },
    { "source": "/the-new-business-normal/sponsors", "destination": "/sponsors.html" },
    { "source": "/thank-you", "destination": "/thank-you.html" },
    { "source": "/dashboard", "destination": "/dashboard.html" },
    { "source": "/participant-details", "destination": "/participant-details.html" }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "SAMEORIGIN" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" }
      ]
    }
  ],
  "crons": [
    { "path": "/api/sync-payments", "schedule": "*/15 * * * *" }
  ]
}
```

- [ ] **Step 3: Append CRON_SECRET to `.env.example`**

Append to `.env.example`:

```
# Vercel auto-sets this in production for cron auth. Set locally to test.
CRON_SECRET=
```

- [ ] **Step 4: Commit**

```bash
git add api/sync-payments.py vercel.json .env.example
git commit -m "feat(sync): add Vercel handler and 15-min cron entry"
```

---

## Task 12: Extend `api/report.py` — new dashboard endpoints

The existing `report.py` has actions that reference tables named `sales`, `page_visits`, and `clicks` (lines 110-114, 141-146, 203-207, 246-249). These names don't match the actual Supabase tables (`new_business_normal_*`). We fix those while adding the new actions.

**Files:**
- Modify: `api/report.py`

- [ ] **Step 1: Rename table references at the top of `report.py`**

Add these module-level constants near the top of `api/report.py`, right after the imports (before the "Helpers" section):

```python
# Actual Supabase table names (shared prefix for this event)
TABLE_VISITS = "new_business_normal_visits"
TABLE_CLICKS = "new_business_normal_clicks"
TABLE_PARTICIPANTS = "new_business_normal_participants"
TABLE_PURCHASES = "new_business_normal_purchases"
TABLE_SYNC_LOG = "new_business_normal_sync_log"
```

- [ ] **Step 2: Replace the existing stale table references**

In `api/report.py`, find and replace these literal strings (be precise — only inside the supabase_get calls):

- `"page_visits?select=id"` → `f"{TABLE_VISITS}?select=id"`
- `"clicks?select=id"` → `f"{TABLE_CLICKS}?select=id"`
- `"sales?select=id,amount&payment_status=eq.paid"` → `f"{TABLE_PURCHASES}?select=transaction_id,total&payment_status=in.(PAID,FULLY_PAID)"`
- `"page_visits?select=utm_source"` → `f"{TABLE_VISITS}?select=utm_source"`
- `"clicks?select=utm_source"` → `f"{TABLE_CLICKS}?select=utm_source"`
- `"sales?select=utm_source,amount,ticket_tier&payment_status=eq.paid"` → `f"{TABLE_PURCHASES}?select=utm_source,total,tier&payment_status=in.(PAID,FULLY_PAID)"`
- `"sales?select=ticket_tier,amount&payment_status=eq.paid"` → `f"{TABLE_PURCHASES}?select=tier,total&payment_status=in.(PAID,FULLY_PAID)"`
- `"clicks?select=clicked_at&clicked_at=gte." + _thirty_days_ago()` → `f"{TABLE_CLICKS}?select=clicked_at&clicked_at=gte.{_thirty_days_ago()}"`

Then update field references to match the renamed columns in the aggregators:
- In `handle_summary`: change `sum(row.get("amount", 0) or 0 for row in sales)` to `sum(row.get("total", 0) or 0 for row in sales)`
- In `handle_by_utm`: change `row.get("amount", 0) or 0` to `row.get("total", 0) or 0`
- In `handle_by_utm`: change `row.get("ticket_tier") or "unknown"` to `row.get("tier") or "unknown"`
- In `handle_by_tier`: change `row.get("ticket_tier") or "unknown"` to `row.get("tier") or "unknown"`
- In `handle_by_tier`: change `row.get("amount", 0) or 0` to `row.get("total", 0) or 0`
- In `handle_by_utm`: update the fixed tier keys in the response dict from `tiers.get("early_bird", 0)`, `tiers.get("regular", 0)`, `tiers.get("vip", 0)` to `tiers.get("Early Bird", 0)`, `tiers.get("Regular", 0)`, `tiers.get("VIP", 0)` (matches what Scale Your Org sends)
- In `handle_by_tier`: change `ordered_tiers = ["early_bird", "regular", "vip"]` to `ordered_tiers = ["Early Bird", "Regular", "VIP"]`

- [ ] **Step 3: Add the 5 new action handlers**

Insert before the `class handler(BaseHTTPRequestHandler):` line in `api/report.py`:

```python
def handle_revenue_by_utm(h, supabase_url, service_key):
    """GET /api/report?action=revenue_by_utm — ₱ per UTM source"""
    if not check_auth(h):
        return
    try:
        purchases = supabase_get(
            supabase_url, service_key,
            f"{TABLE_PURCHASES}?select=utm_source,total&payment_status=in.(PAID,FULLY_PAID)"
        )
    except urllib.error.URLError as exc:
        _send_json(h, 502, {"error": f"Supabase request failed: {exc}"})
        return

    def norm(v): return v if v else "direct"
    buckets = defaultdict(float)
    for row in purchases:
        buckets[norm(row.get("utm_source"))] += float(row.get("total", 0) or 0)

    result = [{"utm_source": k, "revenue": round(v, 2)}
              for k, v in sorted(buckets.items(), key=lambda kv: kv[1], reverse=True)]
    _send_json(h, 200, result)


def handle_tickets_by_utm_tier(h, supabase_url, service_key):
    """GET /api/report?action=tickets_by_utm_tier — stacked bar data"""
    if not check_auth(h):
        return
    try:
        purchases = supabase_get(
            supabase_url, service_key,
            f"{TABLE_PURCHASES}?select=utm_source,tier&payment_status=in.(PAID,FULLY_PAID)"
        )
    except urllib.error.URLError as exc:
        _send_json(h, 502, {"error": f"Supabase request failed: {exc}"})
        return

    def norm(v): return v if v else "direct"
    stacks = defaultdict(lambda: {"Early Bird": 0, "Regular": 0, "VIP": 0, "Other": 0})
    for row in purchases:
        src = norm(row.get("utm_source"))
        tier = row.get("tier") or "Other"
        if tier not in ("Early Bird", "Regular", "VIP"):
            tier = "Other"
        stacks[src][tier] += 1

    result = [{"utm_source": src, **counts}
              for src, counts in sorted(stacks.items(),
                  key=lambda kv: sum(kv[1].values()), reverse=True)]
    _send_json(h, 200, result)


def handle_conversion_by_utm(h, supabase_url, service_key):
    """
    GET /api/report?action=conversion_by_utm
    Returns visits, participants, purchases per UTM source with % conversion rates.
    """
    if not check_auth(h):
        return
    try:
        visits = supabase_get(supabase_url, service_key,
            f"{TABLE_VISITS}?select=utm_source")
        participants = supabase_get(supabase_url, service_key,
            f"{TABLE_PARTICIPANTS}?select=utm_source")
        purchases = supabase_get(supabase_url, service_key,
            f"{TABLE_PURCHASES}?select=utm_source&payment_status=in.(PAID,FULLY_PAID)")
    except urllib.error.URLError as exc:
        _send_json(h, 502, {"error": f"Supabase request failed: {exc}"})
        return

    def norm(v): return v if v else "direct"
    v_c = defaultdict(int); p_c = defaultdict(int); b_c = defaultdict(int)
    for r in visits:       v_c[norm(r.get("utm_source"))] += 1
    for r in participants: p_c[norm(r.get("utm_source"))] += 1
    for r in purchases:    b_c[norm(r.get("utm_source"))] += 1

    sources = set(v_c) | set(p_c) | set(b_c)
    def pct(n, d): return round((n / d) * 100, 2) if d else 0

    result = []
    for src in sorted(sources):
        v = v_c[src]; p = p_c[src]; b = b_c[src]
        result.append({
            "utm_source": src,
            "visits": v, "participants": p, "paid": b,
            "visit_to_form_pct": pct(p, v),
            "form_to_paid_pct":  pct(b, p),
            "visit_to_paid_pct": pct(b, v),
        })
    _send_json(h, 200, result)


def handle_recent_payments(h, supabase_url, service_key):
    """GET /api/report?action=recent_payments — last 50 purchases"""
    if not check_auth(h):
        return
    try:
        purchases = supabase_get(
            supabase_url, service_key,
            f"{TABLE_PURCHASES}?select=transaction_id,paid_at,full_name,email,tier,total,utm_source,match_method,payment_status"
            f"&order=paid_at.desc&limit=50"
        )
    except urllib.error.URLError as exc:
        _send_json(h, 502, {"error": f"Supabase request failed: {exc}"})
        return
    _send_json(h, 200, purchases)


def handle_last_sync(h, supabase_url, service_key):
    """GET /api/report?action=last_sync — most recent sync log row"""
    if not check_auth(h):
        return
    try:
        logs = supabase_get(
            supabase_url, service_key,
            f"{TABLE_SYNC_LOG}?select=started_at,finished_at,rows_read,rows_upserted,rows_matched,rows_unmatched,success,errors"
            f"&order=started_at.desc&limit=1"
        )
    except urllib.error.URLError as exc:
        _send_json(h, 502, {"error": f"Supabase request failed: {exc}"})
        return
    _send_json(h, 200, logs[0] if logs else None)
```

- [ ] **Step 4: Wire the new actions into the router**

Inside the `do_GET` method of `class handler`, find the `elif action == "clicks_over_time":` block and add these branches right after it:

```python
        elif action == "revenue_by_utm":
            handle_revenue_by_utm(self, supabase_url, service_key)

        elif action == "tickets_by_utm_tier":
            handle_tickets_by_utm_tier(self, supabase_url, service_key)

        elif action == "conversion_by_utm":
            handle_conversion_by_utm(self, supabase_url, service_key)

        elif action == "recent_payments":
            handle_recent_payments(self, supabase_url, service_key)

        elif action == "last_sync":
            handle_last_sync(self, supabase_url, service_key)
```

Also update the "Unknown action" error message to include the new actions:

```python
            _send_json(self, 400, {
                "error": (
                    f"Unknown action: '{action}'. Valid actions: "
                    "auth, summary, by_utm, by_tier, clicks_over_time, "
                    "revenue_by_utm, tickets_by_utm_tier, conversion_by_utm, "
                    "recent_payments, last_sync"
                )
            })
```

- [ ] **Step 5: Sanity-check `report.py` imports are complete**

`handle_revenue_by_utm` uses `defaultdict` — already imported at top.
No new imports needed.

- [ ] **Step 6: Commit**

```bash
git add api/report.py
git commit -m "feat(report): add 5 new dashboard endpoints + fix stale table names"
```

---

## Task 13: Dashboard UI — KPI cards, new charts, payments table

The existing `admin.html` already has a layout and includes `js/admin.js`. We add a new section for the sales/attribution data and a new JS file to populate it.

First, inspect the current `admin.html` structure to decide where to insert. Read the file and find the `<main>` section.

**Files:**
- Modify: `admin.html`
- Create: `js/admin-sales.js`

- [ ] **Step 1: Read the current admin.html to find the insertion point**

Run: `cat admin.html | head -100`

Find the opening `<main>` tag and the first `<section>` after it. The new section will be inserted **before** the first existing section, so sales/revenue shows at the top.

- [ ] **Step 2: Insert the new section HTML**

Insert this block immediately after the opening `<main>` tag (or at the top of the first `<section>`, whichever makes sense given the existing structure):

```html
<section id="sales-attribution" class="card">
  <header class="card-header">
    <h2>Sales &amp; UTM Attribution</h2>
    <div class="sync-status" id="sync-status">
      <span class="dot" id="sync-dot">•</span>
      <span id="sync-label">Last sync: checking…</span>
    </div>
  </header>

  <!-- KPI strip -->
  <div class="kpi-strip">
    <div class="kpi">
      <div class="kpi-label">Total Revenue</div>
      <div class="kpi-value" id="kpi-revenue">₱0</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Tickets Sold</div>
      <div class="kpi-value" id="kpi-tickets">0</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Visit → Paid</div>
      <div class="kpi-value" id="kpi-conv">0%</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Unmatched</div>
      <div class="kpi-value" id="kpi-unmatched">0</div>
    </div>
  </div>

  <!-- Charts -->
  <div class="chart-grid">
    <div class="chart-cell">
      <h3>Revenue by UTM source</h3>
      <canvas id="chart-revenue-utm" height="220"></canvas>
    </div>
    <div class="chart-cell">
      <h3>Tickets by UTM source × tier</h3>
      <canvas id="chart-tickets-utm-tier" height="220"></canvas>
    </div>
    <div class="chart-cell full-width">
      <h3>Conversion funnel by UTM source</h3>
      <canvas id="chart-conversion-utm" height="260"></canvas>
    </div>
  </div>

  <!-- Recent payments -->
  <div class="recent-payments">
    <h3>Recent payments</h3>
    <div class="table-wrap">
      <table id="table-recent-payments">
        <thead>
          <tr>
            <th>Paid at</th>
            <th>Name</th>
            <th>Email</th>
            <th>Tier</th>
            <th>Amount</th>
            <th>UTM source</th>
            <th>Match</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody><!-- rows inserted by admin-sales.js --></tbody>
      </table>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Add styling**

In `css/style.css`, append at the bottom:

```css
/* Sales & UTM attribution section */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin: 16px 0 24px;
}
.kpi {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px 16px;
}
.kpi-label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; }
.kpi-value { font-size: 28px; font-weight: 700; color: #0d9488; margin-top: 4px; }

.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}
.chart-cell {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px;
}
.chart-cell.full-width { grid-column: 1 / -1; }
.chart-cell h3 { margin: 0 0 12px; font-size: 14px; color: #374151; }

.recent-payments { margin-top: 24px; }
.recent-payments h3 { font-size: 14px; color: #374151; margin: 0 0 8px; }
.table-wrap { overflow-x: auto; border: 1px solid #e5e7eb; border-radius: 10px; }
.table-wrap table { width: 100%; border-collapse: collapse; font-size: 13px; }
.table-wrap th, .table-wrap td {
  padding: 8px 12px; text-align: left; border-bottom: 1px solid #f3f4f6;
}
.table-wrap th { background: #fafaf9; font-weight: 600; color: #6b7280; }

.sync-status { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #6b7280; }
.sync-status .dot { font-size: 18px; line-height: 1; }
.sync-status .dot.ok { color: #10b981; }
.sync-status .dot.err { color: #ef4444; }

@media (max-width: 768px) {
  .chart-grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 4: Include `js/admin-sales.js` in admin.html**

Find the existing `<script src="js/admin.js"></script>` line in `admin.html`. Add this immediately after it:

```html
<script src="js/admin-sales.js"></script>
```

- [ ] **Step 5: Create `js/admin-sales.js`**

```javascript
/**
 * admin-sales.js
 * Populates the Sales & UTM Attribution section of admin.html.
 * Depends on: admin.js defining window.apiFetch (existing).
 */

(function () {
  'use strict';

  var revenueChart = null;
  var ticketsChart = null;
  var conversionChart = null;

  function peso(n) {
    return '₱' + Number(n || 0).toLocaleString('en-PH', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  }

  function ago(iso) {
    if (!iso) return '—';
    var diffMs = Date.now() - new Date(iso).getTime();
    var diffMin = Math.round(diffMs / 60000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return diffMin + 'm ago';
    var diffHr = Math.round(diffMin / 60);
    if (diffHr < 24) return diffHr + 'h ago';
    return Math.round(diffHr / 24) + 'd ago';
  }

  async function loadSyncStatus() {
    try {
      var log = await window.apiFetch('last_sync');
      var dot = document.getElementById('sync-dot');
      var label = document.getElementById('sync-label');
      if (!log) {
        dot.className = 'dot err'; label.textContent = 'No syncs yet';
        return;
      }
      dot.className = 'dot ' + (log.success ? 'ok' : 'err');
      label.textContent = 'Last sync: ' + ago(log.started_at)
        + ' • ' + (log.rows_upserted || 0) + ' payments';
    } catch (err) {
      document.getElementById('sync-dot').className = 'dot err';
      document.getElementById('sync-label').textContent = 'Sync status unavailable';
    }
  }

  async function loadKPIs() {
    var summary = await window.apiFetch('summary');
    document.getElementById('kpi-revenue').textContent = peso(summary.total_revenue);
    document.getElementById('kpi-tickets').textContent = Number(summary.total_sales || 0).toLocaleString();
    document.getElementById('kpi-conv').textContent = (summary.conversion_rate || 0) + '%';

    var recent = await window.apiFetch('recent_payments');
    var unmatched = (recent || []).filter(function (r) { return r.match_method === 'direct'; }).length;
    document.getElementById('kpi-unmatched').textContent = unmatched;

    return recent;
  }

  async function drawRevenueChart() {
    var data = await window.apiFetch('revenue_by_utm');
    var ctx = document.getElementById('chart-revenue-utm').getContext('2d');
    var labels = data.map(function (r) { return r.utm_source; });
    var values = data.map(function (r) { return r.revenue; });
    if (revenueChart) { revenueChart.destroy(); }
    revenueChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{ label: 'Revenue (₱)', data: values, backgroundColor: '#0d9488' }],
      },
      options: {
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: function (c) { return peso(c.parsed.x); } } },
        },
        scales: { x: { ticks: { callback: function (v) { return peso(v); } } } },
      },
    });
  }

  async function drawTicketsChart() {
    var data = await window.apiFetch('tickets_by_utm_tier');
    var ctx = document.getElementById('chart-tickets-utm-tier').getContext('2d');
    var labels = data.map(function (r) { return r.utm_source; });
    if (ticketsChart) { ticketsChart.destroy(); }
    ticketsChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          { label: 'Early Bird', data: data.map(function (r) { return r['Early Bird']; }), backgroundColor: '#f59e0b' },
          { label: 'Regular',    data: data.map(function (r) { return r['Regular']; }),    backgroundColor: '#0d9488' },
          { label: 'VIP',        data: data.map(function (r) { return r['VIP']; }),        backgroundColor: '#7c3aed' },
          { label: 'Other',      data: data.map(function (r) { return r['Other']; }),      backgroundColor: '#9ca3af' },
        ],
      },
      options: {
        responsive: true,
        scales: { x: { stacked: true }, y: { stacked: true, ticks: { precision: 0 } } },
      },
    });
  }

  async function drawConversionChart() {
    var data = await window.apiFetch('conversion_by_utm');
    var ctx = document.getElementById('chart-conversion-utm').getContext('2d');
    var labels = data.map(function (r) { return r.utm_source; });
    if (conversionChart) { conversionChart.destroy(); }
    conversionChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          { label: 'Visits',          data: data.map(function (r) { return r.visits; }),       backgroundColor: '#cbd5e1' },
          { label: 'Filled form',     data: data.map(function (r) { return r.participants; }), backgroundColor: '#94a3b8' },
          { label: 'Paid',            data: data.map(function (r) { return r.paid; }),         backgroundColor: '#0d9488' },
        ],
      },
      options: {
        responsive: true,
        scales: { y: { ticks: { precision: 0 } } },
      },
    });
  }

  function renderPaymentsTable(rows) {
    var tbody = document.querySelector('#table-recent-payments tbody');
    tbody.innerHTML = '';
    (rows || []).forEach(function (r) {
      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + (r.paid_at ? new Date(r.paid_at).toLocaleString('en-PH') : '') + '</td>' +
        '<td>' + escapeHtml(r.full_name || '') + '</td>' +
        '<td>' + escapeHtml(r.email || '') + '</td>' +
        '<td>' + escapeHtml(r.tier || '') + '</td>' +
        '<td>' + peso(r.total) + '</td>' +
        '<td>' + escapeHtml(r.utm_source || 'direct') + '</td>' +
        '<td>' + escapeHtml(r.match_method || '') + '</td>' +
        '<td>' + escapeHtml(r.payment_status || '') + '</td>';
      tbody.appendChild(tr);
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  async function loadAll() {
    try {
      await loadSyncStatus();
      var recent = await loadKPIs();
      renderPaymentsTable(recent);
      await drawRevenueChart();
      await drawTicketsChart();
      await drawConversionChart();
    } catch (err) {
      console.error('[admin-sales] load failed', err);
    }
  }

  // Run after admin.js has authenticated (admin.js dispatches 'admin:authed' on success).
  // Fallback: also run on DOMContentLoaded if the event doesn't fire within 3s.
  var ran = false;
  function runOnce() { if (!ran) { ran = true; loadAll(); } }

  window.addEventListener('admin:authed', runOnce);
  window.addEventListener('DOMContentLoaded', function () {
    setTimeout(runOnce, 3000);
  });
})();
```

- [ ] **Step 6: Make `admin.js` expose `apiFetch` and fire an `admin:authed` event**

Open `js/admin.js`. Locate the `apiFetch` function — currently it's declared with `async function apiFetch(action)` or similar. Right after its declaration, add:

```javascript
window.apiFetch = apiFetch;
```

Locate where the dashboard successfully authenticates (after `action === 'auth'` returns authenticated). Immediately after the code that reveals the main dashboard content, add:

```javascript
window.dispatchEvent(new Event('admin:authed'));
```

If you can't locate the exact insertion point, wrap the first `loadAll()` / `loadSummary()` call (whatever the existing admin.js calls after auth succeeds) with:

```javascript
window.dispatchEvent(new Event('admin:authed'));
```

- [ ] **Step 7: Commit**

```bash
git add admin.html css/style.css js/admin-sales.js js/admin.js
git commit -m "feat(dashboard): add sales/UTM attribution section with KPIs, charts, payments table"
```

---

## Task 14: Manual end-to-end verification

No automated test can cover "did Vercel cron fire and did IMPORTRANGE refresh" — verify by hand after deploy.

- [ ] **Step 1: Run the local test suite one more time**

```bash
source .venv/bin/activate
pytest tests/ -v
```

Expected: all 30 tests pass.

- [ ] **Step 2: Deploy to Vercel**

```bash
vercel --prod
```

Expected: deploy succeeds. Confirm the new cron appears in Vercel dashboard → Settings → Crons.

- [ ] **Step 3: Manually trigger the cron endpoint to confirm it works**

From Vercel dashboard, find the cron and click "Run now" — or hit the endpoint directly with the CRON_SECRET:

```bash
curl -H "Authorization: Bearer $CRON_SECRET" https://<your-domain>/api/sync-payments
```

Expected response: JSON with `success: true`, `rows_read > 0`, `rows_upserted >= 0`.

- [ ] **Step 4: Check the sync log in Supabase**

Via the MCP:
```
mcp__supabase__execute_sql with query:
select * from new_business_normal_sync_log order by started_at desc limit 5;
```

Expected: row exists with success=true and sensible counts.

- [ ] **Step 5: Check purchases are populated**

```
select count(*), count(*) filter (where participant_id is not null) as matched,
       count(*) filter (where match_method='direct') as direct
from new_business_normal_purchases;
```

Expected: counts are non-zero and match what you saw in the Scale Your Org sheet.

- [ ] **Step 6: End-to-end UTM attribution check**

1. Open the sales page with a test UTM: `https://<your-domain>/the-new-business-normal?utm_source=pancake`
2. Submit the participant form with a unique test email.
3. Make a real test payment via Scale Your Org (smallest amount possible).
4. Wait 15 min (or trigger cron manually).
5. Open admin.html → verify the payment appears in the Recent Payments table with `utm_source=pancake` and `match_method=email`.
6. Verify the Revenue-by-UTM chart shows the test amount under `pancake`.

- [ ] **Step 7: Update memory**

Save a project memory that the Business Unlocked payment sync is live, with the data flow and where to check logs. Update `MEMORY.md`.

- [ ] **Step 8: Final commit / PR**

No code to commit at this step — everything is verified. If working in a branch, merge / open PR.

---

## Self-Review

**Spec coverage check:**
- Bridge sheet + service account setup → Task 3 ✓
- Supabase schema (purchases + sync_log with RLS, indexes) → Task 2 ✓
- Normalizers (email, mobile) → Task 4 ✓
- Tier parser → Task 5 ✓
- Row parser (Scale Your Org format) → Task 6 ✓
- Participant matcher with tie-break → Task 7 ✓
- Sheets API reader with forced refresh → Task 8 ✓
- Supabase PostgREST helpers (upsert, fetch participants, fetch unmatched, update match, write log) → Task 9 ✓
- Orchestrator (read→parse→match→upsert→rematch→log) with 7-day re-match → Task 10 ✓
- Vercel handler + cron secret + vercel.json entry → Task 11 ✓
- Dashboard API endpoints (revenue_by_utm, tickets_by_utm_tier, conversion_by_utm, recent_payments, last_sync) + fix stale table names in existing endpoints → Task 12 ✓
- Dashboard UI (KPI cards, 3 charts, payments table, last-sync indicator) → Task 13 ✓
- End-to-end verification → Task 14 ✓
- All 9 accuracy defenses from the spec are implemented:
  1. PK + UPSERT → Task 9 (merge-duplicates) ✓
  2. Force IMPORTRANGE refresh → Task 8 ✓
  3. Email normalization → Task 4 ✓
  4. Mobile normalization → Task 4 ✓
  5. 7-day re-match window → Task 10 ✓
  6. Filter refunds at query time → Task 12 (payment_status IN filter) ✓
  7. Most-recent-before-payment tie-break → Task 7 ✓
  8. Direct bucket for unmatched → Task 10 (_EMPTY_UTM + match_method='direct') ✓
  9. Audit log → Task 9 + Task 10 (write_log always called) ✓

**Placeholder scan:** No TBDs, no TODOs, no "similar to task N" — every step has concrete code or commands.

**Type consistency:** Function signatures used in `run_sync` tests (`upsert(purchase, participant_id, match_method, utm_fields)`, `fetch_participants(emails, mobiles)`, `fetch_unmatched(days=7)`, `update_match(txn_id, pid, method, utm)`, `write_log(log)`) match the Supabase helper signatures defined in Task 9. `normalize_email` / `normalize_mobile` / `parse_tier` / `parse_row` / `match_purchase_to_participant` / `run_sync` names are consistent across Tasks 4-10.

**Scope check:** This is one feature — payment sync + dashboard. No sub-decomposition needed.

Plan is complete.
