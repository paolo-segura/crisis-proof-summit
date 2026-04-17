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
    # payment_status reads col 16 — real order status ("PAID"/"PENDING"), not
    # the col-14 amount-mode flag that's always "FULLY_PAID".
    assert result["payment_status"] == "PAID"
    assert result["paid_at"] == "2026-04-12T01:39:45.555Z"
    assert result["raw_row"] == SAMPLE_ROW

def test_parse_row_short_row_returns_none():
    # Defensive: if Scale Your Org changes schema, skip instead of crashing
    assert sp.parse_row(["only", "three", "cols"]) is None

def test_parse_row_header_row_returns_none():
    # Literal sheet header: col 0 is "Event Status", not a purchase event → skip
    header = [
        "Event Status", "Status", "Full Name", "Email", "Phone Number",
        "Product Name", "Iterm Pric", "Quantity", "Total price",
        "Reference Number", "Transaction Number", "ID",
        "", "", "", "Paid At", "Status",
    ]
    assert sp.parse_row(header) is None

def test_parse_row_non_bu_product_returns_none():
    # Shared Xendit gateway routes other products (e.g. Emerge Book) through the
    # same sheet. Those belong to a different dashboard, so skip them here.
    row = list(SAMPLE_ROW)
    row[5] = "Emerge Book"
    assert sp.parse_row(row) is None

def test_parse_row_pending_event_is_kept():
    # We still ingest pending rows so the pending row gets overwritten by the
    # success row on a later sync. Dashboard filters by payment_status downstream.
    row = list(SAMPLE_ROW)
    row[0] = "purchase.pending"
    row[1] = "pending"
    row[15] = ""          # no paid_at yet
    row[16] = "PENDING"   # real status
    result = sp.parse_row(row)
    assert result is not None
    assert result["payment_status"] == "PENDING"
    assert result["paid_at"] is None

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


# ---------- run_sync (orchestrator) ----------

class _FakeSupabase:
    """In-memory stand-in for the Supabase helpers."""
    def __init__(self, participants=None, unmatched=None):
        self.participants = participants or []
        self.unmatched = unmatched or []
        self.upserted = []
        self.patched = []
        self.logs = []

    def upsert(self, purchase, participant_id, match_method, utm_fields):
        self.upserted.append({
            "purchase": purchase, "participant_id": participant_id,
            "method": match_method, "utm": utm_fields,
        })

    def fetch_participants(self, emails, mobiles):
        hits = []
        for p in self.participants:
            p_email = (p.get("email") or "").lower().strip()
            p_mobile_norm = sp.normalize_mobile(p.get("mobile_number"))
            if p_email in emails or (p_mobile_norm and p_mobile_norm in mobiles):
                hits.append(p)
        return hits

    def fetch_unmatched(self, days=7):
        return list(self.unmatched)

    def update_match(self, order_id, pid, method, utm):
        self.patched.append({"order_id": order_id, "pid": pid, "method": method, "utm": utm})

    def write_log(self, log):
        self.logs.append(log)


def test_run_sync_upserts_matched_purchase_with_utm():
    fake = _FakeSupabase(participants=[
        _pt("p1", email="wyne_ramos@yahoo.com", created_at="2026-04-11T12:00:00Z",
            utm_source="pancake"),
    ])
    rows = [list(SAMPLE_ROW)]

    result = sp.run_sync(
        read_rows=lambda: rows,
        upsert=fake.upsert,
        fetch_participants=fake.fetch_participants,
        fetch_unmatched=fake.fetch_unmatched,
        update_match=fake.update_match,
        write_log=fake.write_log,
    )

    assert len(fake.upserted) == 1
    assert fake.upserted[0]["method"] == "email"
    assert fake.upserted[0]["utm"]["utm_source"] == "pancake"
    assert result["rows_upserted"] == 1
    assert result["rows_matched"] == 1
    assert result["rows_unmatched"] == 0
    assert result["success"] is True


def test_run_sync_unmatched_purchase_marked_direct():
    fake = _FakeSupabase(participants=[])
    rows = [list(SAMPLE_ROW)]

    sp.run_sync(
        read_rows=lambda: rows,
        upsert=fake.upsert,
        fetch_participants=fake.fetch_participants,
        fetch_unmatched=fake.fetch_unmatched,
        update_match=fake.update_match,
        write_log=fake.write_log,
    )

    assert fake.upserted[0]["method"] == "direct"
    assert fake.upserted[0]["utm"] == {
        "utm_source": None, "utm_medium": None, "utm_campaign": None, "utm_content": None,
    }


def test_run_sync_rematches_unmatched_purchases():
    fake = _FakeSupabase(
        participants=[
            _pt("p1", email="late@example.com", created_at="2026-04-13T09:00:00Z",
                utm_source="gencys"),
        ],
        unmatched=[
            {"order_id": "TXN-OLD", "email": "late@example.com",
             "mobile": "", "paid_at": "2026-04-12T10:00:00Z"},
        ],
    )

    sp.run_sync(
        read_rows=lambda: [],
        upsert=fake.upsert,
        fetch_participants=fake.fetch_participants,
        fetch_unmatched=fake.fetch_unmatched,
        update_match=fake.update_match,
        write_log=fake.write_log,
    )

    assert len(fake.patched) == 1
    assert fake.patched[0]["order_id"] == "TXN-OLD"
    assert fake.patched[0]["method"] == "email"
    assert fake.patched[0]["utm"]["utm_source"] == "gencys"


def test_run_sync_skips_malformed_rows_and_records_errors():
    fake = _FakeSupabase(participants=[])
    rows = [
        ["only", "two"],               # too short -> skipped
        list(SAMPLE_ROW),               # valid
    ]

    result = sp.run_sync(
        read_rows=lambda: rows,
        upsert=fake.upsert,
        fetch_participants=fake.fetch_participants,
        fetch_unmatched=fake.fetch_unmatched,
        update_match=fake.update_match,
        write_log=fake.write_log,
    )

    assert result["rows_read"] == 2
    assert result["rows_upserted"] == 1
    assert result["success"] is True


def test_run_sync_writes_audit_log():
    fake = _FakeSupabase()
    sp.run_sync(
        read_rows=lambda: [],
        upsert=fake.upsert,
        fetch_participants=fake.fetch_participants,
        fetch_unmatched=fake.fetch_unmatched,
        update_match=fake.update_match,
        write_log=fake.write_log,
    )
    assert len(fake.logs) == 1
    log = fake.logs[0]
    assert "started_at" in log and "finished_at" in log
    assert log["success"] is True
