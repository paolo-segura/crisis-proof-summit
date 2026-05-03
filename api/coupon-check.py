"""
GET /api/coupon-check?code=X — public coupon validator.

Used by the inline checkout to live-validate codes a buyer types. No auth: codes
are shared publicly (in DMs, IG stories, etc.) — confirming what someone already
typed isn't a leak. The full LIST of codes stays auth-gated at /api/coupons.

Returns:
  { valid: true,  code, base_tier, amount, label }    — code exists and is active
  { valid: false }                                    — unknown / inactive / bad input

Cache: per-cold-start dict shared with create-invoice.py would be ideal, but each
serverless function has its own process. We do a 5-min TTL fetch here too so a
single buyer typing a code 6 chars at a time doesn't fire 6 sequential DB hits.

Required env vars:
  - SUPABASE_URL
  - SUPABASE_SERVICE_KEY
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request


COUPONS_TABLE = "bu_coupons"
CODE_PATTERN = re.compile(r"^[A-Z0-9]{2,40}$")

# Per-container cache. TTL'd so coupons added in /admin/coupons go live within
# 5 min worst-case across all serverless containers.
_CACHE = None             # dict[str, dict] | None — None means never fetched OR fetch failed
_CACHE_FETCHED_AT = 0.0   # epoch seconds, set on every attempt (success OR failure)
_CACHE_TTL = 300          # 5 minutes


def _add_cors_headers(h):
    origin = h.headers.get("Origin", "")
    h.send_header("Access-Control-Allow-Origin", origin or "*")
    h.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "Content-Type")
    h.send_header("Vary", "Origin")


def _send_json(h, status, payload):
    body = json.dumps(payload).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    # Short browser cache so a buyer who types KATH then changes their mind and
    # types it again doesn't refetch. Server cache still respects TTL.
    h.send_header("Cache-Control", "public, max-age=60")
    _add_cors_headers(h)
    h.end_headers()
    h.wfile.write(body)


def _fetch_active_coupons():
    """Read all active coupons. Returns dict keyed by uppercase code, or None
    on any failure (caller treats None as 'no valid codes available right now')."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return None
    try:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/rest/v1/{COUPONS_TABLE}"
            f"?select=code,base_tier,amount,label&active=eq.true",
            method="GET",
        )
        req.add_header("apikey", key)
        req.add_header("Authorization", f"Bearer {key}")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=8) as resp:
            rows = json.loads(resp.read().decode("utf-8") or "[]")
    except Exception as exc:  # noqa: BLE001
        print(f"[coupon-check] DB fetch failed: {type(exc).__name__}: {exc}", flush=True)
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
        out[code] = {
            "code": code,
            "base_tier": base,
            "amount": amount,
            "label": label,
        }
    return out


def _lookup(code):
    global _CACHE, _CACHE_FETCHED_AT
    norm = (code or "").upper().strip()
    if not norm:
        return None
    now = time.time()
    if (now - _CACHE_FETCHED_AT) > _CACHE_TTL:
        result = _fetch_active_coupons()
        _CACHE_FETCHED_AT = now  # stamp on success AND failure to avoid retry storms
        if result is not None:
            _CACHE = result
        # On failure with prior cache, we keep serving the prior cache.
    if _CACHE is None:
        return None
    return _CACHE.get(norm)


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(204)
        _add_cors_headers(self)
        self.end_headers()

    def do_GET(self):
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        raw_code = (params.get("code") or [""])[0]
        norm = raw_code.strip().upper()

        # Bad shape — return valid=false without hitting DB. Saves cycles + makes
        # spam-tries visibly cheap.
        if not norm or not CODE_PATTERN.match(norm):
            _send_json(self, 200, {"valid": False})
            return

        coupon = _lookup(norm)
        if coupon is None:
            _send_json(self, 200, {"valid": False})
            return

        _send_json(self, 200, {
            "valid": True,
            "code": coupon["code"],
            "base_tier": coupon["base_tier"],
            "amount": coupon["amount"],
            "label": coupon["label"],
        })

    def log_message(self, format, *args):
        pass
