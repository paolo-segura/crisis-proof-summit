"""
POST /api/xendit-webhook

Xendit → us. On every invoice state change, update the matching purchase row.

Verification: Xendit sends the configured "Callback Verification Token" in
the `x-callback-token` header. Any request whose token doesn't match our
XENDIT_CALLBACK_TOKEN env var is rejected with 401. This is the only piece
of auth protecting this endpoint, so don't skip it.

We care about these invoice events:
  - invoice.paid     → payment_status = 'PAID',   paid_at set, participant rematch queued
  - invoice.expired  → payment_status = 'EXPIRED'

Any other event is acknowledged with 200 so Xendit stops retrying. We return
200 quickly even on soft errors (e.g. row not found) to avoid Xendit pounding
this endpoint with retries during an outage — the Vercel function logs
capture the detail for us to retry manually.

Required env vars:
  - XENDIT_CALLBACK_TOKEN
  - SUPABASE_URL
  - SUPABASE_SERVICE_KEY
"""

from http.server import BaseHTTPRequestHandler
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request


PURCHASES_TABLE = "new_business_normal_purchases"
PARTICIPANTS_TABLE = "new_business_normal_participants"


# ---------------------------------------------------------------------------
# Auth — constant-time compare so timing doesn't leak the token
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
    """Return the existing pending row (if any) so we can preserve fields the
    webhook doesn't carry (session_id, utm, preferred_method, etc.)."""
    q = urllib.parse.quote(order_id)
    rows = _supabase_request(
        "GET",
        f"{PURCHASES_TABLE}?select=*&order_id=eq.{q}&limit=1",
    )
    return rows[0] if rows else None


def _find_participant(email, mobile, session_id):
    """Look for a matching participant row so we can set participant_id on
    the purchase. Matching mirrors sync_payments.py:
      session_id → email → mobile (last-10 digits ILIKE)."""
    from urllib.parse import quote

    candidates = []
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
        # last 10 digits — matches sync_payments.normalize_mobile behaviour
        digits = "".join(ch for ch in mobile if ch.isdigit())
        if len(digits) >= 10:
            last10 = digits[-10:]
            rows = _supabase_request(
                "GET",
                f"{PARTICIPANTS_TABLE}?select=id,email,mobile_number,session_id,created_at"
                f"&mobile_number=ilike.*{last10}*&order=created_at.desc&limit=5",
            )
            if rows:
                # Prefer the most recent — ordered desc by created_at above
                return rows[0]["id"], "mobile"

    return None, "direct"


def _upsert_purchase(row):
    """PostgREST upsert by order_id. merge-duplicates so webhook retries are
    idempotent and we don't drop fields the create-invoice row already set."""
    _supabase_request(
        "POST",
        f"{PURCHASES_TABLE}?on_conflict=order_id",
        body=row,
        extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
    )


# ---------------------------------------------------------------------------
# Event handling
# ---------------------------------------------------------------------------

# Statuses we care about. Xendit sends uppercase.
_HANDLED_STATUSES = {"PAID", "SETTLED", "EXPIRED", "FAILED"}


def _status_to_internal(xendit_status):
    """Normalize to the string we write to payment_status. SETTLED is the
    post-settlement version of PAID (funds cleared) — we treat it as PAID
    for dashboard simplicity; if we ever need to distinguish, the raw_row
    blob has the exact Xendit status."""
    s = (xendit_status or "").upper()
    if s in ("PAID", "SETTLED"):
        return "PAID"
    return s  # EXPIRED / FAILED / anything else pass-through


def _handle_event(body):
    """Given a parsed Xendit webhook body, update the matching purchase row.

    Returns (http_status, response_payload) to send back to Xendit.
    We always aim to return 200 so Xendit doesn't retry; anything unexpected
    is logged and we still 200. Real failures (auth, bad JSON) are handled
    upstream before this is called.
    """
    status = (body.get("status") or "").upper()
    external_id = body.get("external_id")

    if not external_id:
        print(f"[xendit-webhook] missing external_id in payload: {str(body)[:300]}", flush=True)
        return 200, {"ok": True, "note": "ignored (no external_id)"}

    if status not in _HANDLED_STATUSES:
        # PENDING / other intermediate states — ack without changing state.
        print(f"[xendit-webhook] ignoring status={status} order={external_id}", flush=True)
        return 200, {"ok": True, "note": f"ignored status {status}"}

    internal_status = _status_to_internal(status)

    # Fetch existing row to preserve create-invoice fields
    existing = _fetch_purchase_by_order_id(external_id) or {}
    email = (body.get("payer_email") or existing.get("email") or "").lower()
    mobile = existing.get("mobile") or ""
    session_id = existing.get("session_id")

    participant_id = existing.get("participant_id")
    match_method = existing.get("match_method")
    if internal_status == "PAID" and not participant_id:
        try:
            participant_id, match_method = _find_participant(email, mobile, session_id)
        except Exception as exc:  # noqa: BLE001
            # Matcher failure shouldn't block writing the PAID status
            print(f"[xendit-webhook] matcher error: {type(exc).__name__}: {exc}", flush=True)
            participant_id, match_method = None, "direct"

    # Xendit webhook fields that are useful to persist
    paid_at = body.get("paid_at") or body.get("updated") or body.get("created")
    amount = body.get("amount") or existing.get("amount")
    payment_channel = body.get("payment_channel") or body.get("payment_method")

    row = {
        # Identity
        "order_id":         external_id,
        "xendit_invoice_id": body.get("id") or existing.get("xendit_invoice_id"),
        # Status
        "payment_status":   internal_status,
        "payment_provider": "xendit",
        "payment_channel":  payment_channel,
        "paid_at":          paid_at if internal_status == "PAID" else existing.get("paid_at"),
        # Amount / totals (webhook is authoritative)
        "amount":           amount,
        "quantity":         existing.get("quantity") or 1,
        "total":            amount,
        # Attribution
        "participant_id":   participant_id,
        "match_method":     match_method,
        # Raw dump for forensics
        "raw_row":          {
            "source": "xendit-webhook",
            "status": status,
            "event":  body.get("event"),
            "id":     body.get("id"),
            "paid_at": paid_at,
            "payment_channel": payment_channel,
        },
    }
    # Preserve fields the webhook doesn't re-send so we don't blank them on upsert
    for k in ("email", "mobile", "full_name", "ticket_tier", "session_id",
              "invoice_url", "preferred_method",
              "utm_source", "utm_medium", "utm_campaign", "utm_content"):
        if existing.get(k) is not None:
            row[k] = existing[k]
    # If the row didn't exist yet (webhook beat create-invoice's DB write —
    # unlikely but possible), backfill email from the webhook payload.
    if not existing and email:
        row["email"] = email

    _upsert_purchase(row)

    print(f"[xendit-webhook] upserted order={external_id} status={internal_status} "
          f"participant_id={participant_id} method={match_method}", flush=True)

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
        # Verify shared-secret header before we parse or touch the DB
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
            # Return 500 so Xendit retries — this is a config error we need to fix
            _send_json(self, 500, {"error": "Server misconfiguration"})
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[xendit-webhook] error: {type(exc).__name__}: {exc}", flush=True)
            # Return 200 so Xendit doesn't hammer retries during a transient fault.
            # The event is visible in Vercel logs — we'll re-drive manually if needed.
            _send_json(self, 200, {"ok": False, "note": "deferred"})
            return

        _send_json(self, status, payload)

    def log_message(self, format, *args):
        pass
