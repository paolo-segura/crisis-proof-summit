"""
sync_manual_sales — Manual / off-platform ticket sync for the BU dashboard.

Reads the client-maintained "BUS: Leads" Google Sheet, where Crisis Summit
logs warm-lead, partner, and bulk-discount ticket sales that don't go
through the website checkout. Inserts those rows into
new_business_normal_purchases tagged with `payment_provider = 'manual'`
so the existing /admin dashboard rolls them into Total Sales / Total
Revenue automatically.

Triggered every 30 minutes via vercel.json -> /api/sync-manual-sales,
auth'd with CRON_SECRET.

The sheet has 7 tabs in two shapes:
  1. Warm   - free-form. One row per company, multi-line Names cell,
              single Payment total. Split evenly across parsed names.
  2. Form-style (Bulk 1000/1500, Grit & Grace, DF/SP, Organic) - one row
     per attendee with a "Select Registration Type" cell that contains the
     price as "P1000" / "P1500".
  3. Complimentary - free tickets, no Payment column - tab is skipped
     entirely (rule from Paolo: only count rows where Payment is filled).

Idempotency: order_id is a deterministic hash of (tab, identity_key) so
re-syncs upsert in place. Editing a typo in the amount keeps the same
order_id, just updates the row.
"""

import hashlib
import json
import os
import re


# ---------------------------------------------------------------------------
# Tab configuration
# ---------------------------------------------------------------------------

WARM_TAB = "BUS: Warm"

# Form-style tabs. tier value is what we write to ticket_tier; default_amount
# is the fallback price when the row's Registration Type cell can't be parsed.
FORM_TABS = {
    "Bulk 1500":              {"tier": "bulk_1500",   "default_amount": 1500},
    "Bulk 1000":              {"tier": "bulk_1000",   "default_amount": 1000},
    "Grit and Grace Network": {"tier": "ggn",         "default_amount": None},
    "DF/SP Distributors":     {"tier": "df_sp",       "default_amount": None},
    "Organic":                {"tier": "organic",     "default_amount": None},
}

# Complimentary is intentionally NOT synced - per Paolo's rule, only count
# rows where Payment is filled. Complimentary has no Payment column.

# Form-tab column aliases - resolved by header name to stay resilient if the
# client reorders columns.
_FORM_COL_ALIASES = {
    "timestamp":     ["timestamp"],
    "full_name":     ["full name", "name"],
    "mobile":        ["mobile number", "mobile", "phone number", "phone"],
    "email":         ["email address", "email"],
    "registration":  ["select registration type", "registration type"],
    "payment_proof": ["upload proof of payment:", "upload proof of payment"],
    "referrer":      ["who referred you to this event?", "who referred you to this event"],
    "attendance":    ["how would you like to attend?", "how would you like to attend"],
}

# Warm-tab column aliases.
_WARM_COL_ALIASES = {
    "tag":      [""],            # col A is unlabeled ('warm')
    "company":  ["company name"],
    "names":    ["name", "names"],
    "payment":  ["payment"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_header(name):
    """Lowercase + trim + collapse whitespace, taking only the first line.

    Google Form-generated sheets cram the question text PLUS the help
    description into a single header cell separated by '\\n'. e.g.
        "Upload Proof of Payment:\\nUpload your payment screenshot..."
    Without splitting first, the normalized form is the entire blob, and no
    alias would ever match. Take the first line as the canonical name.
    """
    if name is None:
        return ""
    first_line = str(name).split("\n", 1)[0]
    return re.sub(r"\s+", " ", first_line.strip().lower().replace("_", " "))


def _slug(s):
    """Lowercase + collapse non-alphanumerics to '-'. Used in stable order_ids."""
    if not s:
        return ""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", str(s).strip().lower())).strip("-")


def _hash8(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def make_order_id(tab, identity):
    """Stable order_id from tab + identity tuple. Same identity -> same id,
    so editing a typo in amount upserts in place instead of creating a duplicate."""
    h = _hash8(f"{tab}||{identity}")
    return f"MANUAL-{_slug(tab).upper()}-{h}"


def parse_payment_amount(raw):
    """Parse '14,000', 'P1500', '1000.00', '?1,500.50' etc. -> float, or 0.0
    when the cell is empty / can't be parsed.

    A *non-numeric but non-empty* cell ('TBD', 'pending') returns 0.0 - the
    caller treats 0.0 as "Payment not filled" and skips the row.
    """
    if raw is None:
        return 0.0
    s = str(raw).strip()
    if not s:
        return 0.0
    digits = re.sub(r"[^0-9.]", "", s)
    if not digits or digits == ".":
        return 0.0
    try:
        return float(digits)
    except ValueError:
        return 0.0


def build_col_map(header_row, aliases):
    """Resolve canonical field -> column index by header name.
    Header lookups are normalized (lowercase, trimmed). Later occurrences win."""
    if not header_row:
        return {}
    name_to_idx = {}
    for i, raw in enumerate(header_row):
        name_to_idx[_normalize_header(raw)] = i  # later wins
    resolved = {}
    for canonical, alias_list in aliases.items():
        for alias in alias_list:
            if alias in name_to_idx:
                resolved[canonical] = name_to_idx[alias]
                break
    return resolved


def _cell(row, col_map, key, default=""):
    idx = col_map.get(key)
    if idx is None or idx >= len(row):
        return default
    val = row[idx]
    return default if val is None else val


# ---------------------------------------------------------------------------
# Warm tab - parse one row into N attendee purchases
# ---------------------------------------------------------------------------

# Matches numbered list items inside the multi-line Names cell:
#   "1. Mar Christopher Sison" / "2) Joshua" / "10. Tyok Aguilar"
_NAME_NUMBERED = re.compile(r"^\s*\d+\s*[.)]\s*(.+?)\s*$")

# Matches "John Concina 4 pax" - a single name plus a pax count.
_NAME_PAX = re.compile(r"^\s*\d*\s*[.)]?\s*(.+?)\s+(\d+)\s*pax\s*$", re.IGNORECASE)


def parse_warm_names(cell):
    """Split a multi-line Names cell into a list of (attendee_name, count)
    tuples. count is usually 1 except when the cell says 'X pax'.

    Examples:
      "1. CJ Estavillo\n2. Earlbin Fabian"   -> [("CJ Estavillo",1),("Earlbin Fabian",1)]
      "1.John Concina 4 pax"                  -> [("John Concina", 4)]
      "1. Mar\n2. Joshua"                     -> [("Mar",1),("Joshua",1)]
      ""                                      -> []

    Returns [] when the cell is empty - caller will fall back to a single
    anonymous attendee for the full payment."""
    if not cell:
        return []
    out = []
    for raw_line in str(cell).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        pax_match = _NAME_PAX.match(line)
        if pax_match:
            name = pax_match.group(1).strip()
            count = int(pax_match.group(2))
            out.append((name, count))
            continue
        num_match = _NAME_NUMBERED.match(line)
        if num_match:
            out.append((num_match.group(1).strip(), 1))
            continue
        # Unnumbered non-empty line - take it as a single attendee
        out.append((line, 1))
    return out


def parse_warm_row(row, col_map, row_idx):
    """Parse one Warm-tab row into a list of purchase dicts (one per attendee).

    Returns [] when:
      - Payment cell is empty / unparseable / 0
      - Company is empty (defensive - shouldn't happen)
    """
    company = str(_cell(row, col_map, "company")).strip()
    if not company:
        return []

    payment = parse_payment_amount(_cell(row, col_map, "payment"))
    if payment <= 0:
        return []  # rule: only count when Payment is filled

    parsed_names = parse_warm_names(_cell(row, col_map, "names"))

    if parsed_names:
        total_pax = sum(count for _, count in parsed_names)
        per_pax_amount = round(payment / total_pax, 2) if total_pax else payment
        purchases = []
        for attendee_name, count in parsed_names:
            for n in range(count):
                # Identity per attendee. When count>1 ("4 pax") we differentiate
                # by suffix so each pax gets a stable but distinct order_id.
                identity = f"{_slug(company)}|{_slug(attendee_name)}|{n}" if count > 1 else f"{_slug(company)}|{_slug(attendee_name)}"
                purchases.append(_warm_purchase(
                    company=company,
                    attendee_name=attendee_name if count == 1 else f"{attendee_name} ({n+1}/{count})",
                    amount=per_pax_amount,
                    identity=identity,
                ))
        return purchases

    # Names cell empty - fall back to a single anonymous attendee for the
    # full payment. Keep the row visible in the dashboard so the operator
    # notices the missing attendee names.
    identity = f"{_slug(company)}|row{row_idx}"
    return [_warm_purchase(
        company=company,
        attendee_name=f"{company} (unnamed)",
        amount=payment,
        identity=identity,
    )]


def _warm_purchase(company, attendee_name, amount, identity):
    return {
        "order_id":         make_order_id(WARM_TAB, identity),
        "full_name":        attendee_name,
        "email":            "",
        "mobile":           "",
        "ticket_tier":      "warm",
        "amount":           amount,
        "quantity":         1,
        "total":            amount,
        "payment_provider": "manual",
        "payment_status":   "PAID",
        "paid_at":          None,
        "session_id":       None,
        "utm_source":       None,
        "utm_medium":       None,
        "utm_campaign":     None,
        "utm_content":      None,
        "match_method":     "manual",
        "raw_row":          {"tab": WARM_TAB, "company": company, "row": list(map(_safe_str, []))},
        "_meta_tab":        WARM_TAB,
        "_meta_company":    company,
    }


# ---------------------------------------------------------------------------
# Form-style tabs - one row per attendee
# ---------------------------------------------------------------------------

def _safe_str(v):
    return "" if v is None else str(v)


def parse_form_row(row, col_map, tab, tier, default_amount):
    """Parse a form-style row into a single purchase dict, or None to skip.

    Skip rules:
      - No Full Name (header / blank row)
      - No payment proof AND no parseable amount in the Registration Type cell
        (rule: only count rows where Payment is filled)
    """
    full_name = str(_cell(row, col_map, "full_name")).strip()
    if not full_name:
        return None

    email = str(_cell(row, col_map, "email")).strip().lower()
    mobile = re.sub(r"\D", "", str(_cell(row, col_map, "mobile")))[-10:] if _cell(row, col_map, "mobile") else ""

    registration = str(_cell(row, col_map, "registration")).strip()
    payment_proof = str(_cell(row, col_map, "payment_proof")).strip()

    # Payment-filled check: either the proof column has a URL or the
    # registration type cell has a parseable peso amount.
    amount = parse_payment_amount(registration)
    if amount <= 0:
        amount = float(default_amount) if default_amount else 0.0

    if amount <= 0 and not payment_proof:
        return None  # not paid yet

    if amount <= 0 and payment_proof:
        # Has proof but unparseable amount - last-ditch fallback to default tier price
        amount = float(default_amount) if default_amount else 0.0
    if amount <= 0:
        return None

    # Identity = email if present, else name+mobile - stable across re-syncs
    if email:
        identity = email
    elif mobile:
        identity = f"{_slug(full_name)}|{mobile}"
    else:
        identity = _slug(full_name)

    return {
        "order_id":         make_order_id(tab, identity),
        "full_name":        full_name,
        "email":            email,
        "mobile":           mobile,
        "ticket_tier":      tier,
        "amount":           amount,
        "quantity":         1,
        "total":            amount,
        "payment_provider": "manual",
        "payment_status":   "PAID",
        "paid_at":          None,  # client sheet has Timestamp but mixed formats; skip parsing
        "session_id":       None,
        "utm_source":       None,
        "utm_medium":       None,
        "utm_campaign":     None,
        "utm_content":      None,
        "match_method":     "manual",
        "raw_row":          {"tab": tab, "row": [_safe_str(v) for v in row]},
        "_meta_tab":        tab,
        "_meta_proof":      payment_proof,
    }


# ---------------------------------------------------------------------------
# Google Sheets reader (per-tab)
# ---------------------------------------------------------------------------

def _sheets_service():
    """Authenticated Sheets client. Same service-account creds as the bridge sync."""
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
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def read_manual_sheet():
    """Read the manual-sales sheet and return {tab_name: [rows]}.
    Forces an IMPORTRANGE/cache refresh by hitting spreadsheets().get() first.
    Returns {} if MANUAL_SALES_SHEET_ID is unset (cron is a no-op until configured)."""
    sheet_id = os.environ.get("MANUAL_SALES_SHEET_ID")
    if not sheet_id:
        return {}

    svc = _sheets_service()
    svc.spreadsheets().get(spreadsheetId=sheet_id).execute()

    tabs_to_read = [WARM_TAB] + list(FORM_TABS.keys())
    result = svc.spreadsheets().values().batchGet(
        spreadsheetId=sheet_id,
        ranges=[f"'{t}'!A:Z" for t in tabs_to_read],
    ).execute()

    out = {}
    for tab, value_range in zip(tabs_to_read, result.get("valueRanges", [])):
        out[tab] = value_range.get("values", [])
    return out


# ---------------------------------------------------------------------------
# Supabase upsert (reuse the bridge sync's helper)
# ---------------------------------------------------------------------------

def supabase_upsert_manual(purchase):
    """Upsert one manual-sales purchase into new_business_normal_purchases.
    Idempotent on order_id (unique partial index from 2026-04-14 migration)."""
    import sync_payments as sp  # noqa: WPS433 - lazy import, same dir
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
        "match_method":     purchase["match_method"],
        "raw_row":          purchase["raw_row"],
    }
    sp._supabase_request(
        "POST",
        f"{sp.PURCHASES_TABLE}?on_conflict=order_id",
        body=row,
        extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
    )


def supabase_write_log(log):
    """Reuse bridge sync's audit-log writer."""
    import sync_payments as sp  # noqa: WPS433
    sp.supabase_write_sync_log(log)


# ---------------------------------------------------------------------------
# Orchestrator (testable via injected I/O)
# ---------------------------------------------------------------------------

def parse_all_tabs(tabs_data):
    """Pure parser: takes {tab: [rows]} and returns a list of purchase dicts.
    No I/O - unit-testable with synthetic data."""
    purchases = []
    parse_errors = []

    # Warm
    warm_rows = tabs_data.get(WARM_TAB, [])
    if warm_rows:
        col_map = build_col_map(warm_rows[0], _WARM_COL_ALIASES)
        if "company" in col_map and "payment" in col_map:
            for i, row in enumerate(warm_rows[1:], start=2):
                try:
                    purchases.extend(parse_warm_row(row, col_map, row_idx=i))
                except Exception as exc:  # noqa: BLE001
                    parse_errors.append({"tab": WARM_TAB, "row": i, "error": str(exc)})
        else:
            parse_errors.append({"tab": WARM_TAB, "error": "missing required columns"})

    # Form-style tabs
    for tab, cfg in FORM_TABS.items():
        rows = tabs_data.get(tab, [])
        if not rows:
            continue
        col_map = build_col_map(rows[0], _FORM_COL_ALIASES)
        if "full_name" not in col_map:
            parse_errors.append({"tab": tab, "error": "missing Full Name column"})
            continue
        for i, row in enumerate(rows[1:], start=2):
            try:
                p = parse_form_row(row, col_map, tab, cfg["tier"], cfg["default_amount"])
                if p is not None:
                    purchases.append(p)
            except Exception as exc:  # noqa: BLE001
                parse_errors.append({"tab": tab, "row": i, "error": str(exc)})

    return purchases, parse_errors


def _iso_now():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run_sync(read_tabs, upsert, write_log):
    """One sync cycle. All I/O injected. Returns a result dict and writes
    a row to new_business_normal_sync_log (best-effort)."""
    started_at = _iso_now()
    errors = []
    rows_read = 0
    rows_upserted = 0

    try:
        tabs_data = read_tabs()
        rows_read = sum(len(v) for v in tabs_data.values())

        purchases, parse_errors = parse_all_tabs(tabs_data)
        errors.extend(parse_errors)

        for purchase in purchases:
            try:
                upsert(purchase)
                rows_upserted += 1
            except Exception as exc:  # noqa: BLE001
                errors.append({
                    "phase": "upsert",
                    "order_id": purchase.get("order_id"),
                    "error": str(exc),
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
        "rows_matched": rows_upserted,    # manual rows have no participant; treat upserted as the count
        "rows_unmatched": 0,
        "errors": errors if errors else None,
        "success": success,
    }
    try:
        write_log(log)
    except Exception:  # noqa: BLE001
        pass

    return {
        "started_at":      started_at,
        "finished_at":     finished_at,
        "rows_read":       rows_read,
        "rows_upserted":   rows_upserted,
        "errors":          errors,
        "success":         success,
        "source":          "manual_sales",
    }
