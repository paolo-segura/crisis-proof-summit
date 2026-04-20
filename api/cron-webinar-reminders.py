"""Vercel cron — sends the same-day webinar reminder ~1 hour before each session.

Runs daily at 10:00 UTC (6PM PHT). If today matches one of the 6 webinar
dates, it fetches the registered users from the Apps Script webhook and
sends each one a reminder email via Brevo (immediate send — no scheduling).

Env:
  SHEETS_WEBHOOK_URL   Apps Script /exec URL (used for both write and read)
  SHEETS_READ_SECRET   matches the Apps Script SHEETS_READ_SECRET property
  BREVO_API_KEY        transactional sender
  BREVO_SENDER_EMAIL   optional (default success@exponential-university.live)
  BREVO_SENDER_NAME    optional (default "Business Unlocked")
  CRON_SECRET          Vercel cron sends this in the Authorization header
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from http.server import BaseHTTPRequestHandler
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "emails" / "webinar-reminder.html"

DEFAULT_SENDER_EMAIL = "success@exponential-university.live"
DEFAULT_SENDER_NAME = "Business Unlocked"

MAIN_EVENT_URL = "https://www.exponential-university.live/the-new-business-normal"
BASE_URL = "https://exponential-university.live"
ZOOM_URL = "https://us06web.zoom.us/j/82900398611?pwd=iP8tYUqpXBY5Nzo4vPm4EUFWbDn4wF.1"

# --- Webinar schedule -------------------------------------------------------
# Dates are the local PHT day the session fires. The cron runs at 10:00 UTC
# (6:00 PM PHT) on these dates — roughly 1 hour before the 7PM sessions,
# 2 hours before the 8PM W1.
WEBINARS = [
    {
        "num": "01",
        "date_iso": "2026-04-22",
        "pillar": "Overview",
        "speaker": "Migs Flores",
        "topic": "Why Filipino Businesses Are Closing — And The 4 Unlocks That Keep Them Open",
        "time_label": "Today · Wed · Apr 22, 2026 · 8:00 PM PHT",
        "poster": "migs-flores-webinar.png",
        "ics": "w1.ics",
    },
    {
        "num": "02",
        "date_iso": "2026-04-25",
        "pillar": "Flexibility",
        "speaker": "Charlie Gengos",
        "topic": "3 Ways to Sell Kahit Bumagsak ang Isang Revenue Stream",
        "time_label": "Today · Sat · Apr 25, 2026 · 7:00 PM PHT",
        "poster": "charlie-gengos-webinar.png",
        "ics": "w2.ics",
    },
    {
        "num": "03",
        "date_iso": "2026-04-29",
        "pillar": "Final Unlock",
        "speaker": "Russ Juson",
        "topic": "Your 72-Hour Crisis-Proof Action Plan — integrating the 4 Pillars",
        "time_label": "Today · Wed · Apr 29, 2026 · 7:00 PM PHT",
        "poster": "russ-juson.png",
        "ics": "w3.ics",
    },
    {
        "num": "04",
        "date_iso": "2026-05-02",
        "pillar": "Adaptability",
        "speaker": "Jay Jazmines",
        "topic": "Using AI to Future-Proof Your Business in 2026",
        "time_label": "Today · Sat · May 2, 2026 · 7:00 PM PHT",
        "poster": "jay-jazmines-webinar.png",
        "ics": "w4.ics",
    },
    {
        "num": "05",
        "date_iso": "2026-05-04",
        "pillar": "Continuity",
        "speaker": "Nani Razon",
        "topic": "The Cashflow System na Hindi Matitinag ng Krisis",
        "time_label": "Today · Mon · May 4, 2026 · 7:00 PM PHT",
        "poster": "nani-razon-webinar.png",
        "ics": "w5.ics",
    },
    {
        "num": "06",
        "date_iso": "2026-05-07",
        "pillar": "Presence",
        "speaker": "Diana Jane Mitchell",
        "topic": "Paano Ka Makita ng Customers Mo Kahit Walang Ad Budget",
        "time_label": "Today · Thu · May 7, 2026 · 7:00 PM PHT",
        "poster": "diana-mitchell.png",
        "ics": "w6.ics",
    },
]


# ---------------------------------------------------------------------------
def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _http_get(url: str, timeout: int = 20) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 500, str(e)


def _http_post_json(url: str, payload: dict, headers: dict, timeout: int = 12) -> tuple[int, str]:
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


def _pick_webinar_for_today() -> dict | None:
    today = date.today().isoformat()
    for w in WEBINARS:
        if w["date_iso"] == today:
            return w
    return None


def _fetch_registrations() -> tuple[list[dict], dict]:
    url = os.environ.get("SHEETS_WEBHOOK_URL")
    secret = os.environ.get("SHEETS_READ_SECRET")
    if not url or not secret:
        return [], {"ok": False, "error": "SHEETS_WEBHOOK_URL or SHEETS_READ_SECRET not set"}

    full = url + ("&" if "?" in url else "?") + "action=list&secret=" + urllib.parse.quote(secret)
    status, body = _http_get(full)
    if not (200 <= status < 300):
        return [], {"ok": False, "status": status, "body": body[:300]}

    try:
        data = json.loads(body)
    except Exception as e:
        return [], {"ok": False, "error": f"Invalid JSON: {e}", "body": body[:300]}

    if not data.get("ok"):
        return [], {"ok": False, "error": data.get("error") or "apps-script returned ok=false"}

    rows = data.get("rows") or []
    return rows, {"ok": True, "count": len(rows)}


def _send_reminder(template: str, webinar: dict, row: dict) -> dict:
    email = str(row.get("email") or "").strip().lower()
    name = str(row.get("name") or "").strip()
    consent = str(row.get("marketing_consent") or "").upper() == "TRUE"

    if not email or "@" not in email:
        return {"ok": False, "skipped": True, "reason": "invalid email"}
    if not consent:
        return {"ok": False, "skipped": True, "reason": "no marketing consent"}

    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        return {"ok": False, "skipped": True, "reason": "BREVO_API_KEY not set"}

    first_name = name.split()[0].title() if name else "there"
    poster_url = f"{BASE_URL}/assets/images/speakers/{webinar['poster']}"
    ics_url = f"{BASE_URL}/cal/{webinar['ics']}"

    html = _render(
        template,
        {
            "name": first_name,
            "preheader": f"Starts soon — {webinar['speaker']} on {webinar['topic']}.",
            "urgency_label": "Starts today · Join on Zoom",
            "headline": "Starts in about 1 hour",
            "lead": f"Your webinar with {webinar['speaker']} is starting soon. Same Zoom link you've been using — tap below to join.",
            "webinar_num": webinar["num"],
            "pillar": webinar["pillar"],
            "speaker": webinar["speaker"],
            "topic": webinar["topic"],
            "time_label": webinar["time_label"],
            "poster_url": poster_url,
            "zoom_url": ZOOM_URL,
            "ics_url": ics_url,
            "main_event_url": MAIN_EVENT_URL,
            "unsubscribe_url": _unsubscribe_url(email),
        },
    )

    sender_email = os.environ.get("BREVO_SENDER_EMAIL", DEFAULT_SENDER_EMAIL)
    sender_name = os.environ.get("BREVO_SENDER_NAME", DEFAULT_SENDER_NAME)
    subject = f"Starts in 1 hour — {webinar['speaker']} · W{webinar['num']}"

    status, body = _http_post_json(
        "https://api.brevo.com/v3/smtp/email",
        {
            "sender": {"email": sender_email, "name": sender_name},
            "to": [{"email": email, "name": name or email}],
            "subject": subject,
            "htmlContent": html,
        },
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=15,
    )
    return {"ok": 200 <= status < 300, "status": status, "email": email}


def _run(force_webinar_num: str | None = None) -> dict:
    if force_webinar_num:
        webinar = next((w for w in WEBINARS if w["num"] == force_webinar_num), None)
        if not webinar:
            return {"ok": False, "error": f"Unknown webinar: {force_webinar_num}"}
    else:
        webinar = _pick_webinar_for_today()
        if not webinar:
            return {"ok": True, "skipped": True, "reason": f"no webinar on {date.today().isoformat()}"}

    try:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Template load failed: {e}"}

    rows, meta = _fetch_registrations()
    if not meta.get("ok"):
        return {"ok": False, "error": "Failed to fetch registrations", "meta": meta}

    # Dedupe by email
    seen = set()
    unique_rows = []
    for r in rows:
        e = str(r.get("email") or "").strip().lower()
        if e and e not in seen:
            seen.add(e)
            unique_rows.append(r)

    # Parallel send
    results = {"sent": 0, "skipped": 0, "failed": 0, "errors": []}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for res in pool.map(lambda r: _send_reminder(template, webinar, r), unique_rows):
            if res.get("ok"):
                results["sent"] += 1
            elif res.get("skipped"):
                results["skipped"] += 1
            else:
                results["failed"] += 1
                if len(results["errors"]) < 10:
                    results["errors"].append(res)

    return {
        "ok": True,
        "webinar": f"W{webinar['num']} — {webinar['speaker']}",
        "total_rows": len(rows),
        "unique_recipients": len(unique_rows),
        **results,
    }


# ---------------------------------------------------------------------------
class handler(BaseHTTPRequestHandler):  # noqa: N801

    def _authorized(self) -> bool:
        expected = os.environ.get("CRON_SECRET")
        if not expected:
            return True  # if no secret configured, allow (dev)
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {expected}"

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            return _send_json(self, 401, {"error": "unauthorized"})

        # Allow ?webinar=01..06 to force a specific run for testing.
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        force = (qs.get("webinar") or [None])[0]

        result = _run(force_webinar_num=force)
        status = 200 if result.get("ok") else 500
        return _send_json(self, status, result)

    def do_POST(self) -> None:  # noqa: N802
        return self.do_GET()
