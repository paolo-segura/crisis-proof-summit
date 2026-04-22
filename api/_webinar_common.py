"""Shared helpers for all webinar-email endpoints.

Unifies recipient fetch (Apps Script sheet ∪ Supabase BU buyers, deduped by
email), webinar metadata, and template rendering so every send path
(confirmation, 24h, 30min, day-of, live-now, replay) uses the same list.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "https://exponential-university.live"
MAIN_EVENT_URL = "https://www.exponential-university.live/the-new-business-normal"
ZOOM_URL = "https://us06web.zoom.us/j/82900398611?pwd=iP8tYUqpXBY5Nzo4vPm4EUFWbDn4wF.1"

DEFAULT_SENDER_EMAIL = "success@exponential-university.live"
DEFAULT_SENDER_NAME = "Business Unlocked"

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "emails"

# Single source of truth for the 6-webinar schedule + per-session agenda copy.
# dates are the PHT calendar day; time_hour_pht is the 24h PHT start time.
WEBINARS = [
    {
        "num": "01",
        "date_iso": "2026-04-22",
        "time_hour_pht": 20,
        "pillar": "Overview",
        "speaker": "Migs Flores",
        "speaker_first": "Migs",
        "topic": "Why Filipino Businesses Are Closing — And The 4 Unlocks That Keep Them Open",
        "date_label": "Wed · Apr 22",
        "poster": "migs-flores-webinar.png",
        "ics": "w1.ics",
        "agenda": [
            "Why \"successful\" PH businesses are quietly closing in 2026",
            "The 4 Unlocks that keep cashflow moving when markets go sideways",
            "The mindset shift separating owners who survive from owners who scale",
            "A preview of the 5 specialists coming in Webinars 2–6",
        ],
    },
    {
        "num": "02",
        "date_iso": "2026-04-25",
        "time_hour_pht": 19,
        "pillar": "Flexibility",
        "speaker": "Charlie Gengos",
        "speaker_first": "Charlie",
        "topic": "3 Ways to Sell Kahit Bumagsak ang Isang Revenue Stream",
        "date_label": "Sat · Apr 25",
        "poster": "charlie-gengos-webinar.png",
        "ics": "w2.ics",
        "agenda": [
            "3 revenue plays you can launch in 30 days without new staff",
            "How to stress-test your current revenue stream this week",
            "The flexibility playbook top PH operators are quietly running",
        ],
    },
    {
        "num": "03",
        "date_iso": "2026-04-29",
        "time_hour_pht": 19,
        "pillar": "Final Unlock",
        "speaker": "Russ Juson",
        "speaker_first": "Russ",
        "topic": "Your 72-Hour Crisis-Proof Action Plan — integrating the 4 Pillars",
        "date_label": "Wed · Apr 29",
        "poster": "russ-juson.png",
        "ics": "w3.ics",
        "agenda": [
            "How to integrate all 4 pillars into one 72-hour action plan",
            "The sequencing that saves you from rebuilding the wrong thing first",
            "What to do in your business by Monday morning",
        ],
    },
    {
        "num": "04",
        "date_iso": "2026-05-02",
        "time_hour_pht": 19,
        "pillar": "Adaptability",
        "speaker": "Jay Jazmines",
        "speaker_first": "Jay",
        "topic": "Using AI to Future-Proof Your Business in 2026",
        "date_label": "Sat · May 2",
        "poster": "jay-jazmines-webinar.png",
        "ics": "w4.ics",
        "agenda": [
            "Which AI tools actually move the needle for PH SMEs",
            "Workflows you can automate this week (no dev team needed)",
            "The 3 jobs inside your business AI should eat first",
        ],
    },
    {
        "num": "05",
        "date_iso": "2026-05-04",
        "time_hour_pht": 19,
        "pillar": "Continuity",
        "speaker": "Nani Razon",
        "speaker_first": "Nani",
        "topic": "The Cashflow System na Hindi Matitinag ng Krisis",
        "date_label": "Mon · May 4",
        "poster": "nani-razon-webinar.png",
        "ics": "w5.ics",
        "agenda": [
            "The cashflow system that doesn't break when sales dip",
            "How to design continuity without hoarding cash",
            "The numbers to track weekly so you never get blindsided",
        ],
    },
    {
        "num": "06",
        "date_iso": "2026-05-07",
        "time_hour_pht": 19,
        "pillar": "Presence",
        "speaker": "Diana Jane Mitchell",
        "speaker_first": "Diana",
        "topic": "Paano Ka Makita ng Customers Mo Kahit Walang Ad Budget",
        "date_label": "Thu · May 7",
        "poster": "diana-mitchell.png",
        "ics": "w6.ics",
        "agenda": [
            "How to stay visible without spending on ads",
            "The organic content loop that compounds month over month",
            "Where your next 100 customers are already hanging out",
        ],
    },
]


def get_webinar(num: str) -> dict | None:
    for w in WEBINARS:
        if w["num"] == num:
            return w
    return None


def get_webinar_by_date(date_iso: str) -> dict | None:
    for w in WEBINARS:
        if w["date_iso"] == date_iso:
            return w
    return None


# --- HTTP helpers -----------------------------------------------------------
def http_get(url: str, timeout: int = 20, headers: dict | None = None) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 500, str(e)


def http_post_json(url: str, payload: dict, headers: dict, timeout: int = 15) -> tuple[int, str]:
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


# --- Recipient fetch --------------------------------------------------------
def fetch_webinar_regs() -> list[dict]:
    """Free-series registrants from the Apps Script sheet. Filtered to
    marketing_consent=TRUE. Returns dicts with email, name, source='webinar'."""
    url = os.environ.get("SHEETS_WEBHOOK_URL")
    secret = os.environ.get("SHEETS_READ_SECRET")
    if not url or not secret:
        return []

    full = url + ("&" if "?" in url else "?") + "action=list&secret=" + urllib.parse.quote(secret)
    status, body = http_get(full)
    if not (200 <= status < 300):
        return []
    try:
        data = json.loads(body)
    except Exception:
        return []
    if not data.get("ok"):
        return []

    out: list[dict] = []
    for r in (data.get("rows") or []):
        email = str(r.get("email") or "").strip().lower()
        name = str(r.get("name") or "").strip()
        consent = str(r.get("marketing_consent") or "").upper() == "TRUE"
        if email and "@" in email and consent:
            out.append({"email": email, "name": name, "source": "webinar"})
    return out


def fetch_bu_buyers() -> list[dict]:
    """Paid BU-seminar ticket buyers from Supabase. Returns dicts with
    email, name (full_name), source='bu_buyer'. Silently returns [] if
    Supabase credentials are missing or the call fails — the webinar send
    should still succeed on sheet-only data."""
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not base or not key:
        return []

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    out: list[dict] = []
    offset = 0
    page_size = 1000
    while True:
        url = (
            f"{base}/rest/v1/new_business_normal_purchases"
            f"?select=email,full_name,payment_status"
            f"&payment_status=in.(PAID,FULLY_PAID)"
            f"&limit={page_size}&offset={offset}"
        )
        status, body = http_get(url, headers=headers, timeout=30)
        if not (200 <= status < 300):
            break
        try:
            page = json.loads(body)
        except Exception:
            break
        if not page:
            break
        for row in page:
            email = str(row.get("email") or "").strip().lower()
            name = str(row.get("full_name") or "").strip()
            if email and "@" in email:
                out.append({"email": email, "name": name, "source": "bu_buyer"})
        if len(page) < page_size:
            break
        offset += page_size
    return out


def fetch_all_recipients() -> tuple[list[dict], dict]:
    """Union of webinar regs + BU buyers, deduped by email. Webinar regs win
    on name ties (registration form usually captures a better name). Returns
    (recipients, meta) where meta reports source breakdown for logging."""
    regs = fetch_webinar_regs()
    buyers = fetch_bu_buyers()

    by_email: dict[str, dict] = {}
    for r in regs + buyers:
        em = r["email"]
        if em not in by_email:
            by_email[em] = r
    unique = list(by_email.values())

    sources = {"webinar": 0, "bu_buyer": 0}
    for r in unique:
        sources[r["source"]] = sources.get(r["source"], 0) + 1
    meta = {
        "total_rows": len(regs) + len(buyers),
        "webinar_rows": len(regs),
        "bu_buyer_rows": len(buyers),
        "unique": len(unique),
        "sources": sources,
    }
    return unique, meta


# --- Template rendering -----------------------------------------------------
def render(template: str, vars: dict) -> str:
    out = template
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def unsubscribe_url(email: str) -> str:
    return (
        "https://exponential-university.live/free/unsubscribe?email="
        + urllib.parse.quote(email)
    )


def agenda_html(agenda: list[str]) -> str:
    bullets = "".join(
        f'<li style="margin:0 0 8px 0; padding:0;">{item}</li>' for item in agenda
    )
    return (
        f'<ul style="margin:14px 0 0 0; padding-left:20px; font-size:15px; line-height:1.6; color:#334155;">'
        f'{bullets}</ul>'
    )


def read_template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


# --- Brevo send -------------------------------------------------------------
def send_brevo(api_key: str, sender_email: str, sender_name: str,
               to_email: str, to_name: str, subject: str, html: str) -> tuple[int, str]:
    return http_post_json(
        "https://api.brevo.com/v3/smtp/email",
        {
            "sender": {"email": sender_email, "name": sender_name},
            "to": [{"email": to_email, "name": to_name or to_email}],
            "subject": subject,
            "htmlContent": html,
        },
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )


def brevo_config() -> tuple[str, str, str]:
    api_key = os.environ.get("BREVO_API_KEY", "")
    sender_email = os.environ.get("BREVO_SENDER_EMAIL", DEFAULT_SENDER_EMAIL)
    sender_name = os.environ.get("BREVO_SENDER_NAME", DEFAULT_SENDER_NAME)
    return api_key, sender_email, sender_name


def authorized(headers, env_key: str = "CRON_SECRET") -> bool:
    """Bearer-token check against env_key. If env is unset, allow (dev)."""
    expected = os.environ.get(env_key)
    if not expected:
        return True
    auth = headers.get("Authorization", "") if hasattr(headers, "get") else ""
    return auth == f"Bearer {expected}"
