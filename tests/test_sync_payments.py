import sync_payments as sp


# ---------- normalize_email ----------

def test_normalize_email_lowercases_and_trims():
    assert sp.normalize_email("  Paolo@Example.COM ") == "paolo@example.com"

def test_normalize_email_handles_none():
    assert sp.normalize_email(None) == ""

def test_normalize_email_handles_empty():
    assert sp.normalize_email("") == ""


# ---------- normalize_mobile ----------

def test_normalize_mobile_strips_country_code_63():
    assert sp.normalize_mobile("639178334375") == "9178334375"

def test_normalize_mobile_strips_leading_zero():
    assert sp.normalize_mobile("09178334375") == "9178334375"

def test_normalize_mobile_strips_plus_sign():
    assert sp.normalize_mobile("+639178334375") == "9178334375"

def test_normalize_mobile_strips_formatting():
    assert sp.normalize_mobile("+63 917 833 4375") == "9178334375"

def test_normalize_mobile_already_normalized():
    assert sp.normalize_mobile("9178334375") == "9178334375"

def test_normalize_mobile_handles_none():
    assert sp.normalize_mobile(None) == ""

def test_normalize_mobile_returns_empty_if_too_short():
    # Less than 10 digits → ambiguous, return empty so it never matches
    assert sp.normalize_mobile("1234") == ""


# ---------- parse_tier ----------

def test_parse_tier_from_product_with_pipe():
    assert sp.parse_tier("THE NEW BUSINESS NORMAL | VIP") == "vip"

def test_parse_tier_regular():
    assert sp.parse_tier("THE NEW BUSINESS NORMAL | Regular") == "regular"

def test_parse_tier_early_bird():
    assert sp.parse_tier("BUSINESS UNLOCKED | Early Bird") == "early_bird"

def test_parse_tier_no_pipe_falls_back_to_whole_string():
    assert sp.parse_tier("VIP") == "vip"

def test_parse_tier_none_returns_empty():
    assert sp.parse_tier(None) == ""

def test_parse_tier_strips_whitespace():
    assert sp.parse_tier("  BUSINESS UNLOCKED  |  VIP  ") == "vip"

def test_parse_tier_double_spaces_collapse_to_single_underscore():
    # "Early  Bird" (double space) should still normalize to early_bird, not early__bird
    assert sp.parse_tier("FOO | Early  Bird") == "early_bird"


# ---------- parse_row ----------

SAMPLE_ROW = [
    "purchase.success",
    "success",
    "Wynes Ramos",
    "wyne_ramos@yahoo.com",
    "639178334375",
    "THE NEW BUSINESS NORMAL | VIP",
    "4999.98",
    "1",
    "4999.98",
    "TXN-1775957887846-u6p9pzf4x",
    "TXN-1775957887846-u6p9pzf4x",
    "69daf781fc29a42382638a1f",
    "xendit",
    "full",
    "FULLY_PAID",
    "2026-04-12T01:39:45.555Z",
    "PAID",
]

def test_parse_row_full_sample():
    result = sp.parse_row(SAMPLE_ROW)
    assert result["order_id"] == "TXN-1775957887846-u6p9pzf4x"
    assert result["email"] == "wyne_ramos@yahoo.com"
    assert result["mobile"] == "9178334375"
    assert result["full_name"] == "Wynes Ramos"
    assert result["ticket_tier"] == "vip"
    assert result["amount"] == 4999.98
    assert result["quantity"] == 1
    assert result["total"] == 4999.98
    assert result["payment_provider"] == "xendit"
    assert result["payment_status"] == "FULLY_PAID"
    assert result["paid_at"] == "2026-04-12T01:39:45.555Z"
    assert result["raw_row"] == SAMPLE_ROW

def test_parse_row_short_row_returns_none():
    # Defensive: if Scale Your Org changes schema, skip instead of crashing
    assert sp.parse_row(["only", "three", "cols"]) is None

def test_parse_row_missing_order_id_returns_none():
    row = list(SAMPLE_ROW)
    row[9] = ""
    assert sp.parse_row(row) is None

def test_parse_row_bad_amount_defaults_to_zero():
    row = list(SAMPLE_ROW)
    row[6] = "not-a-number"
    row[7] = ""
    row[8] = ""
    result = sp.parse_row(row)
    assert result["amount"] == 0.0
    assert result["quantity"] == 0
    assert result["total"] == 0.0

def test_parse_row_normalizes_email_and_mobile():
    # Even if Scale Your Org sends mixed-case email or different mobile format
    row = list(SAMPLE_ROW)
    row[3] = "  Wyne_Ramos@Yahoo.COM "
    row[4] = "+63 917 833 4375"
    result = sp.parse_row(row)
    assert result["email"] == "wyne_ramos@yahoo.com"
    assert result["mobile"] == "9178334375"


# ---------- match_purchase_to_participant ----------

PAID_AT = "2026-04-12T10:00:00Z"

def _pt(pid, email="", mobile="", created_at="", utm_source=None):
    """Build a participant dict for matcher tests (uses real DB field names)."""
    return {
        "id": pid,
        "email": email,
        "mobile_number": mobile,
        "created_at": created_at,
        "utm_source": utm_source,
        "utm_medium": None,
        "utm_campaign": None,
        "utm_content": None,
    }

def test_match_by_email():
    participants = [
        _pt("p1", email="wyne_ramos@yahoo.com", created_at="2026-04-11T12:00:00Z", utm_source="pancake"),
    ]
    pid, method = sp.match_purchase_to_participant(
        {"email": "wyne_ramos@yahoo.com", "mobile": "9178334375", "paid_at": PAID_AT},
        participants,
    )
    assert pid == "p1"
    assert method == "email"

def test_match_falls_back_to_mobile():
    participants = [
        _pt("p1", email="different@example.com", mobile="9178334375",
            created_at="2026-04-11T12:00:00Z", utm_source="rtd"),
    ]
    pid, method = sp.match_purchase_to_participant(
        {"email": "wyne_ramos@yahoo.com", "mobile": "9178334375", "paid_at": PAID_AT},
        participants,
    )
    assert pid == "p1"
    assert method == "mobile"

def test_match_no_match_returns_direct():
    participants = [
        _pt("p1", email="someone-else@example.com", mobile="9000000000",
            created_at="2026-04-11T12:00:00Z"),
    ]
    pid, method = sp.match_purchase_to_participant(
        {"email": "wyne_ramos@yahoo.com", "mobile": "9178334375", "paid_at": PAID_AT},
        participants,
    )
    assert pid is None
    assert method == "direct"

def test_match_multiple_picks_most_recent_before_payment():
    participants = [
        _pt("p_old", email="x@example.com", created_at="2026-04-05T12:00:00Z", utm_source="old"),
        _pt("p_new", email="x@example.com", created_at="2026-04-11T12:00:00Z", utm_source="new"),
    ]
    pid, _ = sp.match_purchase_to_participant(
        {"email": "x@example.com", "mobile": "", "paid_at": PAID_AT},
        participants,
    )
    assert pid == "p_new"

def test_match_all_after_payment_picks_most_recent_overall():
    # Paid first, form later scenario
    participants = [
        _pt("p1", email="x@example.com", created_at="2026-04-13T09:00:00Z", utm_source="late"),
        _pt("p2", email="x@example.com", created_at="2026-04-14T09:00:00Z", utm_source="later"),
    ]
    pid, _ = sp.match_purchase_to_participant(
        {"email": "x@example.com", "mobile": "", "paid_at": PAID_AT},
        participants,
    )
    assert pid == "p2"

def test_match_empty_email_and_mobile_returns_direct():
    pid, method = sp.match_purchase_to_participant(
        {"email": "", "mobile": "", "paid_at": PAID_AT}, []
    )
    assert pid is None
    assert method == "direct"

def test_match_handles_participants_with_missing_fields():
    # Defensive: a participant row without created_at shouldn't crash
    participants = [
        {"id": "p1", "email": "x@example.com", "mobile_number": "", "created_at": None},
    ]
    pid, method = sp.match_purchase_to_participant(
        {"email": "x@example.com", "mobile": "", "paid_at": PAID_AT},
        participants,
    )
    assert pid == "p1"
    assert method == "email"
