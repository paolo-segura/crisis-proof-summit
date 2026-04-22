"""Manual push — sends a "we're live now, join in progress" blast for a webinar.

Unlike cron-webinar-reminders.py (which fires 1-2h before the session with
"Starts in 1 hour" copy), this endpoint is meant to be hit manually the
moment the session opens on Zoom. Copy reflects "we're live now" + a short
agenda so registrants know exactly what they'll unlock if they join late.

Usage:
  curl -X POST -H "Authorization: Bearer $CRON_SECRET" \
       "https://exponential-university.live/api/push-webinar-live?webinar=01"

Env: same as cron-webinar-reminders.py (BREVO_API_KEY, SHEETS_WEBHOOK_URL,
SHEETS_READ_SECRET, BREVO_SENDER_EMAIL, BREVO_SENDER_NAME, CRON_SECRET).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "emails" / "webinar-reminder.html"

DEFAULT_SENDER_EMAIL = "success@exponential-university.live"
DEFAULT_SENDER_NAME = "Business Unlocked"

MAIN_EVENT_URL = "https://www.exponential-university.live/the-new-business-normal"
BASE_URL = "https://exponential-university.live"
ZOOM_URL = "https://us06web.zoom.us/j/82900398611?pwd=iP8tYUqpXBY5Nzo4vPm4EUFWbDn4wF.1"

# Per-webinar agenda copy — what they'll unlock if they join now.
# Kept short: 3-4 bullets, plain text, inserted into the reminder template's lead.
WEBINARS = {
    "01": {
        "num": "01",
        "pillar": "Overview",
        "speaker": "Migs Flores",
        "topic": "Why Filipino Businesses Are Closing — And The 4 Unlocks That Keep Them Open",
        "time_label": "Live right now · Apr 22, 2026 · 8:00 PM PHT",
        "poster": "migs-flores-webinar.png",
        "ics": "w1.ics",
        "agenda": [
            "Why \"successful\" PH businesses are quietly closing in 2026",
            "The 4 Unlocks that keep cashflow moving when markets go sideways",
            "The mindset shift separating owners who survive from owners who scale",
            "A preview of the 5 specialists coming in Webinars 2–6",
        ],
    },
    "02": {
        "num": "02",
        "pillar": "Flexibility",
        "speaker": "Charlie Gengos",
        "topic": "3 Ways to Sell Kahit Bumagsak ang Isang Revenue Stream",
        "time_label": "Live right now · Apr 25, 2026 · 7:00 PM PHT",
        "poster": "charlie-gengos-webinar.png",
        "ics": "w2.ics",
        "agenda": [
            "3 revenue plays you can launch in 30 days without new staff",
            "How to stress-test your current revenue stream",
            "The flexibility playbook top PH operators are quietly running",
        ],
    },
    "03": {
        "num": "03",
        "pillar": "Final Unlock",
        "speaker": "Russ Juson",
        "topic": "Your 72-Hour Crisis-Proof Action Plan — integrating the 4 Pillars",
        "time_label": "Live right now · Apr 29, 2026 · 7:00 PM PHT",
        "poster": "russ-juson.png",
        "ics": "w3.ics",
        "agenda": [
            "How to integrate all 4 pillars into one 72-hour action plan",
            "The sequencing that saves you from rebuilding the wrong thing first",
            "What to do in your business by Monday morning",
        ],
    },
    "04": {
        "num": "04",
        "pillar": "Adaptability",
        "speaker": "Jay Jazmines",
        "topic": "Using AI to Future-Proof Your Business in 2026",
        "time_label": "Live right now · May 2, 2026 · 7:00 PM PHT",
        "poster": "jay-jazmines-webinar.png",
        "ics": "w4.ics",
        "agenda": [
            "Which AI tools actually move the needle for PH SMEs",
            "Workflows you can automate this week (no dev team needed)",
            "The 3 jobs inside your business AI should eat first",
        ],
    },
    "05": {
        "num": "05",
        "pillar": "Continuity",
        "speaker": "Nani Razon",
        "topic": "The Cashflow System na Hindi Matitinag ng Krisis",
        "time_label": "Live right now · May 4, 2026 · 7:00 PM PHT",
        "poster": "nani-razon-webinar.png",
        "ics": "w5.ics",
        "agenda": [
            "The cashflow system that doesn't break when sales dip",
            "How to design continuity without hoarding cash",
            "The numbers to track weekly so you never get blindsided",
        ],
    },
    "06": {
        "num": "06",
        "pillar": "Presence",
        "speaker": "Diana Jane Mitchell",
        "topic": "Paano Ka Makita ng Customers Mo Kahit Walang Ad Budget",
        "time_label": "Live right now · May 7, 2026 · 7:00 PM PHT",
        "poster": "diana-mitchell.png",
        "ics": "w6.ics",
        "agenda": [
            "How to stay visible without spending on ads",
            "The organic content loop that compounds month over month",
            "Where your next 100 customers are already hanging out",
        ],
    },
}


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

    return data.get("rows") or [], {"ok": True, "count": len(data.get("rows") or [])}


def _build_lead_html(speaker: str, agenda: list[str]) -> str:
    bullets = "".join(
        f'<li style="margin:0 0 8px 0; padding:0;">{item}</li>' for item in agenda
    )
    return (
        f"<strong>{speaker} is on-screen right now.</strong> Door's still open — tap the Zoom link below and slide in. "
        f"Here's what you'll unlock in the next ~45 minutes:"
        f'<ul style="margin:14px 0 0 0; padding-left:20px; font-size:15px; line-height:1.6; color:#334155;">{bullets}</ul>'
    )


def _send_push(template: str, webinar: dict, row: dict) -> dict:
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
            "preheader": f"{webinar['speaker']} is on Zoom right now — join in progress.",
            "urgency_label": "LIVE NOW · Zoom door is open",
            "headline": "We're live right now",
            "lead": _build_lead_html(webinar["speaker"], webinar["agenda"]),
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
    subject = f"LIVE NOW — {webinar['speaker']} is on · join in progress"

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


def _run(webinar_num: str) -> dict:
    webinar = WEBINARS.get(webinar_num)
    if not webinar:
        return {"ok": False, "error": f"Unknown webinar: {webinar_num}"}

    try:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Template load failed: {e}"}

    rows, meta = _fetch_registrations()
    if not meta.get("ok"):
        return {"ok": False, "error": "Failed to fetch registrations", "meta": meta}

    seen = set()
    unique_rows = []
    for r in rows:
        e = str(r.get("email") or "").strip().lower()
        if e and e not in seen:
            seen.add(e)
            unique_rows.append(r)

    results = {"sent": 0, "skipped": 0, "failed": 0, "errors": []}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for res in pool.map(lambda r: _send_push(template, webinar, r), unique_rows):
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


class handler(BaseHTTPRequestHandler):  # noqa: N801

    def _authorized(self) -> bool:
        expected = os.environ.get("CRON_SECRET")
        if not expected:
            return True
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {expected}"

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            return _send_json(self, 401, {"error": "unauthorized"})

        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        num = (qs.get("webinar") or ["01"])[0]

        result = _run(num)
        status = 200 if result.get("ok") else 500
        return _send_json(self, status, result)

    def do_POST(self) -> None:  # noqa: N802
        return self.do_GET()
