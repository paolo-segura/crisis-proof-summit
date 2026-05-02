"""
POST /api/create-invoice

Creates a Xendit invoice for a Business Unlocked ticket and writes a PENDING
row to new_business_normal_purchases so abandoned-cart + reporting can see
the intent from the moment the inline checkout form is submitted (not just
after payment clears).

On success returns { invoice_url, order_id }. The frontend redirects the
browser to invoice_url, where Xendit hosts the final OTP / 3DS / QR step.
When Xendit marks the invoice PAID, /api/xendit-webhook flips the same row.

Required env vars (set in Vercel):
  - XENDIT_SECRET_KEY
  - SUPABASE_URL
  - SUPABASE_SERVICE_KEY
Optional:
  - PUBLIC_BASE_URL   defaults to https://www.exponential-university.live
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

# Tier config (amount in PHP per ticket, label shown on Xendit's hosted page,
# short code used in the human-readable order_id).
#
# Zoom tiers mirror the in-person prices (same event, different delivery).
# Separate SKUs so Supabase + admin dashboards can segment in-person vs
# online attendance without an extra `access_mode` column. VIP stays
# in-person only per 2026-04-23 decision.
TIERS = {
    "early_bird":      {"amount": 1999, "label": "Early Bird (In-Person)", "code": "EB"},
    "regular":         {"amount": 2500, "label": "Regular (In-Person)",    "code": "REG"},
    "vip":             {"amount": 5000, "label": "VIP",                    "code": "VIP"},
    "early_bird_zoom": {"amount": 1999, "label": "Early Bird (Zoom)",      "code": "EB_ZOOM"},
    "regular_zoom":    {"amount": 2500, "label": "Regular (Zoom)",         "code": "REG_ZOOM"},
}

EVENT_NAME = "Business Unlocked Summit"
INVOICE_DURATION_SECONDS = 60 * 60  # 1 hour before the Xendit invoice expires

# Coupon codes — single source of truth, server-side only.
#
# Each coupon locks a specific tier and a flat new price (PHP). The buyer's
# chosen access_mode (in_person / zoom) is preserved if it matches the coupon's
# base tier (Early Bird and Regular have both modes; VIP is in-person only).
#
# Multi-use, no expiry, no usage cap. To add/remove codes, edit this dict and
# redeploy. Codes are case-insensitive (we uppercase before lookup).
#
# Format: code -> { base_tier, amount, label }
#   base_tier: which tier to lock the buyer into (early_bird | regular | vip)
#   amount:    flat new per-ticket price in PHP
#   label:     human-readable name shown in logs / admin (not on Xendit page)
#
# Hardcoded HOT FALLBACK — always available even if Supabase is unreachable.
# The live source of truth is the bu_coupons Supabase table (managed via the
# /admin/coupons UI). _lookup_coupon below tries the table first, falls back
# here on any error or empty result. KATH must always live here so the active
# Kath promo can never break.
COUPONS_FALLBACK = {
    "KATH":    {"base_tier": "regular",    "amount": 1999, "label": "Kath x BU"},
}

# Cache of the bu_coupons table. TTL'd so a Supabase outage doesn't make
# every checkout wait 8 seconds for the timeout — after the first failed
# fetch we serve fallback for _DB_COUPONS_TTL seconds before retrying.
# A cache hit (success path) lives the same 5 min before refreshing, so
# admin-added codes go live within 5 minutes worst-case.
import time as _time

_DB_COUPONS_CACHE = None       # dict[str, dict] | None  (None = not yet populated)
_DB_COUPONS_FETCHED_AT = 0.0   # epoch seconds — set on every fetch attempt, success OR failure
_DB_COUPONS_TTL = 300          # 5 minutes


def _fetch_coupons_from_db():
    """Read active coupons from bu_coupons. Returns dict keyed by uppercase code,
    or None on any failure (caller falls back to COUPONS_FALLBACK)."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return None
    try:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/rest/v1/bu_coupons"
            f"?select=code,base_tier,amount,label&active=eq.true",
            method="GET",
        )
        req.add_header("apikey", key)
        req.add_header("Authorization", f"Bearer {key}")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=8) as resp:
            rows = json.loads(resp.read().decode("utf-8") or "[]")
    except Exception as exc:  # noqa: BLE001 — never let a coupon-table outage break checkout
        print(f"[create-invoice] coupon DB lookup failed, using fallback: {type(exc).__name__}: {exc}", flush=True)
        return None
    out = {}
    for r in rows or []:
        code = str(r.get("code", "")).upper().strip()
        try:
            amount = float(r.get("amount"))
        except (TypeError, ValueError):
            continue
        base = str(r.get("base_tier", "")).lower()
        label = str(r.get("label", "")).strip() or code
        if not code or base not in ("early_bird", "regular", "vip") or amount <= 0:
            continue
        out[code] = {"base_tier": base, "amount": amount, "label": label}
    return out


def _lookup_coupon(code):
    """Look up a coupon by code (case-insensitive). DB-first with hardcoded
    fallback. Returns None if not found in either.

    DB query is cached for _DB_COUPONS_TTL seconds. On a DB failure we still
    set _DB_COUPONS_FETCHED_AT so subsequent requests serve fallback fast
    instead of retrying an 8-second timeout per checkout under outage.

    Disabling a code via the admin UI sets `active=false`; the fetch query
    filters `active=eq.true` so disabled rows never enter the cache. The
    hardcoded COUPONS_FALLBACK is a last-resort safety net only — to truly
    kill a code that lives there (e.g. KATH), remove it from the dict in
    code AND deactivate the DB row."""
    global _DB_COUPONS_CACHE, _DB_COUPONS_FETCHED_AT
    norm = (code or "").upper().strip()
    if not norm:
        return None
    now = _time.time()
    # Refresh decision based on TTL alone — NOT on whether the cache is
    # populated. If the first fetch failed (cache stays None), we must NOT
    # retry on every request; we wait the full TTL. _DB_COUPONS_FETCHED_AT
    # starts at 0.0, so the first call always falls through to a fetch.
    if (now - _DB_COUPONS_FETCHED_AT) > _DB_COUPONS_TTL:
        result = _fetch_coupons_from_db()
        # Update the timestamp on every attempt — success OR failure — so a
        # downed Supabase doesn't make every checkout wait 8s for the timeout.
        _DB_COUPONS_FETCHED_AT = now
        if result is not None:
            _DB_COUPONS_CACHE = result
        # If result is None and we already had a populated cache, keep it
        # (better stale than wrong). If we had nothing, cache stays None
        # and we fall through to COUPONS_FALLBACK below.
    if _DB_COUPONS_CACHE is not None and norm in _DB_COUPONS_CACHE:
        return _DB_COUPONS_CACHE[norm]
    return COUPONS_FALLBACK.get(norm)

# Map a coupon's base_tier + the buyer's access_mode to the actual database
# ticket_tier value. Mirrors the derivation in js/inline-checkout.js's
# currentTier(). Returns None when the combo is invalid (e.g. VIP + Zoom).
def _resolve_coupon_tier(base_tier, access_mode):
    if base_tier == "vip":
        return "vip" if access_mode == "in_person" else None
    if base_tier in ("early_bird", "regular"):
        return f"{base_tier}_zoom" if access_mode == "zoom" else base_tier
    return None

MIN_QUANTITY = 1
MAX_QUANTITY = 10

# UTM fields accepted from the frontend. Matches what sync_payments.py writes
# so the dashboard / Brevo pipeline keeps aggregating across both sources
# (the legacy GHL sync + this new native flow).
UTM_FIELDS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")

# If the frontend sends one of these, we store it for analytics but we do NOT
# pass it to Xendit as a `payment_methods` filter. Reason: the Invoice API's
# channel enum has drifted (GCASH vs EWALLET_GCASH vs PH_EWALLET_GCASH across
# different Xendit product versions) and a wrong value fails the entire
# invoice creation. Letting Xendit show all available channels on its hosted
# page is the most reliable v1.
ALLOWED_PAYMENT_METHODS = {
    "CREDIT_CARD", "GCASH", "PAYMAYA", "GRABPAY", "QRPH",
    "BPI", "BDO_EPAY", "BILLEASE", "KREDIVO", "CEBUANA", "7ELEVEN",
}


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
    """Digits-only (+ preserved). Xendit is permissive about format but
    a digits-only string avoids upstream reformatting surprises."""
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
    """Human-readable, unique, URL-safe order id used as the Xendit external_id.
    Format: BU-<CODE>-<YYYYMMDD>-<8 random chars>. 36^8 ~= 2.8T combinations,
    so collision in the same day is effectively impossible."""
    code = TIERS[tier]["code"]
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(random.choice(alphabet) for _ in range(8))
    return f"BU-{code}-{today}-{suffix}"


def _iso_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _public_base_url():
    return os.environ.get(
        "PUBLIC_BASE_URL", "https://www.exponential-university.live"
    ).rstrip("/")


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
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        raise RuntimeError(
            f"Xendit POST /v2/invoices failed: {exc.code} {exc.reason} - {body_text[:500]}"
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
    """Insert or merge an intent row keyed by order_id. ON CONFLICT (order_id)
    is handled by the partial unique index from 2026-04-14 migration. We use
    merge-duplicates so a retried submit won't 409."""
    _supabase_post(
        f"{PURCHASES_TABLE}?on_conflict=order_id",
        body=row,
        extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
    )


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

def _build_success_redirect(base_url, session_id, order_id, tier, quantity, total_amount, utm):
    """Include tier + qty + value so the thank-you page can fire Meta Pixel
    Purchase with accurate amount (for ROAS) without needing a roundtrip to
    Supabase. UTM preserved so attribution flows through the whole funnel."""
    from urllib.parse import urlencode
    params = {
        "session_id": session_id or "",
        "order_id": order_id,
        "tier": tier,
        "quantity": str(quantity),
        "value": str(total_amount),
    }
    for k in UTM_FIELDS:
        if utm.get(k):
            params[k] = utm[k]
    return f"{base_url}/thank-you?" + urlencode({k: v for k, v in params.items() if v})


def _build_failure_redirect(base_url):
    # Back to the pricing section on the event page with a flag the frontend
    # can use to show a "payment not completed" banner.
    return f"{base_url}/the-new-business-normal?checkout=failed#pricing"


def _parse_request(raw_body):
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
    # Xendit requires a non-empty surname; we also want full names on the
    # attendee list. Reject anything that's not at least two whitespace-
    # separated words so the user gets a clear message instead of a 502.
    if len(full_name.split()) < 2:
        return None, "Please enter your complete name (first and last)."
    if not email or not EMAIL_PATTERN.match(email):
        return None, "Invalid email address."
    if not mobile:
        return None, "Missing required field: mobile_number."

    try:
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    if quantity < MIN_QUANTITY:
        return None, f"Quantity must be at least {MIN_QUANTITY}."
    if quantity > MAX_QUANTITY:
        return None, f"For more than {MAX_QUANTITY} tickets, please contact us directly."

    session_id = _str(data.get("session_id"), 64)
    utm = {k: _str(data.get(k), 120).lower() or None for k in UTM_FIELDS}

    preferred_method_raw = _str(data.get("preferred_method") or data.get("method"), 40).upper()
    preferred_method = preferred_method_raw if preferred_method_raw in ALLOWED_PAYMENT_METHODS else None

    # Coupon code — optional. Uppercased + trimmed before lookup. Validation
    # happens here so we can surface a clean 400 to the user without burning
    # a Xendit invoice creation on a bad code.
    coupon_code = _str(data.get("coupon_code"), 40).upper()
    coupon_cfg = None
    final_tier = tier
    if coupon_code:
        coupon_cfg = _lookup_coupon(coupon_code)
        if not coupon_cfg:
            return None, "Invalid coupon code. Please check and try again."
        # Derive access mode from the tier the user picked: tiers ending
        # in _zoom = zoom, otherwise in-person.
        access_mode = "zoom" if tier.endswith("_zoom") else "in_person"
        resolved = _resolve_coupon_tier(coupon_cfg["base_tier"], access_mode)
        if resolved is None:
            # The only invalid combo today is VIP + Zoom (VIP is in-person-only).
            return None, "This coupon is for in-person VIP only. Please switch to In-Person to use it."
        final_tier = resolved

    return {
        "tier": final_tier,
        "quantity": quantity,
        "full_name": full_name,
        "email": email,
        "mobile": mobile,
        "session_id": session_id,
        "utm": utm,
        "preferred_method": preferred_method,
        "coupon_code": coupon_code or None,
        "coupon_cfg": coupon_cfg,  # None when no coupon applied
    }, None


def _create_invoice(parsed):
    tier = parsed["tier"]
    tier_cfg = TIERS[tier]
    quantity = parsed["quantity"]
    # Coupon, if any, replaces the per-ticket price. Tier was already locked
    # in _parse_request (e.g. KATHVIP -> 'vip', KATHEB + zoom mode -> 'early_bird_zoom').
    coupon_cfg = parsed.get("coupon_cfg")
    unit_price = coupon_cfg["amount"] if coupon_cfg else tier_cfg["amount"]
    total_amount = unit_price * quantity

    order_id = _generate_order_id(tier)
    base_url = _public_base_url()
    success_url = _build_success_redirect(
        base_url, parsed["session_id"], order_id, tier, quantity, total_amount, parsed["utm"]
    )
    failure_url = _build_failure_redirect(base_url)

    first, last = _split_name(parsed["full_name"])

    qty_suffix = f" × {quantity}" if quantity > 1 else ""
    coupon_suffix = f" — {coupon_cfg['label']}" if coupon_cfg else ""
    xendit_payload = {
        "external_id": order_id,
        # Xendit's `amount` must equal sum(items[].price * items[].quantity) —
        # Xendit displays items but does NOT recalculate amount from them.
        "amount": total_amount,
        "currency": "PHP",
        "description": f"{EVENT_NAME} — {tier_cfg['label']} Ticket{qty_suffix} (May 9, 2026){coupon_suffix}",
        "payer_email": parsed["email"],
        "customer": {
            "given_names": first,
            "surname": last,  # _parse_request guarantees this is non-empty
            "email": parsed["email"],
            "mobile_number": parsed["mobile"],
        },
        "customer_notification_preference": {"invoice_paid": ["email"]},
        "success_redirect_url": success_url,
        "failure_redirect_url": failure_url,
        "invoice_duration": INVOICE_DURATION_SECONDS,
        "items": [
            {
                "name": f"{EVENT_NAME} — {tier_cfg['label']}",
                "quantity": quantity,
                "price": unit_price,
                "category": "Event Ticket",
            }
        ],
        "metadata": {
            "tier": tier,
            "quantity": quantity,
            "session_id": parsed["session_id"],
            **{k: v for k, v in parsed["utm"].items() if v},
        },
    }
    # Intentionally NOT passing `payment_methods`. See module docstring.

    invoice = _xendit_create_invoice(xendit_payload)
    invoice_url = invoice.get("invoice_url")
    invoice_id = invoice.get("id")
    if not invoice_url:
        raise RuntimeError(f"Xendit returned no invoice_url: {str(invoice)[:300]}")

    purchase_row = {
        "order_id":         order_id,
        "email":            parsed["email"],
        "mobile":           parsed["mobile"],
        "full_name":        parsed["full_name"],
        "ticket_tier":      tier,
        "amount":           unit_price,   # per-ticket, matches sync_payments convention
        "quantity":         quantity,
        "total":            total_amount,
        "payment_provider": "xendit",
        "payment_status":   "PENDING",
        "paid_at":          None,
        "participant_id":   None,
        "match_method":     None,
        "session_id":       parsed["session_id"] or None,
        "xendit_invoice_id": invoice_id,
        "invoice_url":      invoice_url,
        "preferred_method": parsed["preferred_method"],
        "coupon_code":      parsed.get("coupon_code"),
        "utm_source":       parsed["utm"].get("utm_source"),
        "utm_medium":       parsed["utm"].get("utm_medium"),
        "utm_campaign":     parsed["utm"].get("utm_campaign"),
        "utm_content":      parsed["utm"].get("utm_content"),
        "raw_row": {
            "source": "create-invoice",
            "xendit_invoice_id": invoice_id,
            "xendit_status": invoice.get("status"),
            "coupon_label": coupon_cfg["label"] if coupon_cfg else None,
            "list_price":   tier_cfg["amount"],  # what they would have paid without the coupon
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
