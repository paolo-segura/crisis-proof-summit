"""
POST /api/xendit-webhook

Xendit -> us. On every invoice state change, update the matching purchase row.

Verification: Xendit sends the configured "Callback Verification Token" in
the `x-callback-token` header. Requests with a missing or wrong token are
rejected 401. This is the only auth protecting the endpoint.

Handled events:
  - invoice.paid / settled  -> payment_status = 'PAID', paid_at set
  - invoice.expired         -> payment_status = 'EXPIRED'

Any other event is acknowledged with 200 and ignored so Xendit stops
retrying.

Required env vars:
  - XENDIT_CALLBACK_TOKEN
  - SUPABASE_URL
  - SUPABASE_SERVICE_KEY

Optional (for post-purchase confirmation email):
  - BREVO_API_KEY           — if unset, email send is skipped (logged)
  - BREVO_SENDER_EMAIL      — defaults to hello@exponential-university.live
  - BREVO_SENDER_NAME       — defaults to Business Unlocked
  - BU_ZOOM_JOIN_URL        — Zoom join URL for Zoom ticket holders; if unset,
                              email falls back to a "link coming 24h before" note
"""

from http.server import BaseHTTPRequestHandler
import hmac
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request


PURCHASES_TABLE = "new_business_normal_purchases"
PARTICIPANTS_TABLE = "new_business_normal_participants"

# ---------------------------------------------------------------------------
# Post-purchase email constants
# ---------------------------------------------------------------------------

_TEMPLATE_DIR = pathlib.Path(__file__).resolve().parent.parent / "emails"

# Tier codes that indicate a Zoom (online-only) purchase.
# Using explicit set — do NOT use substring matching.
_ZOOM_TIER_CODES = {"EB_ZOOM", "REG_ZOOM"}

# Mapping from tier key -> (label, code) so we can resolve from either form.
# Kept in sync with create-invoice.py TIERS dict.
_TIER_MAP = {
    "early_bird":      ("Early Bird (In-Person)", "EB"),
    "regular":         ("Regular (In-Person)",    "REG"),
    "vip":             ("VIP",                    "VIP"),
    "early_bird_zoom": ("Early Bird (Zoom)",       "EB_ZOOM"),
    "regular_zoom":    ("Regular (Zoom)",          "REG_ZOOM"),
}

_DEFAULT_SENDER_EMAIL = "hello@exponential-university.live"
_DEFAULT_SENDER_NAME  = "Business Unlocked"


# ---------------------------------------------------------------------------
# Auth -- constant-time compare so timing doesn't leak the token
# ---------------------------------------------------------------------------

def _verify_callback_token(received):
    expected = os.environ.get("XENDIT_CALLBACK_TOKEN", "")
    if not expected or not received:
        return False
    return hmac.compare_digest(expected, received)


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

def _supabase_env():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    return url.rstrip("/"), key


def _supabase_request(method, path, body=None, extra_headers=None):
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
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as exc:
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        raise RuntimeError(
            f"Supabase {method} {path.split('?')[0]} failed: "
            f"{exc.code} {exc.reason} - {body_text[:500]}"
        ) from exc


def _fetch_purchase_by_order_id(order_id):
    q = urllib.parse.quote(order_id)
    rows = _supabase_request(
        "GET",
        f"{PURCHASES_TABLE}?select=*&order_id=eq.{q}&limit=1",
    )
    return rows[0] if rows else None


def _find_participant(email, mobile, session_id):
    """session_id -> email -> mobile (last 10 digits)."""
    from urllib.parse import quote
    if session_id:
        rows = _supabase_request(
            "GET",
            f"{PARTICIPANTS_TABLE}?select=id,email,mobile_number,session_id,created_at"
            f"&session_id=eq.{quote(session_id)}&limit=1",
        )
        if rows:
            return rows[0]["id"], "session_id"

    if email:
        rows = _supabase_request(
            "GET",
            f"{PARTICIPANTS_TABLE}?select=id,email,mobile_number,session_id,created_at"
            f"&email=eq.{quote(email.lower())}&order=created_at.desc&limit=1",
        )
        if rows:
            return rows[0]["id"], "email"

    if mobile:
        digits = "".join(ch for ch in mobile if ch.isdigit())
        if len(digits) >= 10:
            last10 = digits[-10:]
            rows = _supabase_request(
                "GET",
                f"{PARTICIPANTS_TABLE}?select=id,email,mobile_number,session_id,created_at"
                f"&mobile_number=ilike.*{last10}*&order=created_at.desc&limit=5",
            )
            if rows:
                return rows[0]["id"], "mobile"

    return None, "direct"


def _upsert_purchase(row):
    _supabase_request(
        "POST",
        f"{PURCHASES_TABLE}?on_conflict=order_id",
        body=row,
        extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
    )


# ---------------------------------------------------------------------------
# Post-purchase confirmation email
# ---------------------------------------------------------------------------

def _render_template(template_str, tokens):
    """Minimal {{key}} token replacement — same pattern as register-free.py."""
    result = template_str
    for key, value in tokens.items():
        result = result.replace("{{" + key + "}}", value)
    return result


def _zoom_join_block(zoom_url):
    """Return the HTML fragment for the Join Zoom button, or a fallback note."""
    if zoom_url:
        return (
            '<a href="{url}" style="display:inline-block; padding:12px 24px; '
            'background-color:#F59E0B; color:#0F1B2E; font-size:14px; font-weight:700; '
            'border-radius:999px; text-decoration:none;">Join Zoom →</a>'
        ).format(url=zoom_url)
    else:
        return (
            '<p style="margin:0; font-size:14px; color:#CBD5E1; line-height:1.55;">'
            'Zoom link will be sent 24 hours before the summit. '
            'Keep an eye on your inbox.</p>'
        )


def _send_confirmation_email(email, full_name, tier_key):
    """Fire the appropriate post-purchase email via Brevo.

    Routing:
      - Zoom tiers (EB_ZOOM, REG_ZOOM) -> post-purchase-zoom.html
      - In-person tiers + unknown       -> post-purchase-inperson.html (safe default)

    Returns a dict with ok/skipped/error for logging only — never raises.
    """
    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        print("[xendit-webhook] BREVO_API_KEY not set — skipping confirmation email", flush=True)
        return {"ok": False, "skipped": True, "reason": "BREVO_API_KEY not set"}

    if not email:
        return {"ok": False, "skipped": True, "reason": "no email address"}

    # Resolve tier metadata; unknown tier falls through to in-person (safe default)
    tier_info = _TIER_MAP.get(tier_key)
    if tier_info:
        tier_label, tier_code = tier_info
    else:
        print(f"[xendit-webhook] unknown tier '{tier_key}' — defaulting to in-person email", flush=True)
        tier_label = "Event Ticket"
        tier_code = ""

    is_zoom = tier_code in _ZOOM_TIER_CODES

    # Select and load the right template
    template_name = "post-purchase-zoom.html" if is_zoom else "post-purchase-inperson.html"
    template_path = _TEMPLATE_DIR / template_name
    try:
        template_str = template_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"[xendit-webhook] template load failed ({template_name}): {exc}", flush=True)
        return {"ok": False, "error": f"template load failed: {exc}"}

    first_name = full_name.split()[0].title() if full_name else "there"

    tokens = {
        "name":       first_name,
        "tier_label": tier_label,
    }

    if is_zoom:
        zoom_url = os.environ.get("BU_ZOOM_JOIN_URL", "")
        if not zoom_url:
            print("[xendit-webhook] BU_ZOOM_JOIN_URL not set — using fallback text in Zoom email", flush=True)
        tokens["zoom_join_block"] = _zoom_join_block(zoom_url or "")

    html = _render_template(template_str, tokens)

    sender_email = os.environ.get("BREVO_SENDER_EMAIL", _DEFAULT_SENDER_EMAIL)
    sender_name  = os.environ.get("BREVO_SENDER_NAME",  _DEFAULT_SENDER_NAME)

    subject = "You're In — BUSINESS UNLOCKED · May 9, 2026"

    payload = json.dumps({
        "sender": {"email": sender_email, "name": sender_name},
        "to": [{"email": email, "name": full_name or email}],
        "subject": subject,
        "htmlContent": html,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=payload,
        method="POST",
    )
    req.add_header("api-key", api_key)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(f"[xendit-webhook] confirmation email sent to {email} "
                  f"tier={tier_key} zoom={is_zoom} status={resp.status}", flush=True)
            return {"ok": True, "status": resp.status, "body": body[:200]}
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            err_body = ""
        print(f"[xendit-webhook] Brevo error {exc.code}: {err_body}", flush=True)
        return {"ok": False, "status": exc.code, "error": err_body}
    except Exception as exc:  # noqa: BLE001
        print(f"[xendit-webhook] email send error: {type(exc).__name__}: {exc}", flush=True)
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Event handling
# ---------------------------------------------------------------------------

_HANDLED_STATUSES = {"PAID", "SETTLED", "EXPIRED", "FAILED"}

# All BU invoices created via /api/create-invoice carry this prefix
# (see _generate_order_id in create-invoice.py). Anything else hitting this
# webhook is foreign — most commonly Scale Your Org / GHL funnels that share
# the same Xendit account and fire to the same callback URL.
_BU_ORDER_PREFIX = "BU-"


def _status_to_internal(xendit_status):
    s = (xendit_status or "").upper()
    if s in ("PAID", "SETTLED"):
        return "PAID"
    return s


def _handle_event(body):
    status = (body.get("status") or "").upper()
    external_id = body.get("external_id")

    if not external_id:
        print(f"[xendit-webhook] missing external_id: {str(body)[:300]}", flush=True)
        return 200, {"ok": True, "note": "ignored (no external_id)"}

    if status not in _HANDLED_STATUSES:
        print(f"[xendit-webhook] ignoring status={status} order={external_id}", flush=True)
        return 200, {"ok": True, "note": f"ignored status {status}"}

    internal_status = _status_to_internal(status)

    existing = _fetch_purchase_by_order_id(external_id) or {}

    # Foreign-order guard: if the order_id wasn't created by our
    # /api/create-invoice (no BU- prefix) AND we have no PENDING row for it,
    # this is a different product on the same Xendit account. 200 OK so
    # Xendit stops retrying, but no Supabase write — the row never enters
    # BU's purchases table and our reporting stays clean.
    #
    # We accept TXN-* etc. when `existing` IS populated because that means a
    # legacy GHL row (synced via sync_payments.py before Apr 22) genuinely
    # belongs to BU and a late webhook event for it should still update
    # status/paid_at.
    if not external_id.startswith(_BU_ORDER_PREFIX) and not existing:
        print(
            f"[xendit-webhook] foreign order ignored: order={external_id} "
            f"status={status} amount={body.get('amount')} "
            f"channel={body.get('payment_channel') or body.get('payment_method')}",
            flush=True,
        )
        return 200, {"ok": True, "note": "foreign order ignored", "order_id": external_id}
    email = (body.get("payer_email") or existing.get("email") or "").lower()
    mobile = existing.get("mobile") or ""
    session_id = existing.get("session_id")

    participant_id = existing.get("participant_id")
    match_method = existing.get("match_method")
    if internal_status == "PAID" and not participant_id:
        try:
            participant_id, match_method = _find_participant(email, mobile, session_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[xendit-webhook] matcher error: {type(exc).__name__}: {exc}", flush=True)
            participant_id, match_method = None, "direct"

    paid_at = body.get("paid_at") or body.get("updated") or body.get("created")
    amount = body.get("amount") or existing.get("amount")
    payment_channel = body.get("payment_channel") or body.get("payment_method")

    row = {
        "order_id":         external_id,
        "xendit_invoice_id": body.get("id") or existing.get("xendit_invoice_id"),
        "payment_status":   internal_status,
        "payment_provider": "xendit",
        "payment_channel":  payment_channel,
        "paid_at":          paid_at if internal_status == "PAID" else existing.get("paid_at"),
        "amount":           amount,
        "quantity":         existing.get("quantity") or 1,
        "total":            amount,
        "participant_id":   participant_id,
        "match_method":     match_method,
        "raw_row": {
            "source": "xendit-webhook",
            "status": status,
            "event": body.get("event"),
            "id": body.get("id"),
            "paid_at": paid_at,
            "payment_channel": payment_channel,
        },
    }
    # Preserve fields the webhook doesn't re-send so we don't blank them on upsert
    for k in ("email", "mobile", "full_name", "ticket_tier", "session_id",
              "invoice_url", "preferred_method", "coupon_code",
              "utm_source", "utm_medium", "utm_campaign", "utm_content"):
        if existing.get(k) is not None:
            row[k] = existing[k]
    if not existing and email:
        row["email"] = email

    _upsert_purchase(row)

    print(f"[xendit-webhook] upserted order={external_id} status={internal_status} "
          f"participant_id={participant_id} method={match_method}", flush=True)

    # Send post-purchase confirmation email on PAID. Email errors are logged
    # but never bubble up — Xendit must receive 200 to stop retrying.
    if internal_status == "PAID":
        tier_key = existing.get("ticket_tier") or row.get("ticket_tier", "")
        full_name = existing.get("full_name") or ""
        _send_confirmation_email(email, full_name, tier_key)

    return 200, {"ok": True, "order_id": external_id, "status": internal_status}


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

def _send_json(h, status, payload):
    body = json.dumps(payload).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        token = self.headers.get("x-callback-token") or self.headers.get("X-Callback-Token")
        if not _verify_callback_token(token):
            print("[xendit-webhook] rejected: bad/missing x-callback-token", flush=True)
            _send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 100_000:
            _send_json(self, 400, {"error": "Invalid request body"})
            return

        raw_body = self.rfile.read(length)
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            _send_json(self, 400, {"error": "Invalid JSON"})
            return

        try:
            status, payload = _handle_event(body)
        except EnvironmentError as exc:
            print(f"[xendit-webhook] env error: {exc}", flush=True)
            _send_json(self, 500, {"error": "Server misconfiguration"})
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[xendit-webhook] error: {type(exc).__name__}: {exc}", flush=True)
            # Return 200 so Xendit doesn't retry-hammer during a transient fault.
            # The event is in Vercel logs to re-drive manually if needed.
            _send_json(self, 200, {"ok": False, "note": "deferred"})
            return

        _send_json(self, status, payload)

    def log_message(self, format, *args):
        pass
