"""Vercel Python serverless: the one endpoint that handles a webinar signup.

Steps (executed in order, never blocking on failures):
  1. Validate payload.
  2. POST to a Google Apps Script webhook that appends the row to a Sheet.
     (Deploy the .gs in sheets/apps-script.gs as a Web App; paste URL into
      SHEETS_WEBHOOK_URL.)
  3. Send the confirmation email via Brevo (api.brevo.com/v3/smtp/email).
  4. Return { ok, sheet, email } so the client can proceed to thank-you.

Env:
  SHEETS_WEBHOOK_URL    (required)   Apps Script web-app deployment URL
  BREVO_API_KEY         (required)   same key as the main summit project
  BREVO_SENDER_EMAIL    (optional)   defaults to success@exponential-university.live
  BREVO_SENDER_NAME     (optional)   defaults to "Business Unlocked"
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "emails" / "webinar-confirmation.html"

DEFAULT_SENDER_EMAIL = "success@exponential-university.live"
DEFAULT_SENDER_NAME = "Business Unlocked"
SUBJECT = "You're in — your Zoom details inside"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 10) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 500, str(e)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------
def _render(template: str, vars: dict) -> str:
    out = template
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def _unsubscribe_url(email: str) -> str:
    return (
        "https://exponential-university.live/free/unsubscribe?email="
        + urllib.parse.quote(email)
    )


# ---------------------------------------------------------------------------
# Step 1: append to Google Sheet via Apps Script webhook
# ---------------------------------------------------------------------------
def _append_to_sheet(payload: dict) -> dict:
    url = os.environ.get("SHEETS_WEBHOOK_URL")
    if not url:
        return {"ok": False, "skipped": True, "reason": "SHEETS_WEBHOOK_URL not set"}

    status, body = _post_json(
        url,
        payload,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    return {"ok": 200 <= status < 300, "status": status, "body": body[:300]}


# ---------------------------------------------------------------------------
# Step 2: send Brevo confirmation email
# ---------------------------------------------------------------------------
def _send_email(name: str, email: str) -> dict:
    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        return {"ok": False, "skipped": True, "reason": "BREVO_API_KEY not set"}

    try:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Template load failed: {e}"}

    first_name = name.split()[0].title() if name else "there"
    html = _render(
        template,
        {
            "name": first_name,
            "unsubscribe_url": _unsubscribe_url(email),
        },
    )

    sender_email = os.environ.get("BREVO_SENDER_EMAIL", DEFAULT_SENDER_EMAIL)
    sender_name = os.environ.get("BREVO_SENDER_NAME", DEFAULT_SENDER_NAME)

    status, body = _post_json(
        "https://api.brevo.com/v3/smtp/email",
        {
            "sender": {"email": sender_email, "name": sender_name},
            "to": [{"email": email, "name": name}],
            "subject": SUBJECT,
            "htmlContent": html,
        },
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=12,
    )
    return {"ok": 200 <= status < 300, "status": status, "body": body[:300]}


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
class handler(BaseHTTPRequestHandler):  # noqa: N801

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            return _send_json(self, 400, {"error": "Invalid JSON body."})

        name = (payload.get("name") or "").strip()
        email = (payload.get("email") or "").strip().lower()
        phone = (payload.get("phone") or "").strip()
        consent = bool(payload.get("marketing_consent"))

        if not name or len(name) < 2:
            return _send_json(self, 400, {"error": "Missing name."})
        if not email or not EMAIL_RE.match(email):
            return _send_json(self, 400, {"error": "Invalid email."})
        if not phone or len(phone) < 7:
            return _send_json(self, 400, {"error": "Missing contact number."})

        row = {
            "name": name,
            "email": email,
            "phone": phone,
            "marketing_consent": consent,
            "utm_source": payload.get("utm_source") or "",
            "utm_medium": payload.get("utm_medium") or "",
            "utm_campaign": payload.get("utm_campaign") or "",
            "utm_content": payload.get("utm_content") or "",
            "utm_term": payload.get("utm_term") or "",
            "referrer": payload.get("referrer") or "",
            "user_agent": payload.get("user_agent") or "",
        }

        sheet = _append_to_sheet(row)
        mail = _send_email(name, email)

        # Return 200 as long as the sheet write worked — email failures
        # are not worth blocking the user on.
        if sheet.get("ok") or sheet.get("skipped"):
            return _send_json(self, 200, {"ok": True, "sheet": sheet, "email": mail})
        return _send_json(
            self, 502, {"ok": False, "error": "Sheet write failed.", "sheet": sheet, "email": mail}
        )

    def do_GET(self) -> None:  # noqa: N802
        return _send_json(self, 405, {"error": "Use POST."})
