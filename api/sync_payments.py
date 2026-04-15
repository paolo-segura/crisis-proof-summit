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
