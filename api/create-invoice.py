"""
POST /api/create-invoice

Creates a Xendit invoice for a Business Unlocked ticket and writes a PENDING
row to new_business_normal_purchases so abandoned-cart + reporting can see
the intent the moment the checkout form is submitted (not only after payment).

On success, returns { invoice_url, order_id }. The frontend redirects the
user's browser to invoice_url, where Xendit hosts the final payment UI
(GCash OTP, card tokenization, etc.). When Xendit marks the invoice PAID,
our /api/xendit-webhook endpoint upgrades the same row to PAID.

Required env vars (set in Vercel):
  - XENDIT_SECRET_KEY        xnd_production_... or xnd_development_...
  - SUPABASE_URL
  - SUPABASE_SERVICE_KEY
Optional:
  - PUBLIC_BASE_URL          defaults to https://www.exponential-university.live
"""

from http.server import BaseHTTPRequestHandler
import base64
import datetime
import json
import os
import random
import re
import string
import urllib.error
import urllib.request


EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# Tier config (amount in PHP, label shown on the Xendit invoice page, short
# code used in the human-readable order_id).
TIERS = {
    "early_bird": {"amount": 1999, "label": "Early Bird",         "code": "EB"},
    "regular":    {"amount": 2500, "label": "Regular",            "code": "REG"},
    "vip":        {"amount": 5000, "label": "VIP",                "code": "VIP"},
}

EVENT_NAME = "Business Unlocked Summit"
INVOICE_DURATION_SECONDS = 60 * 60  # 1 hour before the Xendit invoice expires

# Xendit accepts a payment_methods array on Invoice API. We only pass it when
# the user actively picked one; otherwise we let Xendit show all channels on
# its page. Keep this list in sync with the radio tiles on checkout.html.
ALLOWED_PAYMENT_METHODS = {
    "CREDIT_CARD",
    "GCASH",
    "PAYMAYA",
    "GRABPAY",
    "QRIS",
    "BPI",           # Direct Debit
    "BDO_EPAY",      # Direct Debit
    "BILLEASE",      # PayLater
    "KREDIVO",       # PayLater
    "CEBUANA",       # Retail outlet
    "7ELEVEN",       # Retail outlet
}

# UTM fields we'll accept, pass through to the redirect URL, and stash on
# the purchase row. Matches what sync_payments.py writes.
UTM_FIELDS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_cors_headers(h):
    origin = h.headers.get("Origin", "")
    h.send_header("Access-Control-Allow-Origin", origin or "*")
    h.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "Content-Type")
    h.send_header("Vary", "Origin")


def _send_json(h, status, payload):
    body = json.dumps(payload).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    _add_cors_headers(h)
    h.end_headers()
    h.wfile.write(body)


def _str(val, limit=500):
    if val is None:
        return ""
    return str(val).strip()[:limit]


def _normalize_email(raw):
    return _str(raw).lower()


def _normalize_mobile(raw):
    """Return digits-only, preserve leading + if present. Xendit is permissive
    about format but a digits-only string avoids provider-side reformatting."""
    if not raw:
        return ""
    digits = re.sub(r"[^\d+]", "", str(raw))
    return digits[:20]


def _split_name(full_name):
    parts = (full_name or "").strip().split(None, 1)
    first = parts[0] if parts else "Guest"
    last = parts[1] if len(parts) > 1 else ""
    return first, last


def _generate_order_id(tier):
    """
    Human-readable, unique, URL-safe order id used as the Xendit external_id.
    Format: BU-<CODE>-<YYYYMMDD>-<8 random chars>
    The 8-char suffix is alphanumeric uppercase (36^8 ≈ 2.8T) so duplicates
    are effectively impossible even across bursts of submissions.
    """
    code = TIERS[tier]["code"]
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(random.choice(alphabet) for _ in range(8))
    return f"BU-{code}-{today}-{suffix}"


def _iso_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _public_base_url():
    return os.environ.get("PUBLIC_BASE_URL", "https://www.exponential-university.live").rstrip("/")


# ---------------------------------------------------------------------------
# Xendit client (stdlib only, matches sync_payments.py pattern)
# ---------------------------------------------------------------------------

def _xendit_auth_header():
    key = os.environ.get("XENDIT_SECRET_KEY")
    if not key:
        raise EnvironmentError("Missing XENDIT_SECRET_KEY")
    # Xendit uses HTTP Basic with secret key as username, empty password
    token = base64.b64encode(f"{key}:".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _xendit_create_invoice(payload):
    """POST https://api.xendit.co/v2/invoices. Returns the parsed JSON.
    Raises RuntimeError with the API's error snippet on failure."""
    req = urllib.request.Request(
        "https://api.xendit.co/v2/invoices",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    req.add_header("Authorization", _xendit_auth_header())
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        snippet = body_text[:500]
        raise RuntimeError(
            f"Xendit POST /v2/invoices failed: {exc.code} {exc.reason} - {snippet}"
        ) from exc


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

PURCHASES_TABLE = "new_business_normal_purchases"


def _supabase_env():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    return url.rstrip("/"), key


def _supabase_post(table, body, extra_headers=None):
    url, key = _supabase_env()
    req = urllib.request.Request(
        f"{url}/rest/v1/{table}",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
    )
    req.add_header("apikey", key)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    if extra_headers:
        for k, v in extra_headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as exc:
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        raise RuntimeError(
            f"Supabase POST {table} failed: {exc.code} {exc.reason} - {body_text[:500]}"
        ) from exc


def _write_pending_purchase(row):
    """Insert or merge an intent row keyed by order_id.

    ON CONFLICT (order_id) is handled by the partial unique index added in the
    2026-04-14 migration. We use merge-duplicates so that if a user hits the
    endpoint twice with the same order_id (shouldn't happen with random suffix,
    but defensive), we don't 409.
    """
    _supabase_post(
        f"{PURCHASES_TABLE}?on_conflict=order_id",
        body=row,
        extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
    )


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

def _build_success_redirect(base_url, session_id, order_id, utm):
    """Preserve session_id + UTM so /thank-you can still log the purchase
    click-side even if the webhook is slow. Frontend is the source of truth
    for redirect target; the webhook is the source of truth for the PAID row."""
    from urllib.parse import urlencode
    params = {"session_id": session_id or "", "order_id": order_id}
    for k in UTM_FIELDS:
        if utm.get(k):
            params[k] = utm[k]
    return f"{base_url}/thank-you?" + urlencode({k: v for k, v in params.items() if v})


def _build_failure_redirect(base_url, tier):
    return f"{base_url}/checkout?tier={tier}&failed=1"


def _parse_request(raw_body):
    """Return (payload_dict, error_message). On error, payload is None."""
    try:
        data = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None, "Request body must be valid JSON."

    if not isinstance(data, dict):
        return None, "Payload must be a JSON object."

    tier = _str(data.get("tier"), 40).lower().replace("-", "_")
    if tier not in TIERS:
        return None, f"Invalid tier. Must be one of: {', '.join(TIERS.keys())}."

    full_name = _str(data.get("full_name"), 200)
    email = _normalize_email(data.get("email"))
    mobile = _normalize_mobile(data.get("mobile_number") or data.get("mobile"))
    if not full_name:
        return None, "Missing required field: full_name."
    if not email or not EMAIL_PATTERN.match(email):
        return None, "Invalid email address."
    if not mobile:
        return None, "Missing required field: mobile_number."

    session_id = _str(data.get("session_id"), 64)

    utm = {k: _str(data.get(k), 120).lower() or None for k in UTM_FIELDS}

    preferred_method_raw = _str(data.get("preferred_method"), 40).upper()
    preferred_method = preferred_method_raw if preferred_method_raw in ALLOWED_PAYMENT_METHODS else None

    return {
        "tier": tier,
        "full_name": full_name,
        "email": email,
        "mobile": mobile,
        "session_id": session_id,
        "utm": utm,
        "preferred_method": preferred_method,
    }, None


def _create_invoice(parsed):
    """Pure-ish orchestrator: takes parsed dict, talks to Xendit + Supabase,
    returns {invoice_url, order_id}. Raises on hard failure."""
    tier = parsed["tier"]
    tier_cfg = TIERS[tier]
    amount = tier_cfg["amount"]

    order_id = _generate_order_id(tier)
    base_url = _public_base_url()
    success_url = _build_success_redirect(base_url, parsed["session_id"], order_id, parsed["utm"])
    failure_url = _build_failure_redirect(base_url, tier)

    first, last = _split_name(parsed["full_name"])

    xendit_payload = {
        "external_id": order_id,
        "amount": amount,
        "currency": "PHP",
        "description": f"{EVENT_NAME} — {tier_cfg['label']} Ticket (May 9, 2026)",
        "payer_email": parsed["email"],
        "customer": {
            "given_names": first,
            "surname": last,
            "email": parsed["email"],
            "mobile_number": parsed["mobile"],
        },
        "customer_notification_preference": {
            "invoice_paid": ["email"],
        },
        "success_redirect_url": success_url,
        "failure_redirect_url": failure_url,
        "invoice_duration": INVOICE_DURATION_SECONDS,
        "items": [
            {
                "name": f"{EVENT_NAME} — {tier_cfg['label']}",
                "quantity": 1,
                "price": amount,
                "category": "Event Ticket",
            }
        ],
        "metadata": {
            "tier": tier,
            "session_id": parsed["session_id"],
            **{k: v for k, v in parsed["utm"].items() if v},
        },
    }
    # Note: we intentionally DO NOT pass `payment_methods` on v1. Xendit's
    # Invoice API accepts it but the exact enum (GCASH vs EWALLET_GCASH vs
    # PH_EWALLET_GCASH) has varied across Xendit product iterations, and a
    # bad value fails the entire invoice creation. The Xendit-hosted invoice
    # page already shows all available channels for our account, so skipping
    # the filter is the safest way to guarantee the checkout works end-to-end.
    # The user's preferred_method is still persisted on the purchase row for
    # analytics / UX refinement later.
    invoice = _xendit_create_invoice(xendit_payload)

    invoice_url = invoice.get("invoice_url")
    invoice_id = invoice.get("id")
    if not invoice_url:
        raise RuntimeError(f"Xendit returned no invoice_url: {str(invoice)[:300]}")

    # Write the PENDING row. Schema maps to new_business_normal_purchases —
    # see 2026-04-14 migration + 2026-04-22 migration for the Xendit columns.
    purchase_row = {
        "order_id":         order_id,
        "email":            parsed["email"],
        "mobile":           parsed["mobile"],
        "full_name":        parsed["full_name"],
        "ticket_tier":      tier,
        "amount":           amount,
        "quantity":         1,
        "total":            amount,
        "payment_provider": "xendit",
        "payment_status":   "PENDING",
        "paid_at":          None,
        "participant_id":   None,
        "match_method":     None,
        "session_id":       parsed["session_id"] or None,
        "xendit_invoice_id": invoice_id,
        "invoice_url":      invoice_url,
        "preferred_method": parsed["preferred_method"],
        "utm_source":       parsed["utm"].get("utm_source"),
        "utm_medium":       parsed["utm"].get("utm_medium"),
        "utm_campaign":     parsed["utm"].get("utm_campaign"),
        "utm_content":      parsed["utm"].get("utm_content"),
        "raw_row":          {
            "source": "create-invoice",
            "xendit_invoice_id": invoice_id,
            "xendit_status": invoice.get("status"),
            "created_at": _iso_now(),
        },
    }
    _write_pending_purchase(purchase_row)

    return {"invoice_url": invoice_url, "order_id": order_id}


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(204)
        _add_cors_headers(self)
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 20_000:
            _send_json(self, 400, {"error": "Invalid request body."})
            return

        raw_body = self.rfile.read(length)
        parsed, err = _parse_request(raw_body)
        if err:
            _send_json(self, 400, {"error": err})
            return

        try:
            result = _create_invoice(parsed)
        except EnvironmentError as exc:
            # Missing env var — log server-side, return generic to client
            print(f"[create-invoice] env error: {exc}", flush=True)
            _send_json(self, 500, {"error": "Server is not configured for payments."})
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[create-invoice] error: {type(exc).__name__}: {exc}", flush=True)
            _send_json(self, 502, {"error": "Could not create invoice. Please try again."})
            return

        _send_json(self, 200, result)

    def log_message(self, format, *args):
        pass
