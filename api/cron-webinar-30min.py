"""Vercel cron — 30-minutes-before final push. Fires at 10:30 UTC (6:30 PM
PHT) daily.

If today's PHT date matches a scheduled webinar, sends the "Starting in 30
minutes — here's your Zoom" push to the unified recipient list. No-op on
non-webinar days.

Note: W01 is at 8 PM PHT (30 min before = 7:30 PM PHT / 11:30 UTC). This
cron fires at 10:30 UTC which is 6:30 PM PHT — correct for W02–W06 (all
7 PM PHT). W01 already happened so the misalignment is moot.
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
    read_template, render, send_brevo, unsubscribe_url, within_cron_window,
)

# Scheduled for 10:30 UTC (6:30 PM PHT).
EXPECTED_HOUR_UTC = 10
EXPECTED_MIN_UTC = 30


def _pht_today() -> date:
    return (datetime.now(tz=timezone.utc) + timedelta(hours=8)).date()


def _send_one(template: str, w: dict, row: dict, api_key: str,
              sender_email: str, sender_name: str) -> dict:
    email = row["email"]
    name = row.get("name") or ""
    first = name.split()[0].title() if name else "there"

    lead = (
        f"<strong>{w['speaker']}</strong> is opening the Zoom room in 30 minutes. "
        f"Grab a glass of water, close the other tabs, and save the link below. "
        f"Here's what you'll walk out with tonight:"
        + agenda_html(w["agenda"])
    )

    html = render(template, {
        "name": first,
        "preheader": f"30 minutes until {w['speaker']} goes live.",
        "urgency_label": "Starting in 30 min · Zoom link inside",
        "headline": "Starting in 30 minutes",
        "lead": lead,
        "webinar_num": w["num"],
        "pillar": w["pillar"],
        "speaker": w["speaker"],
        "topic": w["topic"],
        "time_label": f"Tonight · {w['date_label']}, 2026 · {w['time_hour_pht']}:00 PM PHT",
        "poster_url": f"{BASE_URL}/assets/images/speakers/{w['poster']}",
        "zoom_url": ZOOM_URL,
        "ics_url": f"{BASE_URL}/cal/{w['ics']}",
        "main_event_url": MAIN_EVENT_URL,
        "unsubscribe_url": unsubscribe_url(email),
    })

    status, body = send_brevo(
        api_key, sender_email, sender_name, email, name,
        f"30 min — {w['speaker']} goes live tonight", html,
    )
    return {"ok": 200 <= status < 300, "status": status, "email": email,
            "err": body[:150] if not (200 <= status < 300) else ""}


def _run(force_num: str | None = None, dry: bool = False) -> dict:
    if force_num:
        w = get_webinar(force_num)
        if not w:
            return {"ok": False, "error": f"unknown webinar: {force_num}"}
    else:
        w = get_webinar_by_date(_pht_today().isoformat())
        if not w:
            return {"ok": True, "skipped": True,
                    "reason": f"no webinar today (PHT={_pht_today().isoformat()})"}

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
        force_num = (qs.get("webinar") or [None])[0]
        force_flag = (qs.get("force") or ["0"])[0] == "1"
        dry = (qs.get("dry") or ["0"])[0] == "1"

        if not force_flag and not dry and not within_cron_window(EXPECTED_HOUR_UTC, EXPECTED_MIN_UTC):
            return self._json(200, {
                "ok": True, "skipped": True,
                "reason": (
                    f"outside cron window ({EXPECTED_HOUR_UTC:02d}:{EXPECTED_MIN_UTC:02d} UTC ±10min). "
                    "Add &force=1 to override or &dry=1 to preview."
                ),
            })

        result = _run(force_num=force_num, dry=dry)
        self._json(200 if result.get("ok") else 500, result)

    def do_POST(self) -> None:  # noqa: N802
        return self.do_GET()
