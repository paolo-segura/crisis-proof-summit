"""Tests for the manual-sales sync parser.

The parser converts the client-maintained "BUS: Leads" sheet into purchase
dicts that match the new_business_normal_purchases schema. These tests are
pure-Python (no I/O) - the orchestrator's I/O is injected.
"""

import sync_manual_sales as sms


# ---------- payment amount parsing ----------

def test_parse_payment_handles_comma_thousands():
    assert sms.parse_payment_amount("14,000") == 14000.0

def test_parse_payment_handles_peso_prefix():
    assert sms.parse_payment_amount("P1500") == 1500.0

def test_parse_payment_handles_decimals():
    assert sms.parse_payment_amount("1500.50") == 1500.5

def test_parse_payment_empty_returns_zero():
    assert sms.parse_payment_amount("") == 0.0
    assert sms.parse_payment_amount(None) == 0.0
    assert sms.parse_payment_amount("   ") == 0.0

def test_parse_payment_non_numeric_returns_zero():
    assert sms.parse_payment_amount("TBD") == 0.0
    assert sms.parse_payment_amount("pending") == 0.0


# ---------- order_id stability ----------

def test_make_order_id_is_deterministic():
    a = sms.make_order_id("BUS: Warm", "z2m|cj-estavillo")
    b = sms.make_order_id("BUS: Warm", "z2m|cj-estavillo")
    assert a == b

def test_make_order_id_differs_per_identity():
    a = sms.make_order_id("BUS: Warm", "z2m|cj-estavillo")
    b = sms.make_order_id("BUS: Warm", "z2m|earlbin-fabian")
    assert a != b

def test_make_order_id_has_expected_prefix():
    out = sms.make_order_id("Bulk 1000", "test@x.com")
    assert out.startswith("MANUAL-BULK-1000-")


# ---------- warm-tab name parsing ----------

def test_parse_warm_names_numbered_list():
    cell = "1. CJ Estavillo\n2. Earlbin Fabian\n3. Claystone Policarpio"
    out = sms.parse_warm_names(cell)
    assert out == [("CJ Estavillo", 1), ("Earlbin Fabian", 1), ("Claystone Policarpio", 1)]

def test_parse_warm_names_pax_pattern():
    out = sms.parse_warm_names("1.John Concina 4 pax")
    assert out == [("John Concina", 4)]

def test_parse_warm_names_handles_paren_numbers():
    cell = "1) Mar\n2) Joshua"
    out = sms.parse_warm_names(cell)
    assert out == [("Mar", 1), ("Joshua", 1)]

def test_parse_warm_names_skips_blank_lines():
    cell = "1. Foo\n\n2. Bar\n  \n3. Baz"
    out = sms.parse_warm_names(cell)
    assert out == [("Foo", 1), ("Bar", 1), ("Baz", 1)]

def test_parse_warm_names_empty_cell():
    assert sms.parse_warm_names("") == []
    assert sms.parse_warm_names(None) == []


# ---------- warm row -> purchases ----------

def _warm_col_map():
    header = ["", "Company Name", "Name", "Payment"]
    return sms.build_col_map(header, sms._WARM_COL_ALIASES)


def test_parse_warm_row_splits_payment_evenly():
    row = ["warm", "Z2M", "1. CJ\n2. Earlbin", "14000"]
    purchases = sms.parse_warm_row(row, _warm_col_map(), row_idx=2)
    assert len(purchases) == 2
    assert all(p["amount"] == 7000.0 for p in purchases)
    assert all(p["payment_provider"] == "manual" for p in purchases)
    assert all(p["payment_status"] == "PAID" for p in purchases)
    assert all(p["ticket_tier"] == "warm" for p in purchases)
    names = [p["full_name"] for p in purchases]
    assert "CJ" in names and "Earlbin" in names


def test_parse_warm_row_skips_when_payment_empty():
    """Paolo's rule: only count rows where Payment is filled."""
    row = ["warm", "DEF", "1. Mar\n2. Joshua\n3. Amiel", ""]
    assert sms.parse_warm_row(row, _warm_col_map(), row_idx=4) == []


def test_parse_warm_row_skips_when_payment_zero():
    row = ["warm", "DEF", "1. Mar", "0"]
    assert sms.parse_warm_row(row, _warm_col_map(), row_idx=4) == []


def test_parse_warm_row_handles_pax_pattern():
    row = ["warm", "AJ3 Cool Aire", "1.John Concina 4 pax", "8000"]
    purchases = sms.parse_warm_row(row, _warm_col_map(), row_idx=3)
    assert len(purchases) == 4
    assert all(p["amount"] == 2000.0 for p in purchases)
    # Each pax gets a distinct order_id
    assert len({p["order_id"] for p in purchases}) == 4


def test_parse_warm_row_falls_back_when_names_empty():
    """Payment filled but no names listed - still record one anonymous attendee."""
    row = ["warm", "Aircon King", "", "5000"]
    purchases = sms.parse_warm_row(row, _warm_col_map(), row_idx=5)
    assert len(purchases) == 1
    assert purchases[0]["amount"] == 5000.0
    assert "Aircon King" in purchases[0]["full_name"]


def test_parse_warm_row_idempotent():
    row = ["warm", "Z2M", "1. CJ\n2. Earlbin", "14000"]
    a = sms.parse_warm_row(row, _warm_col_map(), row_idx=2)
    b = sms.parse_warm_row(row, _warm_col_map(), row_idx=2)
    assert {p["order_id"] for p in a} == {p["order_id"] for p in b}


# ---------- header normalization (Google Form multi-line headers) ----------

def test_normalize_header_takes_first_line_only():
    """Google Form headers cram help text into the same cell as the question.
    The parser must match on the question text, not the trailing help blob."""
    raw = "Upload Proof of Payment:\nUpload your payment screenshot.\nMake sure your name and reference number are visible."
    assert sms._normalize_header(raw) == "upload proof of payment:"


def test_build_col_map_resolves_multiline_form_headers():
    """The actual Bulk 1000 sheet has multi-line Google Form headers - the
    parser must still resolve every form column via the aliases."""
    real_header = [
        "Timestamp",
        "Full Name",
        "Mobile Number",
        "Email Address",
        "Which describes you?\n(If not listed, please select “Others” and specify below)",
        "What type of business/company do you have?\n(If not listed, please select “Others” and specify below)",
        "Who referred you to this event?\n(Please enter the full name of the person who invited you so we can acknowledge them.)",
        "How would you like to attend?",
        "Select Registration Type",
        "Upload Proof of Payment:\nUpload your payment screenshot.\nMake sure your name and reference number are visible.",
    ]
    col_map = sms.build_col_map(real_header, sms._FORM_COL_ALIASES)
    assert col_map.get("full_name") == 1
    assert col_map.get("mobile") == 2
    assert col_map.get("email") == 3
    assert col_map.get("registration") == 8
    assert col_map.get("payment_proof") == 9


def test_build_col_map_handles_organic_reordered_layout():
    """The Organic tab has a different column order than the Bulk tabs.
    Header-based parsing means we don't care - it should still resolve."""
    organic_header = [
        "Timestamp", "Full Name", "Mobile Number", "Email Address",
        "Which describes you?\n(...)", "What type of business/company do you have?\n(...)",
        "Select Registration Type",
        "Upload Proof of Payment:\nUpload your payment screenshot.",
        "Who referred you to this event?\n(...)",
        "How would you like to attend?",
        "Column 10",
    ]
    col_map = sms.build_col_map(organic_header, sms._FORM_COL_ALIASES)
    # Registration is at col 6 in Organic vs col 8 in Bulk - parser handles it
    assert col_map.get("registration") == 6
    assert col_map.get("payment_proof") == 7
    assert col_map.get("full_name") == 1


# ---------- form-tab row -> purchase ----------

def _form_col_map():
    header = [
        "Timestamp", "Full Name", "Mobile Number", "Email Address",
        "Which describes you?", "What type of business/company do you have?",
        "Who referred you to this event?", "How would you like to attend?",
        "Select Registration Type", "Upload Proof of Payment:",
    ]
    return sms.build_col_map(header, sms._FORM_COL_ALIASES)


def test_parse_form_row_basic():
    row = [
        "5/2/2026 4:17:08", "Marife Leal-Lalonde", "09953348067",
        "Mafeonline23@gmail.com", "Business Owner", "E-commerce / Online Selling",
        "Gencys Group", "Face-to-Face", "P1000",
        "https://drive.google.com/proof.jpg",
    ]
    p = sms.parse_form_row(row, _form_col_map(), "Bulk 1000", "bulk_1000", 1000)
    assert p is not None
    assert p["full_name"] == "Marife Leal-Lalonde"
    assert p["email"] == "mafeonline23@gmail.com"
    assert p["mobile"] == "9953348067"
    assert p["amount"] == 1000.0
    assert p["ticket_tier"] == "bulk_1000"
    assert p["payment_provider"] == "manual"
    assert p["payment_status"] == "PAID"


def test_parse_form_row_uses_default_amount_when_registration_unparseable():
    row = [
        "5/2/2026", "Test Person", "09171234567", "test@x.com",
        "Owner", "Retail", "Bonifacio", "Online", "TBD",
        "https://drive.google.com/proof.jpg",  # has proof
    ]
    p = sms.parse_form_row(row, _form_col_map(), "Bulk 1500", "bulk_1500", 1500)
    assert p is not None
    assert p["amount"] == 1500.0


def test_parse_form_row_skips_no_payment_proof_no_amount():
    row = [
        "5/2/2026", "Test Person", "09171234567", "test@x.com",
        "Owner", "Retail", "Bonifacio", "Online", "",
        "",  # no proof either
    ]
    p = sms.parse_form_row(row, _form_col_map(), "Organic", "organic", None)
    assert p is None


def test_parse_form_row_skips_blank_name():
    row = ["", "", "", "", "", "", "", "", "P1000", ""]
    p = sms.parse_form_row(row, _form_col_map(), "Bulk 1000", "bulk_1000", 1000)
    assert p is None


def test_parse_form_row_idempotent_on_email():
    """Same email -> same order_id even if other cells change (allows in-place edits)."""
    row1 = [
        "5/2/2026", "Marife", "09953348067", "Mafe@x.com",
        "Owner", "Retail", "Gencys", "Face-to-Face", "P1000",
        "https://example.com/proof1.jpg",
    ]
    row2 = [
        "5/3/2026", "Marife Lalonde", "09953348067", "Mafe@x.com",
        "Owner", "E-commerce", "Gencys", "Online", "P1000",
        "https://example.com/proof2.jpg",
    ]
    p1 = sms.parse_form_row(row1, _form_col_map(), "Bulk 1000", "bulk_1000", 1000)
    p2 = sms.parse_form_row(row2, _form_col_map(), "Bulk 1000", "bulk_1000", 1000)
    assert p1["order_id"] == p2["order_id"]


# ---------- parse_all_tabs end-to-end ----------

def test_parse_all_tabs_combines_warm_and_form():
    tabs = {
        "BUS: Warm": [
            ["", "Company Name", "Name", "Payment"],
            ["warm", "Z2M", "1. CJ\n2. Earlbin", "14000"],
            ["warm", "DEF", "1. Skipped\n2. NoPay", ""],  # skipped - no payment
        ],
        "Bulk 1000": [
            ["Timestamp", "Full Name", "Mobile Number", "Email Address",
             "Which describes you?", "What type of business/company do you have?",
             "Who referred you to this event?", "How would you like to attend?",
             "Select Registration Type", "Upload Proof of Payment:"],
            ["5/2/2026", "Marife", "09953348067", "Mafe@x.com",
             "Owner", "Retail", "Gencys", "Face-to-Face", "P1000",
             "https://drive.google.com/proof.jpg"],
        ],
    }
    purchases, errors = sms.parse_all_tabs(tabs)
    assert errors == []
    # 2 from Z2M (split warm) + 1 form-tab row = 3
    assert len(purchases) == 3
    tabs_seen = {p["_meta_tab"] for p in purchases}
    assert tabs_seen == {"BUS: Warm", "Bulk 1000"}


def test_parse_all_tabs_skips_complimentary_implicitly():
    """Complimentary isn't in our tab map - if it appears in the input it's ignored."""
    tabs = {
        "Complimentary Tickets": [
            ["", "Names", "Company Name"],
            ["1", "Skip Me", "Free Co"],
        ],
    }
    purchases, _ = sms.parse_all_tabs(tabs)
    assert purchases == []


def test_parse_all_tabs_handles_missing_required_warm_columns():
    tabs = {"BUS: Warm": [["wrong", "headers"], ["warm", "Z2M"]]}
    _, errors = sms.parse_all_tabs(tabs)
    assert any(e.get("tab") == "BUS: Warm" for e in errors)


# ---------- run_sync orchestrator with injected I/O ----------

def test_run_sync_calls_upsert_for_each_purchase():
    fake_tabs = {
        "BUS: Warm": [
            ["", "Company Name", "Name", "Payment"],
            ["warm", "Z2M", "1. CJ\n2. Earlbin", "14000"],
        ],
    }
    upserted = []
    logged = []

    result = sms.run_sync(
        read_tabs=lambda: fake_tabs,
        upsert=upserted.append,
        write_log=logged.append,
    )

    assert result["success"] is True
    assert result["rows_upserted"] == 2
    assert len(upserted) == 2
    assert len(logged) == 1
    assert logged[0]["rows_upserted"] == 2


def test_run_sync_records_upsert_failures_without_aborting():
    """One bad row shouldn't kill the whole sync."""
    fake_tabs = {
        "BUS: Warm": [
            ["", "Company Name", "Name", "Payment"],
            ["warm", "Z2M", "1. CJ\n2. Earlbin", "14000"],
        ],
    }
    calls = {"n": 0}

    def flaky_upsert(_):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")

    result = sms.run_sync(
        read_tabs=lambda: fake_tabs,
        upsert=flaky_upsert,
        write_log=lambda _: None,
    )
    assert result["success"] is False
    assert result["rows_upserted"] == 1
    assert any("boom" in e.get("error", "") for e in result["errors"])


def test_run_sync_returns_empty_when_sheet_unconfigured():
    """If MANUAL_SALES_SHEET_ID isn't set, read_manual_sheet returns {}.
    The orchestrator should run cleanly with zero rows."""
    upserted = []
    result = sms.run_sync(
        read_tabs=lambda: {},
        upsert=upserted.append,
        write_log=lambda _: None,
    )
    assert result["success"] is True
    assert result["rows_upserted"] == 0
    assert upserted == []
