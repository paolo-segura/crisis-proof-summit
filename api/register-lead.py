"""Vercel Python serverless: BU lead-acquisition signup endpoint.

Steps (executed in order):
  1. Validate payload (honeypot check, field validation).
  2. POST lead row to BU Leads Google Apps Script (→ BU Leads Google Sheet).
  3. Fire a Brevo "we'll call you" confirmation email to the lead.
     (Sheet write is authoritative — email failure does NOT block a 200.)
  4. Return { ok: true } on success.

Env:
  BU_LEADS_APPS_SCRIPT_URL     (required) Apps Script web-app deployment URL for BU Leads sheet
  BREVO_API_KEY                (required) Brevo transactional email API key
  BREVO_SENDER_EMAIL           (optional) defaults to success@exponential-university.live
  BREVO_SENDER_NAME            (optional) defaults to "Business Unlocked"
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "emails" / "lead-confirmation.html"

DEFAULT_SENDER_EMAIL = "success@exponential-university.live"
DEFAULT_SENDER_NAME = "Business Unlocked"
CONFIRMATION_SUBJECT = "Salamat — tatawagan ka namin within 24 hours"


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
# Step 1: append lead to BU Leads Google Sheet via Apps Script
# ---------------------------------------------------------------------------
def _append_lead_to_sheet(row: dict) -> dict:
    url = os.environ.get("BU_LEADS_APPS_SCRIPT_URL")
    if not url:
        return {"ok": False, "skipped": True, "reason": "BU_LEADS_APPS_SCRIPT_URL not set"}

    status, body = _post_json(
        url,
        row,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    return {"ok": 200 <= status < 300, "status": status, "body": body[:300]}


# ---------------------------------------------------------------------------
# Template rendering — simple {{var}} replacement, same pattern as register-free.py
# ---------------------------------------------------------------------------
def _render(template: str, vars: dict) -> str:
    out = template
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out


# ---------------------------------------------------------------------------
# Step 2: send Brevo confirmation email to the lead (inline HTML, no templateId)
# ---------------------------------------------------------------------------
def _send_confirmation_email(name: str, email: str) -> dict:
    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        print("[register-lead] BREVO_API_KEY not set — skipping confirmation email")
        return {"ok": False, "skipped": True, "reason": "BREVO_API_KEY not set"}

    try:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[register-lead] WARNING: template load failed: {e}")
        return {"ok": False, "error": f"Template load failed: {e}"}

    first_name = name.split()[0].title() if name else "there"
    html = _render(template, {"first_name": first_name})

    sender_email = os.environ.get("BREVO_SENDER_EMAIL", DEFAULT_SENDER_EMAIL)
    sender_name = os.environ.get("BREVO_SENDER_NAME", DEFAULT_SENDER_NAME)

    status, body = _post_json(
        "https://api.brevo.com/v3/smtp/email",
        {
            "sender": {"email": sender_email, "name": sender_name},
            "to": [{"email": email, "name": name}],
            "subject": CONFIRMATION_SUBJECT,
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

        # Honeypot: silently succeed for bots that fill the website field
        if payload.get("website"):
            return _send_json(self, 200, {"ok": True})

        # Extract and validate fields
        full_name = (payload.get("full_name") or "").strip()
        email = (payload.get("email") or "").strip().lower()
        # Accept either key name for flexibility
        mobile = (
            payload.get("mobile_number")
            or payload.get("mobile")
            or ""
        ).strip()
        best_time = (payload.get("best_time_to_call") or "").strip()[:60]

        if not full_name or len(full_name) < 2:
            return _send_json(self, 400, {"error": "Full name is required."})
        if not email or not EMAIL_RE.match(email):
            return _send_json(self, 400, {"error": "A valid email address is required."})
        if not mobile or len(mobile) < 7:
            return _send_json(self, 400, {"error": "A valid mobile number is required."})

        submitted_at = datetime.now(timezone.utc).isoformat()

        row = {
            "submitted_at": submitted_at,
            "name": full_name,
            "email": email,
            "phone": mobile,
            "best_time_to_call": best_time,
            "status": "new",
            "source": "business_unlocked",
            # UTM fields
            "utm_source": (payload.get("utm_source") or "").strip()[:200],
            "utm_medium": (payload.get("utm_medium") or "").strip()[:200],
            "utm_campaign": (payload.get("utm_campaign") or "").strip()[:200],
            "utm_content": (payload.get("utm_content") or "").strip()[:200],
            "utm_term": (payload.get("utm_term") or "").strip()[:200],
            # Optional session tracking
            "session_id": (payload.get("session_id") or "").strip()[:64],
        }

        sheet = _append_lead_to_sheet(row)
        mail = _send_confirmation_email(full_name, email)

        # Sheet write is the authoritative "lead captured" signal.
        # Email failure is non-blocking.
        if sheet.get("ok") or sheet.get("skipped"):
            return _send_json(self, 200, {"ok": True, "sheet": sheet, "email": mail})

        return _send_json(
            self, 502,
            {"ok": False, "error": "Sheet write failed.", "sheet": sheet, "email": mail},
        )

    def do_GET(self) -> None:  # noqa: N802
        return _send_json(self, 405, {"error": "Use POST."})
