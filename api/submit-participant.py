"""
POST /api/submit-participant

Receives JSON from the participant-details form and forwards it to a
Google Apps Script Web App (deployed by the user) which appends the row
to a Google Sheet.

Required environment variables on Vercel:
  - APPS_SCRIPT_WEBHOOK_URL  (the "Web app URL" from the Apps Script deployment)
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.error


ALLOWED_FIELDS = [
    "full_name",
    "mobile_number",
    "email",
    "describes_you",
    "business_type",
    "referred_by",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "session_id",
    "page_url",
    "user_agent",
    "submitted_at",
]


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


def _clean_payload(raw):
    """Whitelist fields and cap string lengths to prevent abuse."""
    cleaned = {}
    for field in ALLOWED_FIELDS:
        val = raw.get(field, "")
        if val is None:
            val = ""
        if not isinstance(val, str):
            val = str(val)
        # Cap length
        cleaned[field] = val.strip()[:500]
    return cleaned


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(204)
        _add_cors_headers(self)
        self.end_headers()

    def do_POST(self):
        webhook_url = os.environ.get("APPS_SCRIPT_WEBHOOK_URL")
        if not webhook_url:
            _send_json(self, 500, {"error": "Server is not configured (missing webhook URL)."})
            return

        # Read body
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 20_000:
            _send_json(self, 400, {"error": "Invalid request body."})
            return

        raw_body = self.rfile.read(length)
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            _send_json(self, 400, {"error": "Request body must be valid JSON."})
            return

        if not isinstance(data, dict):
            _send_json(self, 400, {"error": "Payload must be a JSON object."})
            return

        payload = _clean_payload(data)

        # Minimum required fields
        for required in ("full_name", "email", "mobile_number", "describes_you", "business_type", "referred_by"):
            if not payload.get(required):
                _send_json(self, 400, {"error": f"Missing required field: {required}"})
                return

        # Forward to Apps Script as text/plain to avoid CORS preflight on its side
        forward_body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=forward_body,
            method="POST",
        )
        req.add_header("Content-Type", "text/plain;charset=utf-8")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_body = resp.read().decode("utf-8", errors="replace")
                # Apps Script usually returns JSON or plain text
                try:
                    resp_json = json.loads(resp_body)
                except ValueError:
                    resp_json = {"raw": resp_body}

                if resp.status >= 400:
                    _send_json(self, 502, {"error": "Upstream error", "details": resp_json})
                    return

                _send_json(self, 200, {"ok": True, "upstream": resp_json})
        except urllib.error.HTTPError as exc:
            _send_json(self, 502, {"error": f"Webhook returned HTTP {exc.code}"})
        except urllib.error.URLError as exc:
            _send_json(self, 502, {"error": f"Could not reach webhook: {exc.reason}"})
        except Exception as exc:  # noqa: BLE001
            _send_json(self, 500, {"error": f"Unexpected error: {type(exc).__name__}"})

    def log_message(self, format, *args):
        pass
