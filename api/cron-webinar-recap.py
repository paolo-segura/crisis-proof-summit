"""Vercel cron — next-morning recap. Fires at 1 UTC (9 AM PHT) daily.

If yesterday's PHT date matches a scheduled webinar, sends a recap email to
the unified recipient list (webinar regs ∪ BU ticket buyers). Copy thanks
them for joining last night, teases the NEXT upcoming webinar in the series,
and plugs the May 9 Business Unlocked seminar.

For the final webinar (W06), there's no next-up block — the email pivots
entirely to a May 9 closing push.
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
    BASE_URL, MAIN_EVENT_URL, WEBINARS, authorized, brevo_config,
    fetch_all_recipients, get_webinar, get_webinar_by_date, read_template,
    render, send_brevo, unsubscribe_url, within_cron_window,
)

# Scheduled for 01:00 UTC (9 AM PHT).
EXPECTED_HOUR_UTC = 1
EXPECTED_MIN_UTC = 0


def _pht_yesterday() -> date:
    return (datetime.now(tz=timezone.utc) + timedelta(hours=8) - timedelta(days=1)).date()


def _next_webinar_after(num: str) -> dict | None:
    try:
        idx = next(i for i, w in enumerate(WEBINARS) if w["num"] == num)
    except StopIteration:
        return None
    if idx + 1 >= len(WEBINARS):
        return None
    return WEBINARS[idx + 1]


def _next_up_block(next_w: dict | None) -> str:
    if not next_w:
        # Series finale — no next webinar.
        return (
            '<div style="padding:22px 24px; background-color:#0F1B2E; border-radius:14px;">'
            '<p style="margin:0 0 6px 0; font-size:11px; font-weight:700; letter-spacing:2.4px; color:#F59E0B; text-transform:uppercase;">'
            'Series complete</p>'
            '<h3 style="margin:0 0 8px 0; font-family:\'Lora\', Georgia, serif; font-weight:500; font-size:20px; color:#FFFFFF;">'
            'You\'ve unlocked all 4 pillars.</h3>'
            '<p style="margin:0; font-size:15px; line-height:1.55; color:#CBD5E1;">'
            'The free series is done — but the playbook is built on May 9, in Pasay, '
            'with all 5 specialists in the room. That\'s the day this stops being theory.</p>'
            '</div>'
        )
    return (
        '<div style="padding:22px 24px; background-color:#F8FAFC; border-radius:14px; border:1px solid #E7E5E4;">'
        '<p style="margin:0 0 6px 0; font-size:11px; font-weight:700; letter-spacing:2.4px; color:#115E59; text-transform:uppercase;">'
        f'Up next · Webinar {next_w["num"]} · {next_w["pillar"]}</p>'
        '<h3 style="margin:0 0 6px 0; font-family:\'Lora\', Georgia, serif; font-weight:500; font-size:20px; color:#0F1B2E;">'
        f'{next_w["speaker"]}</h3>'
        '<p style="margin:0 0 8px 0; font-size:14px; line-height:1.5; color:#334155; font-weight:500;">'
        f'{next_w["topic"]}</p>'
        '<p style="margin:0; font-size:13px; font-weight:700; color:#64748B; letter-spacing:1px; text-transform:uppercase;">'
        f'{next_w["date_label"]}, 2026 · {next_w["time_hour_pht"]}:00 PM PHT</p>'
        '</div>'
    )


def _send_one(template: str, recap: dict, next_w: dict | None, row: dict,
              api_key: str, sender_email: str, sender_name: str) -> dict:
    email = row["email"]
    name = row.get("name") or ""
    first = name.split()[0].title() if name else "there"

    if next_w:
        recap_body = (
            f"Last night, <strong>{recap['speaker']}</strong> walked us through "
            f"<strong>{recap['pillar'].lower()}</strong> — the part of the puzzle "
            f"most PH operators skip until they're forced to. "
            f"Whether you caught it live or missed it, the next session picks up "
            f"exactly where this one left off."
        )
        eyebrow = f"Thanks for joining · {recap['pillar']} is in the bag"
    else:
        recap_body = (
            f"Last night, <strong>{recap['speaker']}</strong> closed out the series. "
            f"Six webinars. Four pillars. One framework that you now know better than "
            f"95% of Filipino business owners. The last move is putting it into practice."
        )
        eyebrow = "Series finale · You have the framework"

    html = render(template, {
        "name": first,
        "preheader": (
            f"Next up: {next_w['speaker']} on {next_w['date_label']}."
            if next_w else
            "The framework is yours. May 9 is where it becomes a plan."
        ),
        "eyebrow": eyebrow,
        "recap_num": recap["num"],
        "recap_pillar": recap["pillar"],
        "recap_headline": (
            f"Nice one" if next_w else "You unlocked all four"
        ),
        "recap_body": recap_body,
        "next_up_block": _next_up_block(next_w),
        "main_event_url": MAIN_EVENT_URL,
        "unsubscribe_url": unsubscribe_url(email),
    })

    if next_w:
        subject = f"Next up: {next_w['speaker']} on {next_w['date_label']} · {next_w['pillar']}"
    else:
        subject = f"Series done — May 9 is where it becomes a plan"

    status, body = send_brevo(
        api_key, sender_email, sender_name, email, name, subject, html,
    )
    return {"ok": 200 <= status < 300, "status": status, "email": email,
            "err": body[:150] if not (200 <= status < 300) else ""}


def _run(force_num: str | None = None, dry: bool = False) -> dict:
    if force_num:
        recap = get_webinar(force_num)
        if not recap:
            return {"ok": False, "error": f"unknown webinar: {force_num}"}
    else:
        recap = get_webinar_by_date(_pht_yesterday().isoformat())
        if not recap:
            return {"ok": True, "skipped": True,
                    "reason": f"no webinar yesterday (PHT={_pht_yesterday().isoformat()})"}

    next_w = _next_webinar_after(recap["num"])
    template = read_template("webinar-recap.html")
    api_key, sender_email, sender_name = brevo_config()
    if not api_key and not dry:
        return {"ok": False, "error": "BREVO_API_KEY not set"}

    recipients, meta = fetch_all_recipients()
    if not recipients:
        return {"ok": False, "error": "no recipients", "meta": meta}

    if dry:
        return {
            "ok": True, "dry": True,
            "recap_of": f"W{recap['num']} — {recap['speaker']}",
            "next_up": f"W{next_w['num']} — {next_w['speaker']}" if next_w else "finale",
            "would_send_to": meta,
        }

    stats = {"sent": 0, "failed": 0, "errors": []}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for res in pool.map(
            lambda r: _send_one(template, recap, next_w, r, api_key, sender_email, sender_name),
            recipients,
        ):
            if res["ok"]:
                stats["sent"] += 1
            else:
                stats["failed"] += 1
                if len(stats["errors"]) < 10:
                    stats["errors"].append(res)

    return {
        "ok": True,
        "recap_of": f"W{recap['num']} — {recap['speaker']}",
        "next_up": f"W{next_w['num']} — {next_w['speaker']}" if next_w else "finale",
        "recipients": meta,
        **stats,
    }


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
