"""
/api/send-nurture — Vercel cron handler module.

Daily at 9AM Manila (1AM UTC):
  1. Fetch all paid customers from new_business_normal_purchases
  2. For each customer, determine which emails are due based on:
     - after_paid:   now >= paid_at + offset_days
     - before_event: now >= event_date - offset_days
     - after_event:  now >= event_date + offset_days
  3. Skip any (email, email_number) pair already in new_business_normal_email_log
  4. Load HTML template from disk, render with personalized unsubscribe URL
  5. Send via Brevo Transactional API
  6. Log the send to new_business_normal_email_log (even in dry_run mode)

Templates stay on disk — no inline HTML in this module.
"""

import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from urllib.parse import quote


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVENT_DATE = datetime(2026, 5, 9, 0, 0, tzinfo=timezone.utc)

PURCHASES_TABLE = "new_business_normal_purchases"
EMAIL_LOG_TABLE = "new_business_normal_email_log"

EMAILS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "emails")

UNSUBSCRIBE_URL_BASE = "https://businessunlocked.ph/unsubscribe"

SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "success@exponential-university.live")
SENDER_NAME = os.environ.get("SENDER_NAME", "Business Unlocked")

BREVO_TRANSACTIONAL_URL = "https://api.brevo.com/v3/smtp/email"


# ---------------------------------------------------------------------------
# Email schedule
# ---------------------------------------------------------------------------

EMAIL_SCHEDULE = [
    {"num": 1, "type": "after_paid",   "offset_days": 0,  "template": "nurture-1-problem.html",    "subject": "Congratulations — you're in. Here's what happens next."},
    {"num": 2, "type": "after_paid",   "offset_days": 2,  "template": "nurture-2-pillars.html",     "subject": "The 5 pillars of a crisis-proof business"},
    {"num": 3, "type": "after_paid",   "offset_days": 5,  "template": "nurture-3-social-proof.html","subject": "How others turned crisis into cashflow"},
    {"num": 4, "type": "after_paid",   "offset_days": 10, "template": "nurture-4-vip-spotlight.html","subject": "A closer look at what VIP unlocks"},
    {"num": 5, "type": "after_paid",   "offset_days": 15, "template": "nurture-5-urgency.html",     "subject": "Final countdown before May 9"},
    {"num": 6, "type": "before_event", "offset_days": 3,  "template": "countdown-3days.html",       "subject": "3 days to Business Unlocked — here's what to prep"},
    {"num": 7, "type": "before_event", "offset_days": 1,  "template": "countdown-1day.html",        "subject": "Tomorrow: Business Unlocked"},
    {"num": 8, "type": "before_event", "offset_days": 0,  "template": "countdown-dayof.html",       "subject": "We start in a few hours. See you at PTTC."},
    {"num": 9, "type": "after_event",  "offset_days": 1,  "template": "post-event.html",            "subject": "Thank you — your Cashflow Blueprint starts now"},
]


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

def load_template(template_filename):
    """Read HTML template from EMAILS_DIR. Raises FileNotFoundError if missing."""
    path = os.path.join(EMAILS_DIR, template_filename)
    path = os.path.normpath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Template not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def render_template(html, email_address):
    """Replace {{ unsubscribe }} with a personalized URL-encoded unsubscribe link."""
    encoded = quote(email_address, safe="")
    unsubscribe_url = f"{UNSUBSCRIBE_URL_BASE}?email={encoded}"
    return html.replace("{{ unsubscribe }}", unsubscribe_url)


# ---------------------------------------------------------------------------
# Scheduling logic
# ---------------------------------------------------------------------------

def parse_paid_at(s):
    """
    Parse ISO timestamp string from Supabase to a UTC-aware datetime.
    Returns None on failure — callers skip customers with unparseable timestamps.
    """
    if not s:
        return None
    # Supabase returns ISO 8601, e.g. "2026-04-01T10:23:45+00:00" or "...Z"
    s = s.strip()
    # Normalize Z -> +00:00 for fromisoformat compatibility
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        # Ensure UTC — Supabase timestamptz always comes with offset
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def determine_due_emails(paid_at, now, event_date):
    """
    Return a sorted list of email `num` values due to be sent as of `now`.

    Rules:
      after_paid:   due if now >= paid_at + timedelta(days=offset_days)
      before_event: due if now >= event_date - timedelta(days=offset_days)
                    (offset=3 → due on May 6 00:00 UTC or later)
      after_event:  due if now >= event_date + timedelta(days=offset_days)
    """
    due = []
    for entry in EMAIL_SCHEDULE:
        etype = entry["type"]
        offset = entry["offset_days"]
        num = entry["num"]

        if etype == "after_paid":
            if now >= paid_at + timedelta(days=offset):
                due.append(num)
        elif etype == "before_event":
            if now >= event_date - timedelta(days=offset):
                due.append(num)
        elif etype == "after_event":
            if now >= event_date + timedelta(days=offset):
                due.append(num)

    return sorted(due)


# ---------------------------------------------------------------------------
# Brevo payload + send
# ---------------------------------------------------------------------------

def build_brevo_send_payload(to_email, subject, html_body, sender_name, sender_email):
    """Build the JSON dict for POST to Brevo Transactional API."""
    return {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_body,
        "replyTo": {"email": sender_email},
    }


def brevo_send_email(payload, api_key):
    """
    POST payload to Brevo Transactional API.
    Returns messageId string on success.
    Raises RuntimeError with response body on HTTP error.
    """
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BREVO_TRANSACTIONAL_URL,
        data=body,
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("messageId", "")
    except urllib.error.HTTPError as exc:
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        raise RuntimeError(f"Brevo API error {exc.code}: {body_text[:500]}") from exc


# ---------------------------------------------------------------------------
# Supabase helpers (stdlib only — matches abandoned_cart.py pattern)
# ---------------------------------------------------------------------------

def _supabase_env():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    return url.rstrip("/"), key


def _supabase_request(method, path, body=None, extra_headers=None):
    """Generic PostgREST request. Returns parsed JSON or [] on empty body."""
    supabase_url, key = _supabase_env()
    url = f"{supabase_url}/rest/v1/{path.lstrip('/')}"

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("apikey", key)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    if extra_headers:
        for k, v in extra_headers.items():
            req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as exc:
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        snippet = body_text[:500]
        raise RuntimeError(
            f"Supabase {method} {path.split('?')[0]} failed: "
            f"{exc.code} {exc.reason} - {snippet}"
        ) from exc


def supabase_fetch_paid_customers(min_paid_at_iso):
    """
    Fetch paid customers from purchases table.
    Filters by payment_status IN ('PAID', 'FULLY_PAID').
    If min_paid_at_iso is provided, also filters paid_at >= that value.
    Returns list of dicts with keys: email, full_name, paid_at.
    """
    path = (
        f"{PURCHASES_TABLE}"
        f"?select=email,full_name,paid_at"
        f"&payment_status=in.(PAID,FULLY_PAID)"
    )
    if min_paid_at_iso:
        path += f"&paid_at=gte.{quote(min_paid_at_iso, safe='')}"
    path += "&order=paid_at.asc"
    return _supabase_request("GET", path) or []


def supabase_fetch_sent_log():
    """
    Fetch all rows from email log.
    Returns a set of (email_lower, email_number) tuples already sent.
    """
    rows = _supabase_request("GET", f"{EMAIL_LOG_TABLE}?select=email,email_number") or []
    return {(r["email"].lower(), r["email_number"]) for r in rows if r.get("email") and r.get("email_number") is not None}


def supabase_write_log_entry(entry):
    """
    Insert a log row for a sent email.
    entry dict: { email, email_number, subject, message_id, dry_run }
    Handles 409 (UNIQUE violation — already logged) gracefully.
    """
    try:
        _supabase_request(
            "POST",
            EMAIL_LOG_TABLE,
            body=entry,
            extra_headers={"Prefer": "return=minimal"},
        )
    except RuntimeError as exc:
        # 409 Conflict = duplicate (email, email_number) — idempotent, ignore
        if "409" in str(exc):
            return
        raise


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _iso(dt):
    return dt.isoformat()


def _normalize_email(s):
    return (s or "").strip().lower()


def _brevo_api_key():
    key = os.environ.get("BREVO_API_KEY")
    if not key:
        raise EnvironmentError("Missing BREVO_API_KEY")
    return key


def run_send_nurture(
    now=None,
    min_paid_at_iso=None,
    dry_run=False,
    fetch_customers=None,
    fetch_sent_log=None,
    send_fn=None,
    write_log_fn=None,
    load_template_fn=None,
):
    """
    Execute one cron cycle. All I/O is injected for testability.
    Defaults to real Supabase + Brevo functions.

    Returns a summary dict:
      { checked, sent, skipped, errors, details, dry_run }
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if fetch_customers is None:
        fetch_customers = supabase_fetch_paid_customers
    if fetch_sent_log is None:
        fetch_sent_log = supabase_fetch_sent_log
    if send_fn is None:
        api_key = _brevo_api_key()
        def send_fn(payload):  # noqa: E301
            return brevo_send_email(payload, api_key)
    if write_log_fn is None:
        write_log_fn = supabase_write_log_entry
    if load_template_fn is None:
        load_template_fn = load_template

    summary = {
        "checked": 0,
        "sent": 0,
        "skipped": 0,
        "errors": [],
        "details": [],
        "dry_run": dry_run,
    }

    # Fetch sent log once — used to skip duplicates across all customers
    try:
        sent_log = fetch_sent_log()
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append(f"fetch_sent_log: {type(exc).__name__}: {exc}")
        sent_log = set()

    # Fetch customers
    try:
        customers = fetch_customers(min_paid_at_iso)
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append(f"fetch_customers: {type(exc).__name__}: {exc}")
        return summary

    for customer in customers:
        email = _normalize_email(customer.get("email"))
        full_name = customer.get("full_name") or ""
        paid_at_raw = customer.get("paid_at")

        if not email:
            continue

        summary["checked"] += 1

        paid_at = parse_paid_at(paid_at_raw)
        if paid_at is None:
            summary["errors"].append(f"Unparseable paid_at for {email}: {paid_at_raw!r}")
            continue

        due_nums = determine_due_emails(paid_at, now, EVENT_DATE)

        for num in due_nums:
            key = (email, num)
            if key in sent_log:
                summary["skipped"] += 1
                continue

            # Look up schedule entry for this num
            entry = next((e for e in EMAIL_SCHEDULE if e["num"] == num), None)
            if entry is None:
                continue

            try:
                html = load_template_fn(entry["template"])
                rendered = render_template(html, email)
                subject = entry["subject"]

                payload = build_brevo_send_payload(
                    to_email=email,
                    subject=subject,
                    html_body=rendered,
                    sender_name=SENDER_NAME,
                    sender_email=SENDER_EMAIL,
                )

                message_id = ""
                if not dry_run:
                    message_id = send_fn(payload)
                    print(
                        f"[send-nurture] Sent email #{num} to {email} "
                        f"(messageId={message_id})",
                        flush=True,
                    )
                else:
                    print(
                        f"[send-nurture] DRY RUN — would send email #{num} to {email}",
                        flush=True,
                    )

                # Log to DB even in dry_run (with dry_run=true flag)
                log_entry = {
                    "email": email,
                    "email_number": num,
                    "subject": subject,
                    "message_id": message_id or None,
                    "dry_run": dry_run,
                }
                try:
                    write_log_fn(log_entry)
                    sent_log.add(key)  # prevent duplicate sends in same run
                except Exception as log_exc:  # noqa: BLE001
                    # Log write failure is non-fatal — warn but continue
                    summary["errors"].append(
                        f"write_log email={email} num={num}: {type(log_exc).__name__}: {log_exc}"
                    )

                summary["sent"] += 1
                summary["details"].append({
                    "to": email,
                    "name": full_name,
                    "email_num": num,
                    "subject": subject,
                    "message_id": message_id or None,
                    "status": "dry_run" if dry_run else "sent",
                })

            except Exception as exc:  # noqa: BLE001
                summary["errors"].append(
                    f"email #{num} to {email}: {type(exc).__name__}: {exc}"
                )

    return summary
