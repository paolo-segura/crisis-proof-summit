from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse
import urllib.error
from collections import defaultdict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_env(key):
    """Return env var or raise a clear error."""
    value = os.environ.get(key)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return value


def supabase_get(supabase_url, service_key, path):
    """
    Perform a GET request against the Supabase REST API.
    Returns the parsed JSON list, or raises urllib.error.URLError on failure.
    """
    url = f"{supabase_url.rstrip('/')}/rest/v1/{path.lstrip('/')}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("apikey", service_key)
    req.add_header("Authorization", f"Bearer {service_key}")
    req.add_header("Accept", "application/json")
    req.add_header("Prefer", "return=representation")

    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def check_auth(h):
    """
    Validate the Authorization header against ADMIN_PASSWORD.
    Sends a 401 response and returns False if validation fails.
    Returns True if the password matches.
    """
    auth_header = h.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        _send_json(h, 401, {"error": "Missing or malformed Authorization header"})
        return False

    provided = auth_header[len("Bearer "):]
    try:
        admin_password = get_env("ADMIN_PASSWORD")
    except EnvironmentError as exc:
        _send_json(h, 500, {"error": str(exc)})
        return False

    if provided != admin_password:
        _send_json(h, 401, {"error": "Invalid password"})
        return False

    return True


def _send_json(h, status, payload):
    """Write a JSON response with CORS headers."""
    body = json.dumps(payload).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    _add_cors_headers(h)
    h.end_headers()
    h.wfile.write(body)


def _add_cors_headers(h):
    origin = h.headers.get("Origin", "")
    allowed_origin = origin if origin else ""
    h.send_header("Access-Control-Allow-Origin", allowed_origin)
    h.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
    h.send_header("Vary", "Origin")


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

def handle_auth(h, params):
    """GET /api/report?action=auth — password via Authorization: Bearer header"""
    auth_header = h.headers.get("Authorization", "")
    password = auth_header.replace("Bearer ", "", 1) if auth_header.startswith("Bearer ") else ""
    try:
        admin_password = get_env("ADMIN_PASSWORD")
    except EnvironmentError as exc:
        _send_json(h, 500, {"error": str(exc)})
        return

    if password == admin_password:
        _send_json(h, 200, {"authenticated": True})
    else:
        _send_json(h, 401, {"authenticated": False, "error": "Invalid password"})


def handle_summary(h, supabase_url, service_key):
    """GET /api/report?action=summary"""
    if not check_auth(h):
        return

    try:
        visits = supabase_get(supabase_url, service_key, "page_visits?select=id")
        clicks = supabase_get(supabase_url, service_key, "clicks?select=id")
        sales = supabase_get(
            supabase_url, service_key,
            "sales?select=id,amount&payment_status=eq.paid"
        )
    except urllib.error.URLError as exc:
        _send_json(h, 502, {"error": f"Supabase request failed: {exc}"})
        return

    total_visits = len(visits)
    total_clicks = len(clicks)
    total_sales = len(sales)
    total_revenue = sum(row.get("amount", 0) or 0 for row in sales)
    conversion_rate = round((total_sales / total_visits) * 100, 2) if total_visits else 0

    _send_json(h, 200, {
        "total_visits": total_visits,
        "total_clicks": total_clicks,
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "conversion_rate": conversion_rate,
    })


def handle_by_utm(h, supabase_url, service_key):
    """GET /api/report?action=by_utm"""
    if not check_auth(h):
        return

    try:
        visits = supabase_get(supabase_url, service_key, "page_visits?select=utm_source")
        clicks = supabase_get(supabase_url, service_key, "clicks?select=utm_source")
        sales = supabase_get(
            supabase_url, service_key,
            "sales?select=utm_source,amount,ticket_tier&payment_status=eq.paid"
        )
    except urllib.error.URLError as exc:
        _send_json(h, 502, {"error": f"Supabase request failed: {exc}"})
        return

    # Normalise utm_source: treat None as the string "direct"
    def norm(val):
        return val if val else "direct"

    # Count visits per utm_source
    visit_counts = defaultdict(int)
    for row in visits:
        visit_counts[norm(row.get("utm_source"))] += 1

    # Count clicks per utm_source
    click_counts = defaultdict(int)
    for row in clicks:
        click_counts[norm(row.get("utm_source"))] += 1

    # Aggregate sales per utm_source
    sale_counts = defaultdict(int)
    revenue_map = defaultdict(int)
    tier_map = defaultdict(lambda: defaultdict(int))  # utm -> tier -> count

    for row in sales:
        src = norm(row.get("utm_source"))
        tier = row.get("ticket_tier") or "unknown"
        sale_counts[src] += 1
        revenue_map[src] += row.get("amount", 0) or 0
        tier_map[src][tier] += 1

    # Merge all unique utm sources
    all_sources = set(visit_counts) | set(click_counts) | set(sale_counts)

    result = []
    for src in sorted(all_sources):
        tiers = tier_map.get(src, {})
        result.append({
            "utm_source": None if src == "direct" else src,
            "visits": visit_counts.get(src, 0),
            "clicks": click_counts.get(src, 0),
            "sales": sale_counts.get(src, 0),
            "revenue": revenue_map.get(src, 0),
            "early_bird": tiers.get("early_bird", 0),
            "regular": tiers.get("regular", 0),
            "vip": tiers.get("vip", 0),
        })

    _send_json(h, 200, result)


def handle_by_tier(h, supabase_url, service_key):
    """GET /api/report?action=by_tier"""
    if not check_auth(h):
        return

    try:
        sales = supabase_get(
            supabase_url, service_key,
            "sales?select=ticket_tier,amount&payment_status=eq.paid"
        )
    except urllib.error.URLError as exc:
        _send_json(h, 502, {"error": f"Supabase request failed: {exc}"})
        return

    tier_counts = defaultdict(int)
    tier_revenue = defaultdict(int)

    for row in sales:
        tier = row.get("ticket_tier") or "unknown"
        tier_counts[tier] += 1
        tier_revenue[tier] += row.get("amount", 0) or 0

    total_sales = sum(tier_counts.values())

    # Fixed display order, then any unexpected tiers appended
    ordered_tiers = ["early_bird", "regular", "vip"]
    extra_tiers = [t for t in tier_counts if t not in ordered_tiers]

    result = []
    for tier in ordered_tiers + extra_tiers:
        count = tier_counts.get(tier, 0)
        percentage = round((count / total_sales) * 100, 2) if total_sales else 0
        result.append({
            "tier": tier,
            "count": count,
            "revenue": tier_revenue.get(tier, 0),
            "percentage": percentage,
        })

    _send_json(h, 200, result)


def handle_clicks_over_time(h, supabase_url, service_key):
    """GET /api/report?action=clicks_over_time"""
    if not check_auth(h):
        return

    try:
        clicks = supabase_get(
            supabase_url, service_key,
            "clicks?select=clicked_at&clicked_at=gte." + _thirty_days_ago()
        )
    except urllib.error.URLError as exc:
        _send_json(h, 502, {"error": f"Supabase request failed: {exc}"})
        return

    daily_counts = defaultdict(int)
    for row in clicks:
        clicked_at = row.get("clicked_at", "")
        if clicked_at:
            # ISO timestamp: "2026-04-01T12:34:56+00:00" → take first 10 chars
            date_str = str(clicked_at)[:10]
            daily_counts[date_str] += 1

    result = [
        {"date": date, "count": count}
        for date, count in sorted(daily_counts.items())
    ]

    _send_json(h, 200, result)


def _thirty_days_ago():
    """Return an ISO date string 30 days before today without importing datetime externally."""
    import datetime
    cutoff = datetime.date.today() - datetime.timedelta(days=30)
    return cutoff.isoformat()


# ---------------------------------------------------------------------------
# Vercel handler
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        """Respond to CORS preflight."""
        self.send_response(204)
        _add_cors_headers(self)
        self.end_headers()

    def do_GET(self):
        # Parse query params
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        action = params.get("action", [""])[0]

        # Load Supabase credentials for all actions except auth
        try:
            supabase_url = get_env("SUPABASE_URL")
            service_key = get_env("SUPABASE_SERVICE_KEY")
        except EnvironmentError as exc:
            # auth endpoint does not need Supabase, so only fail for others
            if action != "auth":
                _send_json(self, 500, {"error": str(exc)})
                return
            supabase_url = service_key = None

        if action == "auth":
            handle_auth(self, params)

        elif action == "summary":
            handle_summary(self, supabase_url, service_key)

        elif action == "by_utm":
            handle_by_utm(self, supabase_url, service_key)

        elif action == "by_tier":
            handle_by_tier(self, supabase_url, service_key)

        elif action == "clicks_over_time":
            handle_clicks_over_time(self, supabase_url, service_key)

        else:
            _send_json(self, 400, {
                "error": f"Unknown action: '{action}'. Valid actions: auth, summary, by_utm, by_tier, clicks_over_time"
            })

    def log_message(self, format, *args):
        """Suppress default BaseHTTPRequestHandler logging to stdout."""
        pass
