"""Manual trigger — "we're live now" blast, fired the moment Zoom opens.

Differs from cron-webinar-reminders.py (which pre-announces "Starts in 1
hour"): copy reflects "we're live now" + agenda bullets so latecomers know
exactly what they'll unlock if they slide in mid-session.

Pulls the unified recipient list (free-series regs ∪ BU ticket buyers).
"""
from __future__ import annotations

import os
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _webinar_common import (  # noqa: E402
    BASE_URL, MAIN_EVENT_URL, ZOOM_URL, agenda_html, authorized,
    brevo_config, fetch_all_recipients, get_webinar, read_template,
    render, send_brevo, unsubscribe_url,
)


def _send_one(template: str, w: dict, row: dict, api_key: str,
              sender_email: str, sender_name: str) -> dict:
    email = row["email"]
    name = row.get("name") or ""
    first = name.split()[0].title() if name else "there"

    lead = (
        f"<strong>{w['speaker']} is on-screen right now.</strong> "
        f"Door's still open — tap the Zoom link below and slide in. "
        f"Here's what you'll unlock in the next ~45 minutes:"
        + agenda_html(w["agenda"])
    )

    html = render(template, {
        "name": first,
        "preheader": f"{w['speaker']} is on Zoom right now — join in progress.",
        "urgency_label": "LIVE NOW · Zoom door is open",
        "headline": "We're live right now",
        "lead": lead,
        "webinar_num": w["num"],
        "pillar": w["pillar"],
        "speaker": w["speaker"],
        "topic": w["topic"],
        "time_label": f"Live right now · {w['date_label']}, 2026 · {w['time_hour_pht']}:00 PM PHT",
        "poster_url": f"{BASE_URL}/assets/images/speakers/{w['poster']}",
        "zoom_url": ZOOM_URL,
        "ics_url": f"{BASE_URL}/cal/{w['ics']}",
        "main_event_url": MAIN_EVENT_URL,
        "unsubscribe_url": unsubscribe_url(email),
    })

    status, body = send_brevo(
        api_key, sender_email, sender_name, email, name,
        f"LIVE NOW — {w['speaker']} is on · join in progress", html,
    )
    return {"ok": 200 <= status < 300, "status": status, "email": email,
            "err": body[:150] if not (200 <= status < 300) else ""}


def _run(num: str, dry: bool = False) -> dict:
    w = get_webinar(num)
    if not w:
        return {"ok": False, "error": f"unknown webinar: {num}"}

    template = read_template("webinar-reminder.html")
    api_key, sender_email, sender_name = brevo_config()
    if not api_key and not dry:
        return {"ok": False, "error": "BREVO_API_KEY not set"}

    recipients, meta = fetch_all_recipients()
    if not recipients:
        return {"ok": False, "error": "no recipients", "meta": meta}

    if dry:
        return {"ok": True, "dry": True, "webinar": f"W{w['num']} — {w['speaker']}",
                "would_send_to": meta}

    stats = {"sent": 0, "failed": 0, "errors": []}
    with ThreadPoolExecutor(max_workers=12) as pool:
        for res in pool.map(
            lambda r: _send_one(template, w, r, api_key, sender_email, sender_name),
            recipients,
        ):
            if res["ok"]:
                stats["sent"] += 1
            else:
                stats["failed"] += 1
                if len(stats["errors"]) < 10:
                    stats["errors"].append(res)

    return {"ok": True, "webinar": f"W{w['num']} — {w['speaker']}",
            "recipients": meta, **stats}


class handler(BaseHTTPRequestHandler):  # noqa: N801

    def _json(self, status: int, payload: dict) -> None:
        import json
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if not authorized(self.headers):
            return self._json(401, {"error": "unauthorized"})

        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        num = (qs.get("webinar") or ["01"])[0]
        dry = (qs.get("dry") or ["0"])[0] == "1"
        result = _run(num, dry=dry)
        self._json(200 if result.get("ok") else 500, result)

    def do_POST(self) -> None:  # noqa: N802
        return self.do_GET()
