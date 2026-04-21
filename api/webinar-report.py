"""Admin endpoint: webinar funnel attendees report.

GET /api/webinar-report
Auth: Authorization: Bearer <ADMIN_PASSWORD>

Reads registrations from the Apps Script list endpoint and returns
aggregated + filtered data for the admin dashboard's webinar section.

Response:
  { ok, total, by_day: [{date, count}], rows: [{timestamp, name, email, phone}] }

Env:
  ADMIN_PASSWORD       Bearer token for access (reuses existing value)
  SHEETS_WEBHOOK_URL   Apps Script /exec URL (same one used for writes/cron)
  SHEETS_READ_SECRET   matches the Script Property in Apps Script
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
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

    return data.get("rows") or [], {"ok": True}


def _day_key(ts) -> str:
    """Best-effort YYYY-MM-DD extraction from Apps Script timestamp strings."""
    if not ts:
        return ""
    s = str(ts)
    # Apps Script serialises JS Dates as ISO-like: "2026-04-20T17:02:03.000Z"
    # or sometimes "Mon Apr 20 2026 17:02:03 GMT+0800 (Philippine Standard Time)"
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    # Fallback — just return the raw string, group by its first 10 chars
    return s[:10]


class handler(BaseHTTPRequestHandler):  # noqa: N801

    def _authorized(self) -> bool:
        expected = os.environ.get("ADMIN_PASSWORD", "")
        if not expected:
            return False
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        return auth[len("Bearer "):] == expected

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            return _send_json(self, 401, {"ok": False, "error": "Invalid password"})

        rows, meta = _fetch_registrations()
        if not meta.get("ok"):
            return _send_json(self, 502, {"ok": False, "error": "Failed to fetch registrations", "meta": meta})

        # Filter + slim rows: only keep the 4 fields the dashboard displays.
        slim = []
        by_day_counts: dict[str, int] = {}
        seen_emails = set()

        for r in rows:
            email = str(r.get("email") or "").strip().lower()
            if not email:
                continue
            if email in seen_emails:
                # Dedupe — same email registered twice counts once
                continue
            seen_emails.add(email)

            ts = r.get("timestamp") or ""
            day = _day_key(ts)
            by_day_counts[day] = by_day_counts.get(day, 0) + 1

            slim.append({
                "timestamp": str(ts),
                "name": str(r.get("name") or ""),
                "email": email,
                "phone": str(r.get("phone") or ""),
            })

        # Sort rows newest first
        slim.sort(key=lambda x: x["timestamp"], reverse=True)

        # by_day sorted oldest → newest so charts draw left-to-right chronologically
        by_day = [
            {"date": d, "count": c}
            for d, c in sorted(by_day_counts.items())
            if d
        ]

        return _send_json(self, 200, {
            "ok": True,
            "total": len(slim),
            "by_day": by_day,
            "rows": slim,
        })
