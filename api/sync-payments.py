"""
Vercel serverless endpoint /api/sync-payments

Vercel routes file path api/sync-payments.py to URL /api/sync-payments.
Triggered by a cron entry in vercel.json every 15 minutes (Pro tier).

This file is a thin wrapper. All sync logic lives in `sync_payments.py`
(underscore — Python module name) so the test suite can import it cleanly.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Vercel runs each function in /api as its own entrypoint, with /api on the
# import path. So `import sync_payments` resolves to api/sync_payments.py.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_payments as sp  # noqa: E402


def _send_json(h, status, payload):
    body = json.dumps(payload).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def _is_authorized_cron_request(h):
    """
    Vercel cron sends `Authorization: Bearer <CRON_SECRET>` when CRON_SECRET
    is set in env vars.

    Locally (VERCEL_ENV unset or 'development'), CRON_SECRET is optional —
    requests without the header are allowed, useful for manual triggers.

    In production (VERCEL_ENV='production'), CRON_SECRET MUST be set;
    if missing, every request is rejected to avoid public exposure.
    """
    expected = os.environ.get("CRON_SECRET")
    is_production = os.environ.get("VERCEL_ENV") == "production"

    if not expected:
        if is_production:
            # Refuse to serve in production without auth — fail closed
            return False
        return True  # local/dev bypass

    auth = h.headers.get("Authorization", "")
    return auth == f"Bearer {expected}"


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if not _is_authorized_cron_request(self):
            _send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            result = sp.run_sync(
                read_rows=sp.read_bridge_sheet,
                upsert=sp.supabase_upsert_purchase,
                fetch_participants=sp.supabase_fetch_participants_by_contacts,
                fetch_unmatched=sp.supabase_fetch_unmatched_purchases,
                update_match=sp.supabase_update_purchase_match,
                write_log=sp.supabase_write_sync_log,
            )
            _send_json(self, 200, result)
        except Exception as exc:  # noqa: BLE001
            # Log full details server-side (Vercel function logs);
            # return only a generic message to the caller so internal paths,
            # env names, and supabase URLs don't leak via the HTTP response.
            print(f"[sync-payments] error: {type(exc).__name__}: {exc}", flush=True)
            _send_json(self, 500, {"error": "Sync failed; see server logs."})

    def log_message(self, format, *args):
        pass
