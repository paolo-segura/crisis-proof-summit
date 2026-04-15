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
