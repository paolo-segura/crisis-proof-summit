"""
Vercel serverless endpoint /api/sync-manual-sales

Reads the client-maintained "BUS: Leads" Google Sheet (warm leads, partner
ticket batches, bulk-discount form responses) and pipes the entries into
new_business_normal_purchases as manual sales so they roll into the /admin
dashboard alongside online checkouts.

Cron: every 30 min (vercel.json). Auth: CRON_SECRET (same pattern as
/api/sync-payments).

This file is a thin wrapper. All sync logic lives in sync_manual_sales.py
so the test suite can import it cleanly.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_manual_sales as sms  # noqa: E402


def _send_json(h, status, payload):
    body = json.dumps(payload).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def _is_authorized_cron_request(h):
    """Same pattern as /api/sync-payments. CRON_SECRET required in prod;
    optional in local/dev for manual triggers."""
    expected = os.environ.get("CRON_SECRET")
    is_production = os.environ.get("VERCEL_ENV") == "production"
    if not expected:
        return not is_production
    return h.headers.get("Authorization", "") == f"Bearer {expected}"


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if not _is_authorized_cron_request(self):
            _send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            result = sms.run_sync(
                read_tabs=sms.read_manual_sheet,
                upsert=sms.supabase_upsert_manual,
                write_log=sms.supabase_write_log,
                prune_warm_orphans=sms.supabase_prune_warm_orphans,
            )
            _send_json(self, 200, result)
        except Exception as exc:  # noqa: BLE001
            print(f"[sync-manual-sales] error: {type(exc).__name__}: {exc}", flush=True)
            _send_json(self, 500, {"error": "Sync failed; see server logs."})

    def log_message(self, format, *args):
        pass
