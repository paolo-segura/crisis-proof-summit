"""
Vercel serverless endpoint /api/send-nurture.

Vercel routes api/send-nurture.py to URL /api/send-nurture.
Triggered daily by a cron entry in vercel.json (9AM Manila = 1AM UTC).

Thin wrapper — all logic lives in send_nurture.py (underscore module)
so the test suite can import it cleanly.

Query params:
  ?dry_run=true    Run without sending emails (still logs to DB with dry_run=true)

Env vars:
  BREVO_API_KEY            Required. Brevo transactional API key.
  SUPABASE_URL             Required.
  SUPABASE_SERVICE_KEY     Required.
  SENDER_EMAIL             Optional. Default: success@exponential-university.live
  SENDER_NAME              Optional. Default: Business Unlocked
  NURTURE_START_PAID_AT    Optional ISO timestamp. Only process customers who paid
                           on or after this date. Omit to include all paid customers.
  CRON_SECRET              Optional. If set, enforces Bearer auth on prod.
"""

import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import send_nurture as sn  # noqa: E402


def _send_json(h, status, payload):
    body = json.dumps(payload).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def _is_authorized(h):
    """
    Same fail-closed-in-prod pattern as abandoned-cart.py.
    If CRON_SECRET is set, require Bearer auth.
    If not set, allow in non-production environments only.
    """
    expected = os.environ.get("CRON_SECRET")
    is_production = os.environ.get("VERCEL_ENV") == "production"
    if not expected:
        return not is_production
    return h.headers.get("Authorization", "") == f"Bearer {expected}"


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if not _is_authorized(self):
            _send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            # Parse query params
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            dry_run = qs.get("dry_run", ["false"])[0].lower() == "true"

            # Optional cutoff date for which customers to process
            min_paid_at_iso = os.environ.get("NURTURE_START_PAID_AT") or None

            result = sn.run_send_nurture(
                now=datetime.now(timezone.utc),
                min_paid_at_iso=min_paid_at_iso,
                dry_run=dry_run,
            )
            _send_json(self, 200, result)

        except Exception as exc:  # noqa: BLE001
            print(f"[send-nurture] error: {type(exc).__name__}: {exc}", flush=True)
            _send_json(self, 500, {"error": "Send-nurture run failed; see server logs."})

    def log_message(self, format, *args):
        pass
