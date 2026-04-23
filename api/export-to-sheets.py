"""
GET /api/export-to-sheets  — Vercel cron (every 10 min).

Pushes the current Supabase state to a live Google Sheet that clients can view.
This is the REVERSE of sync_payments.py: Supabase → Sheet (not Sheet → Supabase).

The sheet has three tabs, all truncate-and-rewrite each run so corrections /
late name backfills propagate cleanly:

  1. Payments      — one row per purchase (PAID first, then the rest)
  2. Participants  — one row per form-fill (latest first)
  3. Summary       — KPIs computed in Python so clients never see a broken formula

Auth:
  - Same Bearer-token pattern as /api/sync-payments. Vercel cron hits this with
    `Authorization: Bearer $CRON_SECRET`. Browser hits are rejected 401.

Required env vars:
  - SUPABASE_URL, SUPABASE_SERVICE_KEY
  - GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON  (reused from sync-payments)
  - BU_EXPORT_SHEET_ID                  (the Supabase-bridge sheet)
  - CRON_SECRET

The sheet must be shared with the service account's client_email as Editor.
"""

from http.server import BaseHTTPRequestHandler
import datetime
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request


PURCHASES_TABLE = "new_business_normal_purchases"
PARTICIPANTS_TABLE = "new_business_normal_participants"

# Tier code -> human label. Keep aligned with create-invoice.py TIERS.
_TIER_LABELS = {
    "early_bird":      "Early Bird (In-Person)",
    "regular":         "Regular (In-Person)",
    "vip":             "VIP",
    "early_bird_zoom": "Early Bird (Zoom)",
    "regular_zoom":    "Regular (Zoom)",
}

# Tab names + headers. Headers are the first row on each tab.
PAYMENTS_TAB = "Payments"
PAYMENTS_HEADER = [
    "order_id", "paid_at", "created_at", "full_name", "email", "mobile",
    "ticket_tier", "tier_label", "quantity", "amount", "total",
    "payment_status", "payment_provider", "payment_channel",
    "utm_source", "utm_medium", "utm_campaign", "utm_content",
    "session_id", "match_method", "xendit_invoice_id",
]

PARTICIPANTS_TAB = "Participants"
PARTICIPANTS_HEADER = [
    "created_at", "full_name", "email", "mobile_number",
    "describes_you", "business_type", "referred_by",
    "utm_source", "utm_medium", "utm_campaign", "utm_content",
    "session_id",
]

SUMMARY_TAB = "Summary"


# ---------------------------------------------------------------------------
# Supabase (stdlib)
# ---------------------------------------------------------------------------

def _supabase_env():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    return url.rstrip("/"), key


def _supabase_get(path):
    url, key = _supabase_env()
    req = urllib.request.Request(f"{url}/rest/v1/{path.lstrip('/')}")
    req.add_header("apikey", key)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        raise RuntimeError(
            f"Supabase GET {path.split('?')[0]} failed: "
            f"{exc.code} {exc.reason} - {body[:500]}"
        ) from exc


def fetch_purchases():
    # PAID first, then everything else — sorted newest-first within each group
    # via payment_status.desc (P before E before null alphabetically we'd get
    # PENDING first, so do two queries to guarantee PAID is at the top).
    paid = _supabase_get(
        f"{PURCHASES_TABLE}?select=*&payment_status=eq.PAID&order=paid_at.desc.nullslast"
    )
    other = _supabase_get(
        f"{PURCHASES_TABLE}?select=*&payment_status=neq.PAID&order=created_at.desc"
    )
    return paid + other


def fetch_participants():
    return _supabase_get(
        f"{PARTICIPANTS_TABLE}?select=*&order=created_at.desc&limit=2000"
    )


# ---------------------------------------------------------------------------
# Row projection (Supabase row -> sheet row)
# ---------------------------------------------------------------------------

def _s(v):
    """Sheets API: None/False strings cause empty cells; coerce everything to a
    display-friendly string. Timestamps stay as ISO (sheet can parse them)."""
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return v  # let Sheets render as number
    return str(v)


def _tier_label(key):
    return _TIER_LABELS.get((key or "").lower(), key or "")


def project_payment(row):
    return [
        _s(row.get("order_id")),
        _s(row.get("paid_at")),
        _s(row.get("created_at")),
        _s(row.get("full_name")),
        _s(row.get("email")),
        _s(row.get("mobile")),
        _s(row.get("ticket_tier")),
        _tier_label(row.get("ticket_tier")),
        _s(row.get("quantity")),
        _s(row.get("amount")),
        _s(row.get("total")),
        _s(row.get("payment_status")),
        _s(row.get("payment_provider")),
        _s(row.get("payment_channel")),
        _s(row.get("utm_source")),
        _s(row.get("utm_medium")),
        _s(row.get("utm_campaign")),
        _s(row.get("utm_content")),
        _s(row.get("session_id")),
        _s(row.get("match_method")),
        _s(row.get("xendit_invoice_id")),
    ]


def project_participant(row):
    return [
        _s(row.get("created_at")),
        _s(row.get("full_name")),
        _s(row.get("email")),
        _s(row.get("mobile_number")),
        _s(row.get("describes_you")),
        _s(row.get("business_type")),
        _s(row.get("referred_by")),
        _s(row.get("utm_source")),
        _s(row.get("utm_medium")),
        _s(row.get("utm_campaign")),
        _s(row.get("utm_content")),
        _s(row.get("session_id")),
    ]


def build_summary(purchases, participants):
    """Plain values so the sheet displays the same numbers as /admin without
    depending on spreadsheet formulas."""
    paid = [p for p in purchases if (p.get("payment_status") or "").upper() == "PAID"]
    pending = [p for p in purchases if (p.get("payment_status") or "").upper() == "PENDING"]

    tickets = sum(int(p.get("quantity") or 1) for p in paid)
    revenue = sum(float(p.get("total") or 0) for p in paid)

    # By tier
    by_tier = {}
    for p in paid:
        t = (p.get("ticket_tier") or "unknown").lower()
        rec = by_tier.setdefault(t, {"tickets": 0, "revenue": 0.0})
        rec["tickets"] += int(p.get("quantity") or 1)
        rec["revenue"] += float(p.get("total") or 0)

    # By UTM source
    by_utm = {}
    for p in paid:
        s = (p.get("utm_source") or "direct").lower()
        rec = by_utm.setdefault(s, {"tickets": 0, "revenue": 0.0})
        rec["tickets"] += int(p.get("quantity") or 1)
        rec["revenue"] += float(p.get("total") or 0)

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    rows = [
        ["Business Unlocked — Live Payments (live from Supabase)"],
        [f"Last updated: {now}"],
        [f"Refreshes every 10 minutes. Edits here are overwritten — treat as read-only."],
        [],
        ["Totals"],
        ["Tickets sold (PAID)", tickets],
        ["Revenue (PHP)", round(revenue, 2)],
        ["Pending orders", len(pending)],
        ["Participants (form fills)", len(participants)],
        [],
        ["By tier (PAID only)"],
        ["Tier", "Tickets", "Revenue (PHP)"],
    ]
    for tier in sorted(by_tier.keys()):
        rec = by_tier[tier]
        rows.append([_tier_label(tier) or tier, rec["tickets"], round(rec["revenue"], 2)])

    rows.extend([
        [],
        ["By UTM source (PAID only)"],
        ["UTM source", "Tickets", "Revenue (PHP)"],
    ])
    for src in sorted(by_utm.keys()):
        rec = by_utm[src]
        rows.append([src, rec["tickets"], round(rec["revenue"], 2)])

    return rows


# ---------------------------------------------------------------------------
# Sheets (google-api-python-client, same deps as sync_payments.py)
# ---------------------------------------------------------------------------

def _sheets_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    raw_json = os.environ.get("GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON")
    if not raw_json:
        raise EnvironmentError("Missing GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON")

    creds = service_account.Credentials.from_service_account_info(
        json.loads(raw_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _ensure_tabs(svc, sheet_id, required):
    """Make sure every required tab exists. No-op if they do."""
    meta = svc.spreadsheets().get(
        spreadsheetId=sheet_id,
        fields="sheets.properties(sheetId,title)",
    ).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
    missing = [t for t in required if t not in existing]
    if not missing:
        return
    svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": t, "gridProperties": {"frozenRowCount": 1}}}} for t in missing]},
    ).execute()


def _overwrite_tab(svc, sheet_id, tab, header, data_rows):
    """Truncate-and-rewrite: clear the full tab, then write header + rows.
    Using clear() (not values.clear) removes stray rows below the new data."""
    svc.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range=f"{tab}!A:ZZ",
        body={},
    ).execute()
    values = [header] + data_rows
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{tab}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()


def _overwrite_tab_raw(svc, sheet_id, tab, rows):
    """Same idea as _overwrite_tab but for the Summary tab where the shape is
    irregular (no single header row)."""
    svc.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range=f"{tab}!A:ZZ",
        body={},
    ).execute()
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{tab}!A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_export():
    sheet_id = os.environ.get("BU_EXPORT_SHEET_ID")
    if not sheet_id:
        raise EnvironmentError("Missing BU_EXPORT_SHEET_ID")

    purchases = fetch_purchases()
    participants = fetch_participants()

    svc = _sheets_service()
    _ensure_tabs(svc, sheet_id, [PAYMENTS_TAB, PARTICIPANTS_TAB, SUMMARY_TAB])

    _overwrite_tab(
        svc, sheet_id, PAYMENTS_TAB, PAYMENTS_HEADER,
        [project_payment(p) for p in purchases],
    )
    _overwrite_tab(
        svc, sheet_id, PARTICIPANTS_TAB, PARTICIPANTS_HEADER,
        [project_participant(p) for p in participants],
    )
    _overwrite_tab_raw(
        svc, sheet_id, SUMMARY_TAB,
        build_summary(purchases, participants),
    )

    return {
        "ok": True,
        "purchases": len(purchases),
        "participants": len(participants),
        "sheet_id": sheet_id,
    }


# ---------------------------------------------------------------------------
# HTTP handler — mirrors sync-payments.py auth
# ---------------------------------------------------------------------------

def _verify_bearer(received):
    expected = os.environ.get("CRON_SECRET", "")
    if not expected or not received:
        return False
    prefix = "Bearer "
    if not received.startswith(prefix):
        return False
    return hmac.compare_digest(expected, received[len(prefix):])


def _send_json(h, status, payload):
    body = json.dumps(payload).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if not _verify_bearer(self.headers.get("Authorization", "")):
            _send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            result = run_export()
        except EnvironmentError as exc:
            print(f"[export-to-sheets] env error: {exc}", flush=True)
            _send_json(self, 500, {"error": "Server misconfiguration", "detail": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[export-to-sheets] error: {type(exc).__name__}: {exc}", flush=True)
            _send_json(self, 500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            return

        print(f"[export-to-sheets] {json.dumps(result)}", flush=True)
        _send_json(self, 200, result)

    def do_POST(self):
        # Vercel cron sends GET, but accept POST too for manual triggers from curl -X POST
        self.do_GET()

    def log_message(self, format, *args):
        pass
