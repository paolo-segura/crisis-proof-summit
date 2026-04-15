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
_COL_FULL_NAME = 2
_COL_EMAIL = 3
_COL_MOBILE = 4
_COL_PRODUCT = 5
_COL_AMOUNT = 6
_COL_QUANTITY = 7
_COL_TOTAL = 8
_COL_ORDER_ID = 9
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
    Parse one Scale Your Org row into a purchase dict keyed for the
    new_business_normal_purchases table.
    Returns None if the row is too short or missing an order_id.
    """
    if not row or len(row) < _MIN_COLS:
        return None

    order_id = str(row[_COL_ORDER_ID]).strip() if row[_COL_ORDER_ID] else ""
    if not order_id:
        return None

    return {
        "order_id":         order_id,
        "full_name":        str(row[_COL_FULL_NAME]).strip() if row[_COL_FULL_NAME] else "",
        "email":            normalize_email(row[_COL_EMAIL]),
        "mobile":           normalize_mobile(row[_COL_MOBILE]),
        "ticket_tier":      parse_tier(row[_COL_PRODUCT]),
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

    return None, "direct"
