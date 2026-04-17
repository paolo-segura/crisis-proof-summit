"""
sync_payments — Core module for the BU Payments Bridge sync.

Every 15 minutes (triggered via Vercel cron from api/sync-payments.py):
  1. Reads the BU Payments Bridge Google Sheet via Sheets API
  2. Parses each row into a purchase record
  3. Upserts into new_business_normal_purchases (by order_id)
  4. Re-matches unmatched purchases (last 7 days) against participants
  5. Logs the run to new_business_normal_sync_log

Protected by CRON_SECRET header (enforced in the Vercel handler).
"""

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
    Strip non-digits, return last 10 digits.
    Returns '' if fewer than 10 digits (ambiguous — we refuse to match).
    Handles '63xxx', '0xxx', '+63xxx', 'xxx' uniformly by taking last 10.
    """
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) < 10:
        return ""
    return digits[-10:]


def parse_tier(raw_product):
    """
    Extract tier from a product label like 'BUSINESS UNLOCKED | VIP'
    and normalize to the lowercase_underscore form used in the database
    (matches the ticket_tier values written by the click-logger).

    Examples:
      'THE NEW BUSINESS NORMAL | VIP' -> 'vip'
      'FOO | Early Bird'              -> 'early_bird'
      'FOO | Early  Bird'             -> 'early_bird'  (collapses whitespace)
      None                            -> ''
    """
    if not raw_product:
        return ""
    parts = str(raw_product).split("|")
    raw_tier = parts[-1].strip().lower()
    # Collapse any run of whitespace to a single underscore
    return re.sub(r"\s+", "_", raw_tier)


# ---------------------------------------------------------------------------
# Row parser (header-based — resilient to Scale Your Org column changes)
# ---------------------------------------------------------------------------

# Canonical field → accepted header names (normalized: lowercased, trimmed,
# underscores → spaces). Scale Your Org has a history of renaming, reordering,
# and inserting columns mid-sheet (see the 'UTM SOURSE' typo they inserted at
# col 9 on 2026-04-17). Matching by header name instead of fixed index keeps
# us immune to their next surprise.
_COL_ALIASES = {
    "event_status":   ["event status"],
    "full_name":      ["full name"],
    "email":          ["email"],
    "mobile":         ["phone number", "phone", "mobile", "mobile number"],
    "product":        ["product name", "product"],
    "amount":         ["iterm pric", "item price", "price", "amount"],
    "quantity":       ["quantity"],
    "total":          ["total price", "total"],
    "order_id":       ["reference number", "transaction number", "order id"],
    "payment_status": ["status"],               # "later occurrence wins" handles the two-Status-columns case
    "paid_at":        ["paid at"],
    "utm_source":     ["utm source", "utm sourse"],   # catches their current typo
    "utm_medium":     ["utm medium"],
    "utm_campaign":   ["utm campaign"],
    "utm_content":    ["utm content"],
    "session_id":     ["bu session id", "session id", "nbn session id"],
}

# Essential columns — if any are missing from the header, we refuse to
# process the sheet instead of silently skipping every row.
_REQUIRED_COLS = ("event_status", "email", "order_id")

# Business Unlocked ticket tiers. Rows for other products (e.g. "Emerge Book")
# share the same Xendit gateway but belong to a different dashboard, so we skip them.
_BU_TIERS = frozenset({"early_bird", "regular", "vip"})


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


def _normalize_header(name):
    """Lowercase, trim, collapse whitespace, underscore → space."""
    if name is None:
        return ""
    s = str(name).strip().lower().replace("_", " ")
    return re.sub(r"\s+", " ", s)


def build_col_map(header_row):
    """Resolve canonical field → column index from the sheet's header row.

    When the sheet has two columns with the same normalized name (the BU bridge
    sheet has two 'Status' columns — col 1 mirrors the event prefix, col 17 is
    the real order state), the later index wins. That's intentional: the real
    order status is what we want for payment_status.
    """
    if not header_row:
        return {}
    name_to_idx = {}
    for i, raw in enumerate(header_row):
        key = _normalize_header(raw)
        if key:
            name_to_idx[key] = i  # later wins for duplicates
    resolved = {}
    for canonical, aliases in _COL_ALIASES.items():
        for alias in aliases:
            if alias in name_to_idx:
                resolved[canonical] = name_to_idx[alias]
                break
    return resolved


def _cell(row, col_map, key, default=""):
    """Read a cell by canonical key; returns default when the column is missing
    or the row is shorter than the header (trailing-empties truncation)."""
    idx = col_map.get(key)
    if idx is None or idx >= len(row):
        return default
    val = row[idx]
    return default if val is None else val


def parse_row(row, col_map):
    """Parse one data row into a purchase dict using `col_map` from build_col_map.

    Returns None if the row:
      - is empty
      - isn't a `purchase.*` event (handles blank rows / non-purchase events)
      - has no order_id
      - is for a non-BU product (Emerge Book / test products share the gateway)
    """
    if not row:
        return None

    event = _normalize_header(_cell(row, col_map, "event_status"))
    if not event.startswith("purchase."):
        return None

    order_id = str(_cell(row, col_map, "order_id")).strip()
    if not order_id:
        return None

    ticket_tier = parse_tier(_cell(row, col_map, "product"))
    if ticket_tier not in _BU_TIERS:
        return None

    def _opt(key):
        """Return stripped non-empty string or None — for session_id (UUID kept exact)."""
        v = str(_cell(row, col_map, key)).strip()
        return v if v else None

    def _opt_lc(key):
        """Same as _opt but lowercased — UTM values are case-normalized so
        'Prime' and 'prime' aggregate to a single source on the dashboard.
        Defends against case drift from GHL, manual share links, or ad tag typos."""
        v = str(_cell(row, col_map, key)).strip().lower()
        return v if v else None

    paid_at_raw = str(_cell(row, col_map, "paid_at")).strip()

    return {
        "order_id":         order_id,
        "full_name":        str(_cell(row, col_map, "full_name")).strip(),
        "email":            normalize_email(_cell(row, col_map, "email")),
        "mobile":           normalize_mobile(_cell(row, col_map, "mobile")),
        "ticket_tier":      ticket_tier,
        "amount":           _safe_float(_cell(row, col_map, "amount")),
        "quantity":         _safe_int(_cell(row, col_map, "quantity")),
        "total":            _safe_float(_cell(row, col_map, "total")),
        "payment_provider": "",   # no dedicated header in current Scale Your Org layout
        "payment_status":   str(_cell(row, col_map, "payment_status")).strip().upper(),
        "paid_at":          paid_at_raw if paid_at_raw else None,
        "session_id":       _opt("session_id"),       # UUID — keep exact casing
        "utm_source":       _opt_lc("utm_source"),
        "utm_medium":       _opt_lc("utm_medium"),
        "utm_campaign":     _opt_lc("utm_campaign"),
        "utm_content":      _opt_lc("utm_content"),
        "raw_row":          list(row),
    }


# ---------------------------------------------------------------------------
# Participant matcher
# ---------------------------------------------------------------------------

def _pick_best_candidate(candidates, paid_at):
    """
    Given a list of participant dicts that all match on email or mobile,
    prefer the most recent created_at < paid_at.
    If all were created AFTER paid_at, return the most recent overall.
    Handles None created_at defensively.
    """
    if not candidates:
        return None

    def key(p):
        return p.get("created_at") or ""

    before = [p for p in candidates if paid_at and key(p) and key(p) < paid_at]
    pool = before if before else candidates
    return max(pool, key=key)


def match_purchase_to_participant(purchase, participants):
    """
    Returns (participant_id, match_method) where match_method is
    'session_id', 'email', 'mobile', or 'direct'.

    Match priority is session_id → email → mobile, then 'direct' if none hit.
    session_id is the strongest signal (unique per browser, set before form
    submit), so we check it first. It's populated on the purchase when Scale
    Your Org forwards our checkout query param into the Bridge Sheet.

    `participants` is a list of dicts containing at minimum:
    id, email, mobile_number, session_id, created_at.
    """
    session_id = purchase.get("session_id") or ""
    email = purchase.get("email") or ""
    mobile = purchase.get("mobile") or ""
    paid_at = purchase.get("paid_at") or ""

    if session_id:
        hits = [p for p in participants if p.get("session_id") == session_id]
        chosen = _pick_best_candidate(hits, paid_at)
        if chosen:
            return chosen["id"], "session_id"

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
    Header rows, if any, are returned as-is — parse_row skips short rows.
    """
    sheet_id = os.environ.get("BRIDGE_SHEET_ID")
    tab = os.environ.get("BRIDGE_SHEET_TAB", "payments")
    if not sheet_id:
        raise EnvironmentError("Missing BRIDGE_SHEET_ID")

    svc = _sheets_service()

    # Force refresh: a get() on the spreadsheet triggers IMPORTRANGE re-evaluation.
    # The values().get() that follows then reads the refreshed values.
    svc.spreadsheets().get(spreadsheetId=sheet_id).execute()

    # Read A:AZ (52 columns). Scale Your Org has a history of inserting columns
    # mid-sheet without notice (UTM SOURSE added at col 9 on 2026-04-17 pushed
    # the real Status to col R, truncating it under the old A:Q range and
    # breaking every downstream parse). A:AZ gives them ~35 columns of runway
    # before we'd ever need to touch this again. Google Sheets only returns
    # populated cells so the wider range costs nothing.
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{tab}!A:AZ",
    ).execute()

    return result.get("values", [])


# ---------------------------------------------------------------------------
# Supabase PostgREST helpers (stdlib only, matches api/report.py pattern)
# ---------------------------------------------------------------------------

import urllib.request
import urllib.error
from urllib.parse import quote

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
    """Generic PostgREST request. Returns parsed JSON (list or dict) or [] on empty body.

    On HTTP errors, includes Supabase's response body in the raised exception so the
    sync log surfaces the actual PostgREST error (e.g. 'column X does not exist',
    '42P10: no unique constraint for ON CONFLICT') instead of a bare 'HTTP 400'.
    """
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

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return []
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        # Truncate to keep sync_log rows compact; first 500 chars is always enough
        # for a PostgREST error payload.
        snippet = body_text[:500]
        raise RuntimeError(
            f"Supabase {method} {path.split('?')[0]} failed: "
            f"{exc.code} {exc.reason} - {snippet}"
        ) from exc


def supabase_upsert_purchase(purchase, participant_id, match_method, utm_fields):
    """
    Upsert one row into new_business_normal_purchases by order_id.
    utm_fields is a dict with utm_source/medium/campaign/content (may have None values).
    """
    row = {
        "order_id":         purchase["order_id"],
        "email":            purchase["email"],
        "mobile":           purchase["mobile"],
        "full_name":        purchase["full_name"],
        "ticket_tier":      purchase["ticket_tier"],
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
    # Requires a UNIQUE constraint on the conflict target — we have one on order_id
    # (partial, WHERE order_id IS NOT NULL) from the 2026-04-14 migration.
    _supabase_request(
        "POST",
        f"{PURCHASES_TABLE}?on_conflict=order_id",
        body=row,
        extra_headers={
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )


def supabase_fetch_participants_by_contacts(emails, mobiles, session_ids=None):
    """
    Fetch participants whose email is in `emails` OR mobile_number matches any
    of `mobiles` OR session_id is in `session_ids`. All args are sets (or None).

    Mobile matching: participants.mobile_number is stored raw (e.g. '+639178334375',
    '09178334375'). We overfetch candidates by using ilike *{last_10_digits}*,
    then the caller (matcher) re-normalizes via normalize_mobile to get an exact
    match.
    """
    if not emails and not mobiles and not session_ids:
        return []

    clauses = []
    if emails:
        # PostgREST `in` filter: email=in.(a@x.com,b@y.com)
        quoted = ",".join(f"\"{e}\"" for e in emails)
        clauses.append(f"email.in.({quoted})")
    if mobiles:
        # PostgREST `or` over ilike matches on last-10-digit substrings
        mobile_clauses = ",".join(f"mobile_number.ilike.*{m}*" for m in mobiles)
        clauses.append(f"or({mobile_clauses})") if len(mobiles) > 1 else clauses.append(
            f"mobile_number.ilike.*{next(iter(mobiles))}*"
        )
    if session_ids:
        quoted = ",".join(f"\"{s}\"" for s in session_ids)
        clauses.append(f"session_id.in.({quoted})")

    if len(clauses) == 1:
        filter_expr = clauses[0]
    else:
        filter_expr = "or=(" + ",".join(clauses) + ")"

    select = "id,email,mobile_number,session_id,created_at,utm_source,utm_medium,utm_campaign,utm_content"
    path = f"{PARTICIPANTS_TABLE}?select={select}&{filter_expr}"

    return _supabase_request("GET", path) or []


def supabase_fetch_unmatched_purchases(days=7):
    """Fetch purchases with NULL participant_id and paid_at within N days."""
    import datetime
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=days)).isoformat()
    path = (
        f"{PURCHASES_TABLE}"
        f"?select=order_id,email,mobile,paid_at"
        f"&participant_id=is.null"
        f"&paid_at=gte.{cutoff}"
    )
    return _supabase_request("GET", path) or []


def supabase_update_purchase_match(order_id, participant_id, match_method, utm_fields):
    """PATCH a purchase by order_id to attach it to a participant with UTM attribution."""
    body = {
        "participant_id": participant_id,
        "match_method":   match_method,
        "utm_source":     utm_fields.get("utm_source"),
        "utm_medium":     utm_fields.get("utm_medium"),
        "utm_campaign":   utm_fields.get("utm_campaign"),
        "utm_content":    utm_fields.get("utm_content"),
    }
    path = f"{PURCHASES_TABLE}?order_id=eq.{quote(order_id)}"
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


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _iso_now():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _utm_from_participant(p):
    """Legacy helper — still used by the rematch path where only participant UTM
    is available (unmatched purchases re-read from DB don't carry sheet UTM)."""
    return {
        "utm_source":   p.get("utm_source"),
        "utm_medium":   p.get("utm_medium"),
        "utm_campaign": p.get("utm_campaign"),
        "utm_content":  p.get("utm_content"),
    }


def _resolve_utm(purchase, participant):
    """Pick UTM for the upsert. Sheet-side UTM (on the purchase dict) wins —
    it's the attribution at the moment of payment. Participant UTM is fallback
    for any field the sheet doesn't provide.
    """
    def pick(key):
        pv = purchase.get(key)
        if pv:
            return pv
        return participant.get(key) if participant else None
    return {
        "utm_source":   pick("utm_source"),
        "utm_medium":   pick("utm_medium"),
        "utm_campaign": pick("utm_campaign"),
        "utm_content":  pick("utm_content"),
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

    The first row of `read_rows()` output is treated as the sheet header and
    used to build a column-name → index map. Data rows start at row[1:].
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

        header = raw_rows[0] if raw_rows else []
        col_map = build_col_map(header)
        missing = [k for k in _REQUIRED_COLS if k not in col_map]
        parsed = []
        if missing:
            errors.append({
                "phase": "header",
                "error": f"Sheet missing required columns: {missing}",
                "header_preview": str(header)[:300],
            })
        else:
            for r in raw_rows[1:]:
                try:
                    purchase = parse_row(r, col_map)
                    if purchase is not None:
                        parsed.append(purchase)
                except Exception as exc:  # noqa: BLE001
                    errors.append({"phase": "parse", "error": str(exc), "row_preview": str(r)[:120]})

        # ---- Phase 2: batch fetch candidate participants ----
        emails = {p["email"] for p in parsed if p["email"]}
        mobiles = {p["mobile"] for p in parsed if p["mobile"]}
        session_ids = {p["session_id"] for p in parsed if p.get("session_id")}
        participants = (
            fetch_participants(emails, mobiles, session_ids)
            if (emails or mobiles or session_ids) else []
        )

        # ---- Phase 3: match + upsert each purchase ----
        for purchase in parsed:
            try:
                pid, method = match_purchase_to_participant(purchase, participants)
                matched_p = None
                if pid:
                    matched_p = next(p for p in participants if p["id"] == pid)
                    rows_matched += 1
                utm = _resolve_utm(purchase, matched_p)
                upsert(purchase, pid, method, utm)
                rows_upserted += 1
                if not pid:
                    rows_unmatched += 1
            except Exception as exc:  # noqa: BLE001
                errors.append({
                    "phase": "upsert",
                    "error": str(exc),
                    "order_id": purchase.get("order_id"),
                })

        # ---- Phase 4: re-match older unmatched purchases ----
        # Note: unmatched rows re-read from DB don't carry session_id, so we
        # fall back to email/mobile here. session_id match already happened on
        # the initial sync for any row that had it.
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
                        update_match(u["order_id"], pid, method, _utm_from_participant(matched_p))
                        rows_matched += 1
                        rows_unmatched = max(0, rows_unmatched - 1)
                except Exception as exc:  # noqa: BLE001
                    errors.append({
                        "phase": "rematch",
                        "error": str(exc),
                        "order_id": u.get("order_id"),
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
