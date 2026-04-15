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
