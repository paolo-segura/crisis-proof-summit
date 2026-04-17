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
# Row parser
# ---------------------------------------------------------------------------

# Column indexes for Scale Your Org row layout.
# Documented in docs/sync-setup.md. Changes here must also update SAMPLE_ROW
# in tests/test_sync_payments.py.
_COL_EVENT_STATUS = 0   # "purchase.pending" / "purchase.success" — used to skip header + non-purchase rows
_COL_FULL_NAME = 2
_COL_EMAIL = 3
_COL_MOBILE = 4
_COL_PRODUCT = 5
_COL_AMOUNT = 6
_COL_QUANTITY = 7
_COL_TOTAL = 8
_COL_ORDER_ID = 9
_COL_PROVIDER = 12
_COL_PAYMENT_STATUS = 16  # real order status (PENDING / PAID). Col 14 is a Xendit amount-mode flag that's always "FULLY_PAID".
_COL_PAID_AT = 15
_MIN_COLS = 17

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


def parse_row(row):
    """
    Parse one Scale Your Org row into a purchase dict keyed for the
    new_business_normal_purchases table.

    Returns None if the row:
      - is too short (sheet header/blank rows)
      - isn't a `purchase.*` event (skips the literal header row whose col 0 is "Event Status")
      - has no order_id
      - is for a non-BU product (the gateway is shared with other clients; we only
        ingest Business Unlocked tiers into this table)
    """
    if not row or len(row) < _MIN_COLS:
        return None

    event = str(row[_COL_EVENT_STATUS]).strip().lower() if row[_COL_EVENT_STATUS] else ""
    if not event.startswith("purchase."):
        return None

    order_id = str(row[_COL_ORDER_ID]).strip() if row[_COL_ORDER_ID] else ""
    if not order_id:
        return None

    ticket_tier = parse_tier(row[_COL_PRODUCT])
    if ticket_tier not in _BU_TIERS:
        return None

    return {
        "order_id":         order_id,
        "full_name":        str(row[_COL_FULL_NAME]).strip() if row[_COL_FULL_NAME] else "",
        "email":            normalize_email(row[_COL_EMAIL]),
        "mobile":           normalize_mobile(row[_COL_MOBILE]),
        "ticket_tier":      ticket_tier,
        "amount":           _safe_float(row[_COL_AMOUNT]),
        "quantity":         _safe_int(row[_COL_QUANTITY]),
        "total":            _safe_float(row[_COL_TOTAL]),
        "payment_provider": str(row[_COL_PROVIDER]).strip().lower() if row[_COL_PROVIDER] else "",
        "payment_status":   str(row[_COL_PAYMENT_STATUS]).strip().upper() if row[_COL_PAYMENT_STATUS] else "",
        "paid_at":          str(row[_COL_PAID_AT]).strip() if row[_COL_PAID_AT] else None,
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
    'email', 'mobile', or 'direct'.

    `participants` is a list of dicts (already fetched from Supabase) containing
    at minimum: id, email, mobile_number, created_at.
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

    # Read A:Q (17 columns — matches Scale Your Org row width)
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{tab}!A:Q",
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


def supabase_fetch_participants_by_contacts(emails, mobiles):
    """
    Fetch participants whose email is in `emails` OR whose mobile_number matches
    any of `mobiles`. Both args are sets of normalized strings.

    Mobile matching is tricky: participants.mobile_number is stored in raw form
    (e.g. '+639178334375', '09178334375'). We overfetch candidates by using
    ilike *{last_10_digits}*, then the caller (matcher) re-normalizes via
    normalize_mobile to get an exact match.
    """
    if not emails and not mobiles:
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

    if len(clauses) == 1:
        filter_expr = clauses[0]
    else:
        filter_expr = "or=(" + ",".join(clauses) + ")"

    select = "id,email,mobile_number,created_at,utm_source,utm_medium,utm_campaign,utm_content"
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
        participants = fetch_participants(emails, mobiles) if (emails or mobiles) else []

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
                    "order_id": purchase.get("order_id"),
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
