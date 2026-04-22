"""Vercel cron — 24-hour-before reminder. Fires at 11 UTC (7 PM PHT) daily.

If tomorrow's PHT date matches a scheduled webinar, sends the "Tomorrow at
7 PM — {speaker}" reminder to the unified recipient list (webinar regs ∪
BU buyers). No-op on other days.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _webinar_common import (  # noqa: E402
    BASE_URL, MAIN_EVENT_URL, ZOOM_URL, agenda_html, authorized,
    brevo_config, fetch_all_recipients, get_webinar, get_webinar_by_date,
    read_template, render, send_brevo, unsubscribe_url,
)


def _pht_tomorrow() -> date:
    return (datetime.now(tz=timezone.utc) + timedelta(hours=8) + timedelta(days=1)).date()


def _send_one(template: str, w: dict, row: dict, api_key: str,
              sender_email: str, sender_name: str) -> dict:
    email = row["email"]
    name = row.get("name") or ""
    first = name.split()[0].title() if name else "there"

    lead = (
        f"Quick heads-up — <strong>{w['speaker']}</strong> is on Zoom "
        f"<strong>tomorrow at {w['time_hour_pht']} PM PHT</strong>. "
        f"Same link you've been using. Here's what you're walking into:"
        + agenda_html(w["agenda"])
        + f'<p style="margin:14px 0 0 0; font-size:14px; color:#64748B;">'
          f'Block the calendar now — sessions run ~60 minutes and the best '
          f'questions always come from people who showed up live.</p>'
    )

    html = render(template, {
        "name": first,
        "preheader": f"Tomorrow {w['date_label']} — {w['speaker']} on {w['topic']}.",
        "urgency_label": "Tomorrow · Block your calendar",
        "headline": f"Tomorrow at {w['time_hour_pht']} PM",
        "lead": lead,
        "webinar_num": w["num"],
        "pillar": w["pillar"],
        "speaker": w["speaker"],
        "topic": w["topic"],
        "time_label": f"Tomorrow · {w['date_label']}, 2026 · {w['time_hour_pht']}:00 PM PHT",
        "poster_url": f"{BASE_URL}/assets/images/speakers/{w['poster']}",
        "zoom_url": ZOOM_URL,
        "ics_url": f"{BASE_URL}/cal/{w['ics']}",
        "main_event_url": MAIN_EVENT_URL,
        "unsubscribe_url": unsubscribe_url(email),
    })

    status, body = send_brevo(
        api_key, sender_email, sender_name, email, name,
        f"Tomorrow {w['date_label']} — {w['speaker']} on {w['pillar']}", html,
    )
    return {"ok": 200 <= status < 300, "status": status, "email": email,
            "err": body[:150] if not (200 <= status < 300) else ""}


def _run(force_num: str | None = None) -> dict:
    if force_num:
        w = get_webinar(force_num)
        if not w:
            return {"ok": False, "error": f"unknown webinar: {force_num}"}
    else:
        w = get_webinar_by_date(_pht_tomorrow().isoformat())
        if not w:
            return {"ok": True, "skipped": True,
                    "reason": f"no webinar tomorrow (PHT={_pht_tomorrow().isoformat()})"}

    template = read_template("webinar-reminder.html")
    api_key, sender_email, sender_name = brevo_config()
    if not api_key:
        return {"ok": False, "error": "BREVO_API_KEY not set"}

    recipients, meta = fetch_all_recipients()
    if not recipients:
        return {"ok": False, "error": "no recipients", "meta": meta}

    stats = {"sent": 0, "failed": 0, "errors": []}
    with ThreadPoolExecutor(max_workers=8) as pool:
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
        force = (qs.get("webinar") or [None])[0]
        result = _run(force_num=force)
        self._json(200 if result.get("ok") else 500, result)

    def do_POST(self) -> None:  # noqa: N802
        return self.do_GET()
