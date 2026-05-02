"""
GET / POST / PATCH /api/coupons — admin coupon management.

Backed by the bu_coupons Supabase table. Auth: ADMIN_PASSWORD Bearer token,
same as /api/report. CORS allows the same origin as the rest of the dashboard.

  GET    /api/coupons                       -> list every coupon (active + inactive)
  POST   /api/coupons                       -> create a coupon { code, base_tier, amount, label, created_by? }
  PATCH  /api/coupons?code=KATH             -> update fields { active?, amount?, label?, base_tier? }

Validation lives entirely on the server. The client form is convenience only.

Required env vars:
  - ADMIN_PASSWORD
  - SUPABASE_URL
  - SUPABASE_SERVICE_KEY
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request


COUPONS_TABLE = "bu_coupons"
ALLOWED_TIERS = ("early_bird", "regular", "vip")

# Code format: 2-40 chars, letters / digits only, normalized to uppercase.
# Hyphens / underscores rejected on purpose to keep codes typo-resistant
# (KATH-BU vs KATHBU vs KATH_BU is a support ticket waiting to happen).
CODE_PATTERN = re.compile(r"^[A-Z0-9]{2,40}$")

# Reasonable price range. Below ₱100 is almost certainly a typo (₱9 instead of
# ₱900); above ₱50,000 is well above any real BU ticket and very likely a typo
# (₱20000 instead of ₱2000). Outside the band -> reject with a friendly message.
MIN_AMOUNT = 100
MAX_AMOUNT = 50_000


# ---------------------------------------------------------------------------
# Helpers (same patterns as api/report.py)
# ---------------------------------------------------------------------------

def _add_cors_headers(h):
    origin = h.headers.get("Origin", "")
    h.send_header("Access-Control-Allow-Origin", origin or "*")
    h.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
    h.send_header("Vary", "Origin")


def _send_json(h, status, payload):
    body = json.dumps(payload).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    _add_cors_headers(h)
    h.end_headers()
    h.wfile.write(body)


def _check_admin_auth(h):
    """ADMIN_PASSWORD Bearer — same scheme as /api/report. Returns True/False;
    on False, the 401 response has already been sent."""
    auth = h.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        _send_json(h, 401, {"error": "Missing or malformed Authorization header"})
        return False
    expected = os.environ.get("ADMIN_PASSWORD")
    if not expected:
        _send_json(h, 500, {"error": "Server missing ADMIN_PASSWORD"})
        return False
    if auth[len("Bearer "):] != expected:
        _send_json(h, 401, {"error": "Invalid password"})
        return False
    return True


def _supabase_env():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    return url.rstrip("/"), key


def _supabase_request(method, path, body=None, extra_headers=None):
    url, key = _supabase_env()
    full = f"{url}/rest/v1/{path.lstrip('/')}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(full, data=data, method=method)
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


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_create_payload(data):
    """Returns (clean_dict, None) on success or (None, error_msg) on failure."""
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object."

    code = str(data.get("code", "")).strip().upper()
    if not CODE_PATTERN.match(code):
        return None, "Code must be 2-40 characters, letters and digits only (e.g. KATHVIP, MIGS50)."

    base_tier = str(data.get("base_tier", "")).strip().lower()
    if base_tier not in ALLOWED_TIERS:
        return None, f"base_tier must be one of: {', '.join(ALLOWED_TIERS)}."

    raw_amount = data.get("amount")
    try:
        amount = float(raw_amount)
    except (TypeError, ValueError):
        return None, "amount must be a number (PHP, no currency symbol)."
    if amount < MIN_AMOUNT or amount > MAX_AMOUNT:
        return None, f"amount must be between ₱{MIN_AMOUNT:,} and ₱{MAX_AMOUNT:,}."

    label = str(data.get("label", "")).strip()
    if not label:
        return None, "label is required (e.g. 'Kath x BU')."
    if len(label) > 120:
        return None, "label must be 120 characters or fewer."

    created_by = str(data.get("created_by", "")).strip()[:80] or None

    return {
        "code": code,
        "base_tier": base_tier,
        "amount": amount,
        "label": label,
        "active": True,
        "created_by": created_by,
    }, None


def _validate_patch_payload(data):
    """Partial update — only the fields present are validated."""
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object."
    out = {}

    if "active" in data:
        active = data["active"]
        if not isinstance(active, bool):
            return None, "active must be true or false."
        out["active"] = active

    if "amount" in data:
        try:
            amount = float(data["amount"])
        except (TypeError, ValueError):
            return None, "amount must be a number."
        if amount < MIN_AMOUNT or amount > MAX_AMOUNT:
            return None, f"amount must be between ₱{MIN_AMOUNT:,} and ₱{MAX_AMOUNT:,}."
        out["amount"] = amount

    if "label" in data:
        label = str(data["label"]).strip()
        if not label or len(label) > 120:
            return None, "label must be 1-120 characters."
        out["label"] = label

    if "base_tier" in data:
        base_tier = str(data["base_tier"]).strip().lower()
        if base_tier not in ALLOWED_TIERS:
            return None, f"base_tier must be one of: {', '.join(ALLOWED_TIERS)}."
        out["base_tier"] = base_tier

    if not out:
        return None, "No editable fields supplied. Allowed: active, amount, label, base_tier."

    return out, None


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def handle_list(h):
    """GET /api/coupons — newest first."""
    try:
        rows = _supabase_request(
            "GET",
            f"{COUPONS_TABLE}?select=code,base_tier,amount,label,active,created_at,created_by"
            f"&order=created_at.desc",
        )
    except RuntimeError as exc:
        print(f"[coupons] list error: {exc}", flush=True)
        _send_json(h, 502, {"error": "Could not load coupons. Try again."})
        return
    _send_json(h, 200, rows or [])


def handle_create(h, raw_body):
    try:
        data = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        _send_json(h, 400, {"error": "Request body must be valid JSON."})
        return

    payload, err = _validate_create_payload(data)
    if err:
        _send_json(h, 400, {"error": err})
        return

    # Insert with conflict-fail so duplicate codes can't sneak past — codes
    # are PRIMARY KEY in the table. We surface a clean 409 instead of a 500.
    try:
        _supabase_request(
            "POST",
            f"{COUPONS_TABLE}",
            body=payload,
            extra_headers={"Prefer": "return=representation"},
        )
    except RuntimeError as exc:
        msg = str(exc)
        # PostgREST surfaces Postgres '23505' (unique_violation) as a 409.
        if "23505" in msg or "duplicate key" in msg.lower():
            _send_json(h, 409, {"error": f"Code '{payload['code']}' already exists. Edit it instead, or use a different code."})
            return
        print(f"[coupons] create error: {msg}", flush=True)
        _send_json(h, 502, {"error": "Could not save coupon. Try again."})
        return

    _send_json(h, 201, {"ok": True, "coupon": payload})


def handle_patch(h, raw_body, code):
    code = str(code or "").strip().upper()
    if not CODE_PATTERN.match(code):
        _send_json(h, 400, {"error": "Missing or invalid ?code= query parameter."})
        return

    try:
        data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (ValueError, UnicodeDecodeError):
        _send_json(h, 400, {"error": "Request body must be valid JSON."})
        return

    payload, err = _validate_patch_payload(data)
    if err:
        _send_json(h, 400, {"error": err})
        return

    try:
        rows = _supabase_request(
            "PATCH",
            f"{COUPONS_TABLE}?code=eq.{urllib.parse.quote(code)}",
            body=payload,
            extra_headers={"Prefer": "return=representation"},
        )
    except RuntimeError as exc:
        print(f"[coupons] patch error: {exc}", flush=True)
        _send_json(h, 502, {"error": "Could not update coupon. Try again."})
        return

    if not rows:
        _send_json(h, 404, {"error": f"Coupon '{code}' not found."})
        return

    _send_json(h, 200, {"ok": True, "coupon": rows[0]})


# ---------------------------------------------------------------------------
# Vercel handler
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(204)
        _add_cors_headers(self)
        self.end_headers()

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return b""
        if length > 20_000:
            _send_json(self, 400, {"error": "Request body too large."})
            return None
        return self.rfile.read(length)

    def do_GET(self):
        if not _check_admin_auth(self):
            return
        handle_list(self)

    def do_POST(self):
        if not _check_admin_auth(self):
            return
        body = self._read_body()
        if body is None:
            return  # 400 already sent
        handle_create(self, body)

    def do_PATCH(self):
        if not _check_admin_auth(self):
            return
        body = self._read_body()
        if body is None:
            return
        # Code comes from the query string so we don't have to parse a path.
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        code = (params.get("code") or [""])[0]
        handle_patch(self, body, code)

    def log_message(self, format, *args):
        pass
