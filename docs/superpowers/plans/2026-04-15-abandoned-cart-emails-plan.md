# Abandoned Cart Email Sequence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vercel cron pushes form-fillers without payments to a Brevo list (which triggers a 3-email sequence), and pushes paying customers to a Brevo exclusion list, so the existing nurture-sequence workflow can chase abandoned carts without sending to actual buyers.

**Architecture:** Cron at `*/15 * * * *` calls `/api/abandoned-cart`. Handler delegates to a pure orchestrator (`run_abandoned_cart`) with all I/O injected — same dependency-injection pattern as `sync_payments.run_sync` so unit tests can stub Supabase and Brevo. Two new columns track per-participant push state. One new audit table mirrors `new_business_normal_sync_log`.

**Tech Stack:** Python 3 (Vercel serverless, stdlib `urllib` only — matches `api/report.py` and `api/sync_payments.py`), PostgreSQL via Supabase, Brevo Contacts API v3, pytest. No new dependencies.

**Reference spec:** `docs/superpowers/specs/2026-04-15-abandoned-cart-emails-design.md`

---

## File Structure

**Create:**
- `supabase/migrations/2026-04-15_brevo_tracking.sql` — the migration (Paolo runs in SQL Editor)
- `api/abandoned_cart.py` — pure module: query builders, payload builders, Supabase helpers, Brevo helper, orchestrator
- `api/abandoned-cart.py` — Vercel cron handler (thin wrapper, mirrors `api/sync-payments.py`)
- `tests/test_abandoned_cart.py` — pytest unit tests for pure helpers + orchestrator
- `emails/abandoned-1-still-thinking.html` — Email 1 draft (3h: light check-in)
- `emails/abandoned-2-what-changes.html` — Email 2 draft (+3d: transformation hook)
- `emails/abandoned-3-last-call.html` — Email 3 draft (+7d: scarcity)

**Modify:**
- `vercel.json` — add cron entry `{ "path": "/api/abandoned-cart", "schedule": "*/15 * * * *" }`
- `.env.example` — add `BREVO_API_KEY`, `BREVO_ABANDONED_LIST_ID`, `BREVO_EXCLUDE_LIST_ID`
- `api/report.py` — add `handle_abandoned_log` action that returns the most recent `new_business_normal_brevo_log` row
- `js/admin-sales.js` — show "Last abandoned-cart run: …" next to the existing "Last sync" indicator
- `docs/sync-setup.md` — append a Brevo setup section

**Responsibility split:** All abandoned-cart logic lives in `api/abandoned_cart.py` as module-level functions, mirroring the `api/sync_payments.py` pattern. The hyphenated `api/abandoned-cart.py` is a 30-line Vercel wrapper that imports the underscore module and wires the orchestrator's injected callables to real implementations.

---

## Task 1: Supabase migration

**Files:**
- Create: `supabase/migrations/2026-04-15_brevo_tracking.sql`

The Supabase MCP is wired to a different project (`hjfuxwytpyqhuvrbssds`), so Paolo runs this in the SQL Editor for `nvhzajpstswkmmfrgtiw`.

- [ ] **Step 1: Create the migration file**

```sql
-- Brevo tracking columns on participants
alter table new_business_normal_participants
  add column if not exists brevo_abandoned_pushed_at timestamptz,
  add column if not exists brevo_excluded_pushed_at  timestamptz;

create index if not exists idx_participants_brevo_abandoned
  on new_business_normal_participants (brevo_abandoned_pushed_at);
create index if not exists idx_participants_brevo_excluded
  on new_business_normal_participants (brevo_excluded_pushed_at);

-- Audit log table for the abandoned-cart cron
create table if not exists new_business_normal_brevo_log (
  id               uuid primary key default gen_random_uuid(),
  started_at       timestamptz,
  finished_at      timestamptz,
  abandoned_pushed int default 0,
  excluded_pushed  int default 0,
  errors           jsonb,
  success          boolean
);
create index if not exists idx_brevo_log_started_at
  on new_business_normal_brevo_log (started_at desc);

alter table new_business_normal_brevo_log enable row level security;
drop policy if exists "brevo_log_no_anon" on new_business_normal_brevo_log;
create policy "brevo_log_no_anon" on new_business_normal_brevo_log
  for all to anon using (false) with check (false);
```

- [ ] **Step 2: Tell Paolo to apply via the Supabase SQL Editor**

Paste the SQL block above into https://supabase.com/dashboard/project/nvhzajpstswkmmfrgtiw/sql/new and click **Run**.

- [ ] **Step 3: Verify via curl that the new columns are queryable**

```bash
ANON='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im52aHphanBzdHN3a21tZnJndGl3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU3OTYyMTcsImV4cCI6MjA5MTM3MjIxN30.Fv_bO_jfxPloC-Nel1ezAHWBWlHZnHja8ZNTtyCkX6k'
curl -s -H "apikey: $ANON" -H "Authorization: Bearer $ANON" \
  "https://nvhzajpstswkmmfrgtiw.supabase.co/rest/v1/new_business_normal_participants?select=brevo_abandoned_pushed_at,brevo_excluded_pushed_at&limit=1"
```

Expected: `[{"brevo_abandoned_pushed_at":null,"brevo_excluded_pushed_at":null}]` (or similar — the keys must appear in the response).

- [ ] **Step 4: Commit the migration file**

```bash
cd "/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit"
git add supabase/migrations/2026-04-15_brevo_tracking.sql
git commit -m "feat(db): add Brevo tracking columns + brevo_log table

Adds brevo_abandoned_pushed_at + brevo_excluded_pushed_at to participants
so the abandoned-cart cron can track which contacts have already been
pushed to which Brevo list (avoid double-pushing). New brevo_log table
captures per-cron-run audit data: counts + errors + success flag.

Migration is additive only and was applied manually via Supabase SQL Editor."
```

---

## Task 2: TDD — Hard cutoff helper

**Files:**
- Create: `api/abandoned_cart.py`
- Create: `tests/test_abandoned_cart.py`

The cron stops pushing new contacts to the abandoned list 2 days before the May 9 event (so no one gets a chase email after the event).

- [ ] **Step 1: Create the test file with failing tests**

`tests/test_abandoned_cart.py`:

```python
from datetime import datetime, timezone, timedelta
import abandoned_cart as ac


# ---------- is_past_push_cutoff ----------

def test_cutoff_false_well_before_event():
    now = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
    assert ac.is_past_push_cutoff(now) is False


def test_cutoff_false_just_before_cutoff():
    # Cutoff is end-of-day 2026-05-07 UTC (2 days before May 9)
    now = datetime(2026, 5, 7, 23, 58, tzinfo=timezone.utc)
    assert ac.is_past_push_cutoff(now) is False


def test_cutoff_true_at_cutoff():
    now = datetime(2026, 5, 8, 0, 0, tzinfo=timezone.utc)
    assert ac.is_past_push_cutoff(now) is True


def test_cutoff_true_on_event_day():
    now = datetime(2026, 5, 9, 9, 0, tzinfo=timezone.utc)
    assert ac.is_past_push_cutoff(now) is True


def test_cutoff_true_after_event():
    now = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
    assert ac.is_past_push_cutoff(now) is True
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
cd "/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit"
source .venv/bin/activate
pytest tests/test_abandoned_cart.py -v
```

Expected: `ModuleNotFoundError: No module named 'abandoned_cart'` (collection error).

- [ ] **Step 3: Create `api/abandoned_cart.py` with the helper**

```python
"""
/api/abandoned-cart — Vercel cron handler module.

Every 15 minutes:
  1. Find form-fillers without a paid purchase (created_at < now - 3h, not pushed yet)
  2. Push each to Brevo "BU Abandoned Cart" list (idempotent)
  3. Find paying participants not yet excluded
  4. Push each to Brevo "BU Paid — Exclude" list (so the Brevo automation skips them)
  5. Audit-log the run to new_business_normal_brevo_log

Stops pushing new abandoned contacts after 2026-05-07 (2 days before the event)
to avoid sending chase emails after the May 9 summit. The exclusion-list push
keeps running so anyone who pays last-minute is still removed from in-flight
automations.
"""

import json
import os
import re
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# Hard cutoff
# ---------------------------------------------------------------------------

EVENT_DATE = datetime(2026, 5, 9, 0, 0, tzinfo=timezone.utc)
PUSH_CUTOFF = EVENT_DATE - timedelta(days=1)  # 2026-05-08T00:00:00Z


def is_past_push_cutoff(now):
    """True once we should stop pushing new contacts to the abandoned-cart list."""
    return now >= PUSH_CUTOFF
```

- [ ] **Step 4: Run the tests, confirm they pass**

```bash
pytest tests/test_abandoned_cart.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add api/abandoned_cart.py tests/test_abandoned_cart.py
git commit -m "feat(abandoned): add hard event-cutoff helper with tests"
```

---

## Task 3: TDD — Participant query helpers

The abandoned-cart query and the newly-paid query are both pure path-string builders. Testing them this way means the orchestrator can stub HTTP entirely.

**Files:**
- Modify: `api/abandoned_cart.py`
- Modify: `tests/test_abandoned_cart.py`

- [ ] **Step 1: Append failing tests**

```python
# ---------- build_abandoned_query ----------

def test_abandoned_query_includes_all_filters():
    now = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
    path = ac.build_abandoned_query(now, abandon_age_hours=3, max_age_days=14)

    assert "new_business_normal_participants" in path
    # Must filter by created_at < now - 3h
    assert "created_at=lt." in path
    assert "2026-04-20T09:00" in path
    # Must filter by created_at > now - 14 days (sliding floor)
    assert "created_at=gt." in path
    assert "2026-04-06T12:00" in path
    # Must skip already-pushed
    assert "brevo_abandoned_pushed_at=is.null" in path
    # Must select fields needed for Brevo payload
    assert "select=" in path
    assert "id" in path and "email" in path and "full_name" in path


# ---------- build_newly_paid_query ----------

def test_newly_paid_query_filters_correctly():
    path = ac.build_newly_paid_query()
    assert "new_business_normal_participants" in path
    assert "brevo_excluded_pushed_at=is.null" in path
    assert "select=" in path
    assert "id" in path and "email" in path and "full_name" in path
```

- [ ] **Step 2: Run, confirm failure**

```bash
pytest tests/test_abandoned_cart.py -v -k "abandoned_query or newly_paid_query"
```

Expected: 2 failures (`AttributeError: no attribute 'build_abandoned_query'`).

- [ ] **Step 3: Append the helpers**

```python
# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------

PARTICIPANTS_TABLE = "new_business_normal_participants"
PURCHASES_TABLE = "new_business_normal_purchases"
BREVO_LOG_TABLE = "new_business_normal_brevo_log"

# Common select set used by both query builders.
PARTICIPANT_FIELDS = "id,email,full_name,mobile_number,created_at"


def build_abandoned_query(now, abandon_age_hours=3, max_age_days=14):
    """
    Build a PostgREST path that returns participants who:
      - filled the form `abandon_age_hours` hours ago or earlier
      - are NOT older than `max_age_days` (don't trigger ancient signups)
      - have not been pushed to the abandoned list yet
    The orchestrator further filters by 'no paid purchase by email/mobile'
    in Python after fetch (because PostgREST can't easily express that join).
    """
    floor = (now - timedelta(days=max_age_days)).isoformat()
    ceiling = (now - timedelta(hours=abandon_age_hours)).isoformat()
    return (
        f"{PARTICIPANTS_TABLE}"
        f"?select={PARTICIPANT_FIELDS}"
        f"&created_at=gt.{floor}"
        f"&created_at=lt.{ceiling}"
        f"&brevo_abandoned_pushed_at=is.null"
    )


def build_newly_paid_query():
    """
    Build a PostgREST path that returns participants not yet excluded.
    The orchestrator filters by 'has paid purchase by email/mobile' in Python.
    """
    return (
        f"{PARTICIPANTS_TABLE}"
        f"?select={PARTICIPANT_FIELDS}"
        f"&brevo_excluded_pushed_at=is.null"
    )
```

- [ ] **Step 4: Run, confirm 7 pass (5 + 2 new)**

```bash
pytest tests/test_abandoned_cart.py -v
```

- [ ] **Step 5: Commit**

```bash
git add api/abandoned_cart.py tests/test_abandoned_cart.py
git commit -m "feat(abandoned): add abandoned + newly-paid query builders"
```

---

## Task 4: TDD — Brevo payload builder

**Files:**
- Modify: `api/abandoned_cart.py`
- Modify: `tests/test_abandoned_cart.py`

- [ ] **Step 1: Append failing tests**

```python
# ---------- build_brevo_contact_payload ----------

def test_brevo_payload_basic():
    p = {
        "id": 42,
        "email": "wyne_ramos@yahoo.com",
        "full_name": "Wynes Ramos",
        "mobile_number": "+639178334375",
        "created_at": "2026-04-15T10:00:00Z",
    }
    payload = ac.build_brevo_contact_payload(p, list_id=7)
    assert payload["email"] == "wyne_ramos@yahoo.com"
    assert payload["listIds"] == [7]
    assert payload["updateEnabled"] is True
    assert payload["attributes"]["FNAME"] == "Wynes"
    assert payload["attributes"]["LNAME"] == "Ramos"
    assert payload["attributes"]["SMS"] == "+639178334375"


def test_brevo_payload_single_word_name():
    p = {"id": 1, "email": "a@b.com", "full_name": "Cher", "mobile_number": None,
         "created_at": "2026-04-15T10:00:00Z"}
    payload = ac.build_brevo_contact_payload(p, list_id=7)
    assert payload["attributes"]["FNAME"] == "Cher"
    assert payload["attributes"]["LNAME"] == ""
    assert "SMS" not in payload["attributes"]


def test_brevo_payload_handles_missing_name():
    p = {"id": 1, "email": "a@b.com", "full_name": None, "mobile_number": "",
         "created_at": "2026-04-15T10:00:00Z"}
    payload = ac.build_brevo_contact_payload(p, list_id=7)
    assert payload["attributes"]["FNAME"] == ""
    assert payload["attributes"]["LNAME"] == ""


def test_brevo_payload_lowercases_email():
    p = {"id": 1, "email": "  Wyne_Ramos@Yahoo.COM ", "full_name": "Test User",
         "mobile_number": None, "created_at": "2026-04-15T10:00:00Z"}
    payload = ac.build_brevo_contact_payload(p, list_id=7)
    assert payload["email"] == "wyne_ramos@yahoo.com"
```

- [ ] **Step 2: Run, confirm failure**

```bash
pytest tests/test_abandoned_cart.py -v -k brevo_payload
```

- [ ] **Step 3: Append helper to `api/abandoned_cart.py`**

```python
# ---------------------------------------------------------------------------
# Brevo payload
# ---------------------------------------------------------------------------

def _split_name(full_name):
    """Best-effort first/last split from a single 'full_name' string."""
    if not full_name:
        return "", ""
    parts = str(full_name).strip().split(None, 1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    return first, last


def build_brevo_contact_payload(participant, list_id):
    """
    Build the JSON body for POST https://api.brevo.com/v3/contacts.
    `updateEnabled: True` makes the call idempotent — if the contact
    already exists it gets updated and added to the list instead of erroring.
    """
    email = (participant.get("email") or "").strip().lower()
    first, last = _split_name(participant.get("full_name"))
    mobile = participant.get("mobile_number") or ""

    attrs = {"FNAME": first, "LNAME": last}
    if mobile:
        attrs["SMS"] = mobile

    return {
        "email": email,
        "attributes": attrs,
        "listIds": [list_id],
        "updateEnabled": True,
    }
```

- [ ] **Step 4: Run, confirm 11 pass (7 + 4 new)**

- [ ] **Step 5: Commit**

```bash
git add api/abandoned_cart.py tests/test_abandoned_cart.py
git commit -m "feat(abandoned): add Brevo contact-payload builder"
```

---

## Task 5: HTTP layer — Supabase + Brevo callers

These are thin urllib wrappers. No unit tests — they're stubbed by the orchestrator's test harness in Task 6.

**Files:**
- Modify: `api/abandoned_cart.py`

- [ ] **Step 1: Append HTTP helpers**

```python
# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only, matches api/report.py + api/sync_payments.py pattern)
# ---------------------------------------------------------------------------

import urllib.request
import urllib.error
from urllib.parse import quote


def _supabase_env():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    return url.rstrip("/"), key


def _supabase_request(method, path, body=None, extra_headers=None):
    """Generic PostgREST request. Returns parsed JSON or [] on empty body."""
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
        return json.loads(raw) if raw else []


def supabase_get_paid_emails_and_mobiles():
    """
    Returns (paid_emails_set, paid_mobiles_set) from purchases where
    payment_status IN ('PAID','FULLY_PAID'). Used by the orchestrator to
    filter abandoned candidates.
    """
    rows = _supabase_request(
        "GET",
        f"{PURCHASES_TABLE}?select=email,mobile&payment_status=in.(PAID,FULLY_PAID)",
    ) or []
    emails = {(r.get("email") or "").lower() for r in rows if r.get("email")}
    mobiles = {(r.get("mobile") or "") for r in rows if r.get("mobile")}
    return emails, mobiles


def supabase_get_participants(path):
    """Execute a participants query path. Returns list of dicts."""
    return _supabase_request("GET", path) or []


def supabase_mark_abandoned_pushed(participant_id, now_iso):
    """PATCH brevo_abandoned_pushed_at on a participant by id."""
    body = {"brevo_abandoned_pushed_at": now_iso}
    _supabase_request(
        "PATCH",
        f"{PARTICIPANTS_TABLE}?id=eq.{participant_id}",
        body=body,
        extra_headers={"Prefer": "return=minimal"},
    )


def supabase_mark_excluded_pushed(participant_id, now_iso):
    """PATCH brevo_excluded_pushed_at on a participant by id."""
    body = {"brevo_excluded_pushed_at": now_iso}
    _supabase_request(
        "PATCH",
        f"{PARTICIPANTS_TABLE}?id=eq.{participant_id}",
        body=body,
        extra_headers={"Prefer": "return=minimal"},
    )


def supabase_write_brevo_log(log):
    """Insert one audit row into brevo_log."""
    _supabase_request(
        "POST",
        BREVO_LOG_TABLE,
        body=log,
        extra_headers={"Prefer": "return=minimal"},
    )


# ---------------------------------------------------------------------------
# Brevo Contacts API
# ---------------------------------------------------------------------------

BREVO_API_URL = "https://api.brevo.com/v3/contacts"


def _brevo_api_key():
    key = os.environ.get("BREVO_API_KEY")
    if not key:
        raise EnvironmentError("Missing BREVO_API_KEY")
    return key


def brevo_add_contact_to_list(participant, list_id):
    """
    POST /v3/contacts with updateEnabled=true so the call is idempotent.
    Brevo returns 201 (new contact), 204 (existing contact updated), or
    a 400+ error. Raises urllib.error.HTTPError on 4xx/5xx.
    """
    payload = build_brevo_contact_payload(participant, list_id)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BREVO_API_URL, data=body, method="POST")
    req.add_header("api-key", _brevo_api_key())
    req.add_header("accept", "application/json")
    req.add_header("content-type", "application/json")

    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status
```

- [ ] **Step 2: Verify the module still imports + tests still pass**

```bash
cd "/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit"
source .venv/bin/activate
python -c "import sys; sys.path.insert(0, 'api'); import abandoned_cart; print('module OK', hasattr(abandoned_cart, 'brevo_add_contact_to_list'))"
pytest tests/test_abandoned_cart.py -v
```

Expected: `module OK True` and 11 passed.

- [ ] **Step 3: Commit**

```bash
git add api/abandoned_cart.py
git commit -m "feat(abandoned): add Supabase + Brevo HTTP helpers"
```

---

## Task 6: TDD — Orchestrator `run_abandoned_cart`

The orchestrator does it all: cutoff check, fetch abandoned, fetch newly-paid, push to both Brevo lists, mark each participant, write audit log. All I/O injected so tests don't touch the network.

**Files:**
- Modify: `api/abandoned_cart.py`
- Modify: `tests/test_abandoned_cart.py`

- [ ] **Step 1: Append failing tests**

```python
# ---------- run_abandoned_cart (orchestrator) ----------

NOW = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)


class _FakeBackend:
    """In-memory stand-in for Supabase + Brevo callables."""
    def __init__(self, abandoned=None, newly_paid_candidates=None,
                 paid_emails=None, paid_mobiles=None):
        self.abandoned_rows = abandoned or []
        self.newly_paid_candidates = newly_paid_candidates or []
        self.paid_emails = paid_emails or set()
        self.paid_mobiles = paid_mobiles or set()
        self.brevo_pushes = []      # list of (participant, list_id)
        self.marked_abandoned = []  # list of participant_id
        self.marked_excluded = []   # list of participant_id
        self.logs = []

    def fetch_paid_contacts(self):
        return self.paid_emails, self.paid_mobiles

    def fetch_participants(self, path):
        if "brevo_abandoned_pushed_at=is.null" in path:
            return list(self.abandoned_rows)
        if "brevo_excluded_pushed_at=is.null" in path:
            return list(self.newly_paid_candidates)
        return []

    def push_to_brevo(self, participant, list_id):
        self.brevo_pushes.append((participant, list_id))
        return 201

    def mark_abandoned(self, pid, now_iso):
        self.marked_abandoned.append(pid)

    def mark_excluded(self, pid, now_iso):
        self.marked_excluded.append(pid)

    def write_log(self, log):
        self.logs.append(log)


def _ptcpt(pid, email, mobile=None, full_name="Test User"):
    return {
        "id": pid, "email": email, "mobile_number": mobile,
        "full_name": full_name, "created_at": "2026-04-20T08:00:00Z",
    }


def test_run_pushes_abandoned_and_marks_them():
    back = _FakeBackend(
        abandoned=[_ptcpt(1, "alice@example.com"),
                   _ptcpt(2, "bob@example.com")],
        paid_emails=set(), paid_mobiles=set(),
    )
    result = ac.run_abandoned_cart(
        now=NOW,
        abandoned_list_id=10, exclude_list_id=20,
        fetch_paid_contacts=back.fetch_paid_contacts,
        fetch_participants=back.fetch_participants,
        push_to_brevo=back.push_to_brevo,
        mark_abandoned=back.mark_abandoned,
        mark_excluded=back.mark_excluded,
        write_log=back.write_log,
    )
    pushed_to_abandoned = [p for p, lid in back.brevo_pushes if lid == 10]
    assert len(pushed_to_abandoned) == 2
    assert sorted(back.marked_abandoned) == [1, 2]
    assert result["abandoned_pushed"] == 2
    assert result["success"] is True


def test_run_skips_abandoned_with_paid_email():
    back = _FakeBackend(
        abandoned=[
            _ptcpt(1, "alice@example.com"),       # paid → skip
            _ptcpt(2, "bob@example.com"),          # not paid → push
        ],
        paid_emails={"alice@example.com"},
    )
    ac.run_abandoned_cart(
        now=NOW,
        abandoned_list_id=10, exclude_list_id=20,
        fetch_paid_contacts=back.fetch_paid_contacts,
        fetch_participants=back.fetch_participants,
        push_to_brevo=back.push_to_brevo,
        mark_abandoned=back.mark_abandoned,
        mark_excluded=back.mark_excluded,
        write_log=back.write_log,
    )
    pushed_emails = [p["email"] for p, lid in back.brevo_pushes if lid == 10]
    assert pushed_emails == ["bob@example.com"]
    assert back.marked_abandoned == [2]


def test_run_skips_abandoned_with_paid_mobile_fallback():
    back = _FakeBackend(
        abandoned=[_ptcpt(1, "carol@example.com", mobile="9178334375")],
        paid_emails=set(), paid_mobiles={"9178334375"},
    )
    ac.run_abandoned_cart(
        now=NOW,
        abandoned_list_id=10, exclude_list_id=20,
        fetch_paid_contacts=back.fetch_paid_contacts,
        fetch_participants=back.fetch_participants,
        push_to_brevo=back.push_to_brevo,
        mark_abandoned=back.mark_abandoned,
        mark_excluded=back.mark_excluded,
        write_log=back.write_log,
    )
    assert back.brevo_pushes == []
    assert back.marked_abandoned == []


def test_run_pushes_newly_paid_to_exclude_list():
    back = _FakeBackend(
        newly_paid_candidates=[_ptcpt(1, "dave@example.com")],
        paid_emails={"dave@example.com"},
    )
    result = ac.run_abandoned_cart(
        now=NOW,
        abandoned_list_id=10, exclude_list_id=20,
        fetch_paid_contacts=back.fetch_paid_contacts,
        fetch_participants=back.fetch_participants,
        push_to_brevo=back.push_to_brevo,
        mark_abandoned=back.mark_abandoned,
        mark_excluded=back.mark_excluded,
        write_log=back.write_log,
    )
    pushed_to_exclude = [p for p, lid in back.brevo_pushes if lid == 20]
    assert len(pushed_to_exclude) == 1
    assert back.marked_excluded == [1]
    assert result["excluded_pushed"] == 1


def test_run_past_cutoff_skips_abandoned_but_still_excludes():
    after_cutoff = datetime(2026, 5, 8, 1, 0, tzinfo=timezone.utc)
    back = _FakeBackend(
        abandoned=[_ptcpt(1, "late@example.com")],
        newly_paid_candidates=[_ptcpt(2, "buyer@example.com")],
        paid_emails={"buyer@example.com"},
    )
    result = ac.run_abandoned_cart(
        now=after_cutoff,
        abandoned_list_id=10, exclude_list_id=20,
        fetch_paid_contacts=back.fetch_paid_contacts,
        fetch_participants=back.fetch_participants,
        push_to_brevo=back.push_to_brevo,
        mark_abandoned=back.mark_abandoned,
        mark_excluded=back.mark_excluded,
        write_log=back.write_log,
    )
    # No abandoned pushed (past cutoff)
    assert result["abandoned_pushed"] == 0
    # Exclusion-list push still happens
    assert result["excluded_pushed"] == 1


def test_run_writes_audit_log_with_counts():
    back = _FakeBackend(abandoned=[_ptcpt(1, "alice@example.com")])
    ac.run_abandoned_cart(
        now=NOW,
        abandoned_list_id=10, exclude_list_id=20,
        fetch_paid_contacts=back.fetch_paid_contacts,
        fetch_participants=back.fetch_participants,
        push_to_brevo=back.push_to_brevo,
        mark_abandoned=back.mark_abandoned,
        mark_excluded=back.mark_excluded,
        write_log=back.write_log,
    )
    assert len(back.logs) == 1
    log = back.logs[0]
    assert "started_at" in log and "finished_at" in log
    assert log["abandoned_pushed"] == 1
    assert log["excluded_pushed"] == 0
    assert log["success"] is True


def test_run_brevo_failure_does_not_mark_pushed():
    """If push_to_brevo raises, the participant must NOT be marked
    as pushed — they retry next cron run."""
    back = _FakeBackend(abandoned=[_ptcpt(1, "alice@example.com")])

    def failing_push(p, lid):
        raise Exception("Brevo 503")

    result = ac.run_abandoned_cart(
        now=NOW,
        abandoned_list_id=10, exclude_list_id=20,
        fetch_paid_contacts=back.fetch_paid_contacts,
        fetch_participants=back.fetch_participants,
        push_to_brevo=failing_push,
        mark_abandoned=back.mark_abandoned,
        mark_excluded=back.mark_excluded,
        write_log=back.write_log,
    )
    assert back.marked_abandoned == []
    assert result["abandoned_pushed"] == 0
    assert result["success"] is False
    assert any("Brevo 503" in str(e) for e in (result.get("errors") or []))
```

- [ ] **Step 2: Run, confirm 7 failures**

```bash
pytest tests/test_abandoned_cart.py -v -k "test_run_"
```

- [ ] **Step 3: Append the orchestrator**

```python
# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _iso(dt):
    return dt.isoformat()


def _normalize_email(s):
    return (s or "").strip().lower()


def _normalize_mobile(s):
    if not s:
        return ""
    digits = re.sub(r"\D", "", str(s))
    return digits[-10:] if len(digits) >= 10 else ""


def run_abandoned_cart(
    now,
    abandoned_list_id,
    exclude_list_id,
    fetch_paid_contacts,
    fetch_participants,
    push_to_brevo,
    mark_abandoned,
    mark_excluded,
    write_log,
):
    """
    Execute one cron cycle. All I/O is injected so this is unit-testable.

    Phases:
      1. Fetch paid emails+mobiles set (one pass; reused for both phases below)
      2. If now < PUSH_CUTOFF: fetch abandoned candidates, filter by
         "not in paid set", push each to abandoned_list_id, mark pushed
      3. Fetch newly-paid candidates (participants without exclusion mark),
         filter by "in paid set", push each to exclude_list_id, mark excluded
      4. Write audit log
    """
    started_at = _iso(now)
    errors = []
    abandoned_pushed = 0
    excluded_pushed = 0

    try:
        paid_emails, paid_mobiles = fetch_paid_contacts()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"fetch_paid_contacts: {type(exc).__name__}: {exc}")
        paid_emails, paid_mobiles = set(), set()

    # ---- Phase: abandoned ----
    if not is_past_push_cutoff(now):
        try:
            path = build_abandoned_query(now)
            abandoned = fetch_participants(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"fetch abandoned: {type(exc).__name__}: {exc}")
            abandoned = []

        for p in abandoned:
            email = _normalize_email(p.get("email"))
            mobile = _normalize_mobile(p.get("mobile_number"))
            if email and email in paid_emails:
                continue
            if mobile and mobile in paid_mobiles:
                continue
            try:
                push_to_brevo(p, abandoned_list_id)
                mark_abandoned(p["id"], _iso(now))
                abandoned_pushed += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"abandoned push id={p.get('id')}: {exc}")

    # ---- Phase: exclusions (always runs, even past cutoff) ----
    try:
        path = build_newly_paid_query()
        newly_paid_candidates = fetch_participants(path)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"fetch newly_paid: {type(exc).__name__}: {exc}")
        newly_paid_candidates = []

    for p in newly_paid_candidates:
        email = _normalize_email(p.get("email"))
        mobile = _normalize_mobile(p.get("mobile_number"))
        is_paid = (email and email in paid_emails) or (mobile and mobile in paid_mobiles)
        if not is_paid:
            continue
        try:
            push_to_brevo(p, exclude_list_id)
            mark_excluded(p["id"], _iso(now))
            excluded_pushed += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"exclude push id={p.get('id')}: {exc}")

    success = len(errors) == 0
    finished_at = _iso(datetime.now(timezone.utc))

    log = {
        "started_at": started_at,
        "finished_at": finished_at,
        "abandoned_pushed": abandoned_pushed,
        "excluded_pushed": excluded_pushed,
        "errors": errors if errors else None,
        "success": success,
    }
    try:
        write_log(log)
    except Exception:  # noqa: BLE001
        pass  # never fail the cron just because the log write failed

    return log
```

- [ ] **Step 4: Run, confirm 18 pass (11 + 7 new)**

```bash
pytest tests/test_abandoned_cart.py -v
```

- [ ] **Step 5: Commit**

```bash
git add api/abandoned_cart.py tests/test_abandoned_cart.py
git commit -m "feat(abandoned): add orchestrator with phase separation and error capture"
```

---

## Task 7: Vercel handler + cron entry

**Files:**
- Create: `api/abandoned-cart.py`
- Modify: `vercel.json`
- Modify: `.env.example`

- [ ] **Step 1: Create `api/abandoned-cart.py`**

```python
"""
Vercel serverless endpoint /api/abandoned-cart.

Vercel routes file path api/abandoned-cart.py to URL /api/abandoned-cart.
Triggered by a cron entry in vercel.json every 15 minutes.

Thin wrapper — all logic lives in `abandoned_cart.py` (underscore module)
so the test suite can import it cleanly.
"""

import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import abandoned_cart as ac  # noqa: E402


def _send_json(h, status, payload):
    body = json.dumps(payload).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def _is_authorized_cron_request(h):
    """Same fail-closed-in-prod pattern as api/sync-payments.py."""
    expected = os.environ.get("CRON_SECRET")
    is_production = os.environ.get("VERCEL_ENV") == "production"
    if not expected:
        return not is_production
    return h.headers.get("Authorization", "") == f"Bearer {expected}"


def _int_env(name):
    raw = os.environ.get(name)
    if not raw:
        raise EnvironmentError(f"Missing {name}")
    try:
        return int(raw)
    except ValueError:
        raise EnvironmentError(f"{name} must be an integer Brevo list id, got: {raw!r}")


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if not _is_authorized_cron_request(self):
            _send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            abandoned_list_id = _int_env("BREVO_ABANDONED_LIST_ID")
            exclude_list_id = _int_env("BREVO_EXCLUDE_LIST_ID")

            result = ac.run_abandoned_cart(
                now=datetime.now(timezone.utc),
                abandoned_list_id=abandoned_list_id,
                exclude_list_id=exclude_list_id,
                fetch_paid_contacts=ac.supabase_get_paid_emails_and_mobiles,
                fetch_participants=ac.supabase_get_participants,
                push_to_brevo=ac.brevo_add_contact_to_list,
                mark_abandoned=ac.supabase_mark_abandoned_pushed,
                mark_excluded=ac.supabase_mark_excluded_pushed,
                write_log=ac.supabase_write_brevo_log,
            )
            _send_json(self, 200, result)
        except Exception as exc:  # noqa: BLE001
            print(f"[abandoned-cart] error: {type(exc).__name__}: {exc}", flush=True)
            _send_json(self, 500, {"error": "Abandoned-cart run failed; see server logs."})

    def log_message(self, format, *args):
        pass
```

- [ ] **Step 2: Add the cron entry to `vercel.json`**

Read the file, find the existing `"crons"` array (currently has one entry for `/api/sync-payments`), and add a second entry. Final crons block:

```json
"crons": [
  { "path": "/api/sync-payments", "schedule": "*/15 * * * *" },
  { "path": "/api/abandoned-cart", "schedule": "*/15 * * * *" }
]
```

- [ ] **Step 3: Append three vars to `.env.example`**

Append to `.env.example`:

```
# Brevo abandoned-cart cron — see docs/sync-setup.md for setup
BREVO_API_KEY=
BREVO_ABANDONED_LIST_ID=
BREVO_EXCLUDE_LIST_ID=
```

- [ ] **Step 4: Verify**

```bash
cd "/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit"
source .venv/bin/activate
python -c "import json; json.load(open('vercel.json')); print('vercel.json OK')"
pytest tests/test_abandoned_cart.py tests/test_sync_payments.py -v 2>&1 | tail -3
```

Expected: `vercel.json OK` and 52 passed (34 sync + 18 abandoned).

- [ ] **Step 5: Commit**

```bash
git add api/abandoned-cart.py vercel.json .env.example
git commit -m "feat(abandoned): add Vercel handler and 15-min cron entry"
```

---

## Task 8: Add `handle_abandoned_log` endpoint to `api/report.py`

**Files:**
- Modify: `api/report.py`

- [ ] **Step 1: Add the table constant**

Find the existing block of `TABLE_*` constants near the top of `report.py` and add a line:

```python
TABLE_BREVO_LOG = "new_business_normal_brevo_log"
```

- [ ] **Step 2: Add the handler function**

Insert after the existing `handle_last_sync` function:

```python
def handle_abandoned_log(h, supabase_url, service_key):
    """GET /api/report?action=abandoned_log — most recent brevo_log row"""
    if not check_auth(h):
        return
    try:
        rows = supabase_get(
            supabase_url, service_key,
            f"{TABLE_BREVO_LOG}?select=started_at,finished_at,abandoned_pushed,excluded_pushed,success,errors"
            f"&order=started_at.desc&limit=1"
        )
    except urllib.error.URLError as exc:
        _send_json(h, 502, {"error": f"Supabase request failed: {exc}"})
        return
    _send_json(h, 200, rows[0] if rows else None)
```

- [ ] **Step 3: Wire into the router**

Inside `class handler(BaseHTTPRequestHandler).do_GET`, add a branch right after the existing `last_sync` branch:

```python
        elif action == "abandoned_log":
            handle_abandoned_log(self, supabase_url, service_key)
```

Update the unknown-action error message string to include `abandoned_log` in the list of valid actions.

- [ ] **Step 4: Verify endpoint registers and existing tests still pass**

```bash
cd "/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit"
python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('report', 'api/report.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print('handle_abandoned_log:', hasattr(m, 'handle_abandoned_log'))
print('TABLE_BREVO_LOG:', m.TABLE_BREVO_LOG)
"
source .venv/bin/activate && pytest tests/ -v 2>&1 | tail -3
```

Expected: function present, `TABLE_BREVO_LOG = new_business_normal_brevo_log`, 52 tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/report.py
git commit -m "feat(report): add abandoned_log action for dashboard status indicator"
```

---

## Task 9: Show abandoned-cart status on the dashboard

**Files:**
- Modify: `js/admin-sales.js`
- Modify: `admin.html`

- [ ] **Step 1: Add a second status indicator next to the existing sync status**

In `admin.html`, find the `<div class="sync-status" id="sync-status">` block. Right below its closing `</div>`, add:

```html
<div class="sync-status" id="abandoned-status">
  <span class="dot" id="abandoned-dot">•</span>
  <span id="abandoned-label">Abandoned-cart: checking…</span>
</div>
```

- [ ] **Step 2: Add the loader function in `js/admin-sales.js`**

Right after the existing `loadSyncStatus()` function, add:

```javascript
async function loadAbandonedStatus() {
  var dot = document.getElementById('abandoned-dot');
  var label = document.getElementById('abandoned-label');
  if (!dot || !label) return;
  try {
    var log = await window.apiFetch('abandoned_log');
    if (!log) {
      dot.className = 'dot err'; label.textContent = 'Abandoned-cart: never run';
      return;
    }
    dot.className = 'dot ' + (log.success ? 'ok' : 'err');
    label.textContent = 'Abandoned-cart: ' + ago(log.started_at)
      + ' • ' + (log.abandoned_pushed || 0) + ' pushed, '
      + (log.excluded_pushed || 0) + ' excluded';
  } catch (err) {
    dot.className = 'dot err';
    label.textContent = 'Abandoned-cart status unavailable';
  }
}
```

- [ ] **Step 3: Call it from `loadAll`**

Inside the `loadAll` function in `js/admin-sales.js`, add a call right after `await loadSyncStatus();`:

```javascript
    await loadAbandonedStatus();
```

- [ ] **Step 4: Verify**

```bash
cd "/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit"
grep -n "abandoned-status\|loadAbandonedStatus\|abandoned_log" admin.html js/admin-sales.js | head -10
```

Expected: matches in both files.

- [ ] **Step 5: Commit**

```bash
git add admin.html js/admin-sales.js
git commit -m "feat(dashboard): show abandoned-cart cron status"
```

---

## Task 10: Email HTML drafts

Three email files in `emails/` matching the existing nurture-series style (dark `#1A1A2E` background, Poppins headlines, Lora body, teal `#0d9488` and amber `#F59E0B` accents, Brevo `{{ unsubscribe }}` footer). Paolo uploads these to Brevo as Templates.

**Files:**
- Create: `emails/abandoned-1-still-thinking.html`
- Create: `emails/abandoned-2-what-changes.html`
- Create: `emails/abandoned-3-last-call.html`

- [ ] **Step 1: Read an existing nurture file as the style template**

```bash
cat emails/nurture-1-problem.html | head -120
```

Note the structure: `<!DOCTYPE html>` + `<head>` with meta tags + `<style>` block (inline + media query) + `<body>` with table-based dark layout, header brand, hero section, body copy, CTA button, footer with `{{ unsubscribe }}`.

- [ ] **Step 2: Create `emails/abandoned-1-still-thinking.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="format-detection" content="telephone=no" />
  <title>Still thinking it over? Here's what people ask me before paying.</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&family=Lora:wght@400;500&display=swap" rel="stylesheet" />
  <style>
    body { margin:0; padding:0; background:#1A1A2E; font-family:'Poppins','Helvetica Neue',Arial,sans-serif; }
    .preheader { display:none; visibility:hidden; opacity:0; mso-hide:all; height:0; max-height:0; line-height:0; }
    .container { max-width:600px; margin:0 auto; }
    .h1 { font-size:28px; font-weight:800; color:#FFFFFF; line-height:1.2; margin:0 0 16px; }
    .body { font-family:'Lora',Georgia,serif; color:#E5E7EB; font-size:16px; line-height:1.6; }
    .cta { display:inline-block; background:#0D9488; color:#FFFFFF; padding:14px 28px; border-radius:8px; text-decoration:none; font-weight:700; }
    @media (max-width:600px) {
      .h1 { font-size:24px; }
    }
  </style>
</head>
<body>
  <span class="preheader">You picked your seat tier — checkout takes 90 seconds.</span>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#1A1A2E;">
    <tr><td align="center" style="padding:24px 16px;">
      <table role="presentation" class="container" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;">

        <tr><td align="center" style="padding:8px 0 32px;">
          <h1 style="margin:0;font-size:22px;font-weight:800;letter-spacing:2px;text-transform:uppercase;color:#FFFFFF;">BUSINESS UNLOCKED</h1>
        </td></tr>

        <tr><td style="background:#16213E;border-radius:12px;padding:32px 24px;">
          <p class="h1">Still thinking it over?</p>
          <p class="body">Hi {{ contact.FNAME }},</p>
          <p class="body">You started signing up for <strong style="color:#F59E0B;">Business Unlocked</strong> on May 9 — and then life probably got in the way. Totally fair.</p>
          <p class="body">Most people in your shoes have one of three questions before checkout:</p>
          <p class="body">
            <strong style="color:#FFFFFF;">1. "Will it actually be worth a Saturday?"</strong><br>
            Yes — you walk out with a 4-pillar cashflow playbook you build during the day, not a stack of slides to review later.
          </p>
          <p class="body">
            <strong style="color:#FFFFFF;">2. "Can I afford it right now?"</strong><br>
            Early Bird is ₱1,999 — that's the price of dinner for two. The point of attending is to find ₱1,999 of new monthly cashflow within 30 days.
          </p>
          <p class="body">
            <strong style="color:#FFFFFF;">3. "What if I can't make it that day?"</strong><br>
            Bring a partner or transfer your seat. Email us if anything weird comes up — we'll work with you.
          </p>
          <p class="body" style="margin:24px 0;">Checkout takes 90 seconds. Same tier you picked is still waiting:</p>
          <p style="text-align:center;margin:24px 0;">
            <a href="https://www.exponential-university.live/the-new-business-normal#pricing?utm_source=email&amp;utm_medium=abandoned&amp;utm_campaign=abandoned-1" class="cta">Finish Checkout →</a>
          </p>
          <p class="body" style="font-size:14px;color:#9CA3AF;">If now isn't the right time, just hit reply and tell me what's holding you back. I read every one.</p>
          <p class="body" style="margin-top:24px;">— The Business Unlocked Team</p>
        </td></tr>

        <tr><td align="center" style="padding:24px 16px;font-family:'Poppins',sans-serif;font-size:11px;color:#9CA3AF;line-height:1.6;">
          You're getting this because you started signing up for Business Unlocked on May 9, 2026.<br>
          <a href="{{ unsubscribe }}" style="color:#9CA3AF;">Unsubscribe</a>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
```

- [ ] **Step 3: Create `emails/abandoned-2-what-changes.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="format-detection" content="telephone=no" />
  <title>What changes when you actually walk out with the cashflow playbook</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&family=Lora:wght@400;500&display=swap" rel="stylesheet" />
  <style>
    body { margin:0; padding:0; background:#1A1A2E; font-family:'Poppins','Helvetica Neue',Arial,sans-serif; }
    .preheader { display:none; visibility:hidden; opacity:0; mso-hide:all; height:0; max-height:0; line-height:0; }
    .container { max-width:600px; margin:0 auto; }
    .h1 { font-size:28px; font-weight:800; color:#FFFFFF; line-height:1.2; margin:0 0 16px; }
    .body { font-family:'Lora',Georgia,serif; color:#E5E7EB; font-size:16px; line-height:1.6; }
    .cta { display:inline-block; background:#F59E0B; color:#1A1A2E; padding:14px 28px; border-radius:8px; text-decoration:none; font-weight:700; }
    @media (max-width:600px) { .h1 { font-size:24px; } }
  </style>
</head>
<body>
  <span class="preheader">The 30-day shift after the summit, in 4 lines.</span>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#1A1A2E;">
    <tr><td align="center" style="padding:24px 16px;">
      <table role="presentation" class="container" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;">

        <tr><td align="center" style="padding:8px 0 32px;">
          <h1 style="margin:0;font-size:22px;font-weight:800;letter-spacing:2px;text-transform:uppercase;color:#FFFFFF;">BUSINESS UNLOCKED</h1>
        </td></tr>

        <tr><td style="background:#16213E;border-radius:12px;padding:32px 24px;">
          <p class="h1">What changes after the summit</p>
          <p class="body">Hi {{ contact.FNAME }},</p>
          <p class="body">You're still on my list, so I'll keep this short. Here's what alumni say their first 30 days look like after walking out of <strong style="color:#F59E0B;">Business Unlocked</strong>:</p>
          <p class="body">
            <strong style="color:#0D9488;">Week 1:</strong> They run the Cashflow Audit on their own books. Most spot ₱30K-₱150K leaking out monthly that no one had named before.
          </p>
          <p class="body">
            <strong style="color:#0D9488;">Week 2:</strong> They pick one of the 4 pillars (Presence, Flexibility, Continuity, Adaptability) and rebuild it. Usually Continuity, because that's where the bleeding is.
          </p>
          <p class="body">
            <strong style="color:#0D9488;">Week 3:</strong> First new revenue line is live. Could be a recurring offer, a price reset, or a payment-terms change.
          </p>
          <p class="body">
            <strong style="color:#0D9488;">Week 4:</strong> They look at the spreadsheet and see the first month where cashflow is no longer "feast or famine."
          </p>
          <p class="body" style="margin:24px 0;">That's the actual unlock. Not slides. Not theory. A working cashflow system that survives the next economic surprise.</p>
          <p style="text-align:center;margin:24px 0;">
            <a href="https://www.exponential-university.live/the-new-business-normal#pricing?utm_source=email&amp;utm_medium=abandoned&amp;utm_campaign=abandoned-2" class="cta">Lock In Your Seat →</a>
          </p>
          <p class="body">— The Business Unlocked Team</p>
        </td></tr>

        <tr><td align="center" style="padding:24px 16px;font-family:'Poppins',sans-serif;font-size:11px;color:#9CA3AF;line-height:1.6;">
          You're getting this because you started signing up for Business Unlocked on May 9, 2026.<br>
          <a href="{{ unsubscribe }}" style="color:#9CA3AF;">Unsubscribe</a>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
```

- [ ] **Step 4: Create `emails/abandoned-3-last-call.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="format-detection" content="telephone=no" />
  <title>Doors closing — last seats for May 9</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&family=Lora:wght@400;500&display=swap" rel="stylesheet" />
  <style>
    body { margin:0; padding:0; background:#1A1A2E; font-family:'Poppins','Helvetica Neue',Arial,sans-serif; }
    .preheader { display:none; visibility:hidden; opacity:0; mso-hide:all; height:0; max-height:0; line-height:0; }
    .container { max-width:600px; margin:0 auto; }
    .h1 { font-size:28px; font-weight:800; color:#FFFFFF; line-height:1.2; margin:0 0 16px; }
    .body { font-family:'Lora',Georgia,serif; color:#E5E7EB; font-size:16px; line-height:1.6; }
    .cta { display:inline-block; background:#F59E0B; color:#1A1A2E; padding:14px 28px; border-radius:8px; text-decoration:none; font-weight:700; }
    .urgent { background:#7F1D1D; color:#FECACA; padding:8px 14px; border-radius:6px; display:inline-block; font-size:13px; font-weight:600; letter-spacing:0.5px; text-transform:uppercase; }
    @media (max-width:600px) { .h1 { font-size:24px; } }
  </style>
</head>
<body>
  <span class="preheader">Final week. After this email I won't follow up again.</span>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#1A1A2E;">
    <tr><td align="center" style="padding:24px 16px;">
      <table role="presentation" class="container" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;">

        <tr><td align="center" style="padding:8px 0 32px;">
          <h1 style="margin:0;font-size:22px;font-weight:800;letter-spacing:2px;text-transform:uppercase;color:#FFFFFF;">BUSINESS UNLOCKED</h1>
        </td></tr>

        <tr><td style="background:#16213E;border-radius:12px;padding:32px 24px;">
          <p style="text-align:center;margin:0 0 20px;"><span class="urgent">⏳ Final Week</span></p>
          <p class="h1">Last call for May 9</p>
          <p class="body">Hi {{ contact.FNAME }},</p>
          <p class="body">This is the last email I'll send about the summit. I'm not going to chase you a fourth time — promise.</p>
          <p class="body">Two reasons to lock in now:</p>
          <p class="body">
            <strong style="color:#F59E0B;">1. The room is closing.</strong> PTTC Manila caps us at 2,000 seats. Once we're full, we're full — no waitlist, no last-minute door sales.
          </p>
          <p class="body">
            <strong style="color:#F59E0B;">2. Early Bird ends.</strong> Regular price kicks in immediately when the timer runs out. The price you saw when you started signing up is the lowest you'll ever pay.
          </p>
          <p class="body" style="margin:24px 0;">If you've been waiting for a sign — this is the boring version of one. Here's the door:</p>
          <p style="text-align:center;margin:24px 0;">
            <a href="https://www.exponential-university.live/the-new-business-normal#pricing?utm_source=email&amp;utm_medium=abandoned&amp;utm_campaign=abandoned-3" class="cta">Save My Seat →</a>
          </p>
          <p class="body" style="font-size:14px;color:#9CA3AF;">If you've decided this isn't for you right now, no hard feelings — just hit unsubscribe and I'll stop emailing.</p>
          <p class="body" style="margin-top:24px;">See you May 9 (I hope),<br>The Business Unlocked Team</p>
        </td></tr>

        <tr><td align="center" style="padding:24px 16px;font-family:'Poppins',sans-serif;font-size:11px;color:#9CA3AF;line-height:1.6;">
          You're getting this because you started signing up for Business Unlocked on May 9, 2026.<br>
          <a href="{{ unsubscribe }}" style="color:#9CA3AF;">Unsubscribe</a>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
```

- [ ] **Step 5: Commit**

```bash
git add emails/abandoned-1-still-thinking.html emails/abandoned-2-what-changes.html emails/abandoned-3-last-call.html
git commit -m "feat(emails): add 3 abandoned-cart email templates for Brevo upload"
```

---

## Task 11: Append Brevo setup section to `docs/sync-setup.md`

**Files:**
- Modify: `docs/sync-setup.md`

- [ ] **Step 1: Append a new `## 6. Brevo abandoned-cart setup` section**

Add this to the end of `docs/sync-setup.md`:

```markdown

## 6. Brevo abandoned-cart setup

These steps activate the abandoned-cart email sequence (3 emails over ~10 days). One-time setup, ~20 min.

### Create the two contact lists

1. Open <https://app.brevo.com/contact/list-listing>.
2. **Create List → name: `BU Abandoned Cart`**. After creation, note the integer ID shown in the URL (`/contact/list/<ID>/...`). You'll need it for `BREVO_ABANDONED_LIST_ID`.
3. **Create List → name: `BU Paid — Exclude`**. Note its integer ID for `BREVO_EXCLUDE_LIST_ID`.

### Upload the 3 email templates

For each of these files in `emails/`, paste the HTML into Brevo Templates (don't upload the file directly — Brevo's editor expects HTML body):

1. <https://app.brevo.com/templates>  → New Template.
2. **Template name:** `abandoned-1-still-thinking` — paste from `emails/abandoned-1-still-thinking.html`. Subject line: `Still thinking it over?`
3. **Template name:** `abandoned-2-what-changes` — paste from `emails/abandoned-2-what-changes.html`. Subject: `What actually changes after the summit`
4. **Template name:** `abandoned-3-last-call` — paste from `emails/abandoned-3-last-call.html`. Subject: `Last email about Business Unlocked`

Brevo's `{{ unsubscribe }}` and `{{ contact.FNAME }}` merge tags are already wired in the HTML.

### Build the automation

1. <https://app.brevo.com/automation/scenarios>  → New Workflow → start from blank.
2. **Trigger:** Contact added to a list → select `BU Abandoned Cart`.
3. **Step 1: Send email** — pick template `abandoned-1-still-thinking`. No wait before this step.
4. **Step 2: Wait** → 3 days.
5. **Step 3: Condition** → if contact is in list `BU Paid — Exclude` → Exit workflow.
6. **Step 4: Send email** → `abandoned-2-what-changes`.
7. **Step 5: Wait** → 4 days.
8. **Step 6: Condition** → if contact is in `BU Paid — Exclude` → Exit.
9. **Step 7: Send email** → `abandoned-3-last-call`.
10. Save and **activate** the workflow.

### Add the secrets to Vercel

In Vercel project settings → Environment Variables:

| Name | Value |
|---|---|
| `BREVO_API_KEY` | Brevo → SMTP & API → API Keys → reveal the v3 key |
| `BREVO_ABANDONED_LIST_ID` | Integer from step 1.2 |
| `BREVO_EXCLUDE_LIST_ID` | Integer from step 1.3 |

### Done

The cron at `*/15 * * * *` will start populating both lists. Watch the abandoned-cart status indicator on `/admin` — it shows `Abandoned-cart: Xm ago • N pushed, M excluded`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/sync-setup.md
git commit -m "docs: add Brevo abandoned-cart setup section"
```

---

## Task 12: Manual end-to-end verification

Mostly Paolo's work — code can't test "did Brevo actually fire the email" without a real account. Verify the chain.

- [ ] **Step 1: Run the local test suite one final time**

```bash
cd "/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit"
source .venv/bin/activate
pytest tests/ -v
```

Expected: 52 passed (34 sync + 18 abandoned).

- [ ] **Step 2: Push and let Vercel deploy**

```bash
git push
```

Wait for the new deploy to be "Ready" in Vercel. Confirm both crons appear in Settings → Crons:
- `/api/sync-payments` `*/15 * * * *`
- `/api/abandoned-cart` `*/15 * * * *`

- [ ] **Step 3: Trigger the abandoned-cart endpoint manually**

```bash
curl -s -H "Authorization: Bearer YOUR_CRON_SECRET" \
  https://www.exponential-university.live/api/abandoned-cart
```

Expected response: JSON with `success: true`, `abandoned_pushed: <N>`, `excluded_pushed: <M>`.

- [ ] **Step 4: Verify the audit log row**

In Supabase SQL Editor:

```sql
select * from new_business_normal_brevo_log
order by started_at desc
limit 1;
```

Expected: a row with sensible counts.

- [ ] **Step 5: Verify contacts landed in the Brevo lists**

Open Brevo → Contacts → Lists → `BU Abandoned Cart` → confirm the abandoned participants appear. Then check `BU Paid — Exclude` for the paid ones.

- [ ] **Step 6: End-to-end with a test signup**

1. Open the sales page in incognito.
2. Fill the participant form with a NEW email you control (don't pay).
3. Wait > 3 hours (or temporarily reduce `abandon_age_hours=3` to `0` in `api/abandoned_cart.py` for the test, then revert).
4. Trigger the cron manually via curl.
5. Confirm Brevo automation fires Email 1 to that address.

- [ ] **Step 7: Update memory**

Save a project memory noting that the abandoned-cart sequence is live, including the cron path, list IDs, and where to check the audit log.

---

## Self-Review

**1. Spec coverage:**
- Migration → Task 1 ✓
- Hard cutoff → Task 2 ✓
- find_abandoned + find_newly_paid query helpers → Task 3 ✓
- Brevo payload builder → Task 4 ✓
- HTTP layer for Supabase + Brevo → Task 5 ✓
- Orchestrator with paid-set filter + exclusion-list-still-runs-past-cutoff → Task 6 ✓
- Vercel handler + cron + env vars → Task 7 ✓
- `handle_abandoned_log` for dashboard → Task 8 ✓
- Dashboard status indicator → Task 9 ✓
- 3 email templates → Task 10 ✓
- Brevo setup docs → Task 11 ✓
- Manual verification → Task 12 ✓
- Brevo API contract (POST /v3/contacts with `updateEnabled: true`) → Task 5 ✓
- Error handling per phase → Task 6 ✓
- Hard cutoff stops abandoned push but exclusion still runs → Task 6 (`test_run_past_cutoff_skips_abandoned_but_still_excludes`) ✓
- Audit log on every run → Task 6 (`test_run_writes_audit_log_with_counts`) ✓

**2. Placeholder scan:** No "TBD"/"TODO"/"similar to task N" strings. Every code-block step is complete code.

**3. Type consistency:**
- Orchestrator parameter names (`fetch_paid_contacts`, `fetch_participants`, `push_to_brevo`, `mark_abandoned`, `mark_excluded`, `write_log`) used identically in Task 6 tests, Task 6 implementation, and Task 7 handler wiring.
- `build_brevo_contact_payload(participant, list_id)` signature consistent across Tasks 4, 5, 6.
- Dict keys (`abandoned_pushed`, `excluded_pushed`, `errors`, `success`, `started_at`, `finished_at`) consistent across orchestrator → audit log → report.py endpoint → admin-sales.js render.

Plan complete.
