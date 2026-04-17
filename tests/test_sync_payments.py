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


# ---------- build_col_map ----------

# Current Scale Your Org BU Bridge Sheet header (2026-04-17). Note the typo
# "SOURSE" — we still want to find it. Two "Status" columns — the later one
# (real order status) must win.
SAMPLE_HEADER = [
    "Event Status", "Status", "Full Name", "Email", "Phone Number",
    "Product Name", "Iterm Pric", "Quantity", "Total price",
    "UTM SOURSE",
    "Reference Number", "Transaction Number", "ID",
    "", "", "",
    "Paid At", "Status",
]


def test_build_col_map_resolves_essentials():
    col_map = sp.build_col_map(SAMPLE_HEADER)
    assert col_map["event_status"] == 0
    assert col_map["full_name"] == 2
    assert col_map["email"] == 3
    assert col_map["mobile"] == 4
    assert col_map["product"] == 5
    assert col_map["amount"] == 6
    assert col_map["quantity"] == 7
    assert col_map["total"] == 8
    assert col_map["order_id"] == 10
    assert col_map["paid_at"] == 16


def test_build_col_map_resolves_utm_sourse_typo():
    # Scale Your Org inserted "UTM SOURSE" (typo) at col 9. Matcher must find it.
    col_map = sp.build_col_map(SAMPLE_HEADER)
    assert col_map["utm_source"] == 9


def test_build_col_map_later_status_column_wins():
    # Col 1 is "Status" (event mirror); col 17 is "Status" (real order state).
    # Whichever occurs LAST in the header should be resolved for payment_status,
    # because that's the actual PAID/PENDING value we filter the dashboard on.
    col_map = sp.build_col_map(SAMPLE_HEADER)
    assert col_map["payment_status"] == 17


def test_build_col_map_missing_optional_columns_not_in_result():
    # If Scale Your Org hasn't added bu_session_id / utm_medium yet, those keys
    # should simply not be in the col_map — not throw, not default to 0.
    col_map = sp.build_col_map(SAMPLE_HEADER)
    assert "session_id" not in col_map
    assert "utm_medium" not in col_map
    assert "utm_campaign" not in col_map


def test_build_col_map_matches_underscore_and_case_variations():
    # If they later name columns "utm_source" or "UTM_Source", should still match.
    header = ["Event Status", "Email", "Reference Number", "Paid At", "Status",
              "utm_source", "UTM_Medium", "bu_session_id"]
    col_map = sp.build_col_map(header)
    assert col_map["utm_source"] == 5
    assert col_map["utm_medium"] == 6
    assert col_map["session_id"] == 7


def test_build_col_map_empty_header_returns_empty_dict():
    assert sp.build_col_map([]) == {}
    assert sp.build_col_map(None) == {}


# ---------- parse_row ----------

# Matches SAMPLE_HEADER layout (18 columns). Values taken from a real
# 'purchase.success' row Scale Your Org wrote for Wynes Ramos on 2026-04-12.
SAMPLE_ROW = [
    "purchase.success",                # 0  event_status
    "success",                         # 1  (event mirror — ignored)
    "Wynes Ramos",                     # 2  full_name
    "wyne_ramos@yahoo.com",            # 3  email
    "639178334375",                    # 4  phone
    "THE NEW BUSINESS NORMAL | VIP",   # 5  product
    "4999.98",                         # 6  amount
    "1",                               # 7  quantity
    "4999.98",                         # 8  total
    "",                                # 9  UTM SOURSE (empty on sheet today)
    "TXN-1775957887846-u6p9pzf4x",     # 10 order_id (Reference Number)
    "TXN-1775957887846-u6p9pzf4x",     # 11 Transaction Number
    "69daf781fc29a42382638a1f",        # 12 ID
    "xendit",                          # 13 (no header)
    "full",                            # 14 (no header)
    "FULLY_PAID",                      # 15 (no header — Xendit amount-mode flag)
    "2026-04-12T01:39:45.555Z",        # 16 Paid At
    "PAID",                            # 17 Status (real order state)
]

COL_MAP = sp.build_col_map(SAMPLE_HEADER)


def test_parse_row_full_sample():
    result = sp.parse_row(SAMPLE_ROW, COL_MAP)
    assert result["order_id"] == "TXN-1775957887846-u6p9pzf4x"
    assert result["email"] == "wyne_ramos@yahoo.com"
    assert result["mobile"] == "9178334375"
    assert result["full_name"] == "Wynes Ramos"
    assert result["ticket_tier"] == "vip"
    assert result["amount"] == 4999.98
    assert result["quantity"] == 1
    assert result["total"] == 4999.98
    # payment_status reads col 17 (real status), not col 15 (Xendit amount-mode flag)
    assert result["payment_status"] == "PAID"
    assert result["paid_at"] == "2026-04-12T01:39:45.555Z"
    # UTM SOURSE is empty in the current sheet → None (not empty string)
    assert result["utm_source"] is None
    assert result["utm_medium"] is None
    assert result["session_id"] is None
    assert result["raw_row"] == SAMPLE_ROW


def test_parse_row_empty_returns_none():
    assert sp.parse_row([], COL_MAP) is None
    assert sp.parse_row(None, COL_MAP) is None


def test_parse_row_short_row_gracefully_returns_none():
    # Row shorter than header (Sheets may trim trailing empties) shouldn't crash.
    # Cells past the end resolve to empty string → most fields fail validation.
    short = ["purchase.success"]  # only event_status; everything else missing
    assert sp.parse_row(short, COL_MAP) is None


def test_parse_row_header_row_returns_none():
    # Literal header row: event_status cell is "Event Status" → doesn't start
    # with "purchase." → skip.
    assert sp.parse_row(SAMPLE_HEADER, COL_MAP) is None


def test_parse_row_non_purchase_event_returns_none():
    # Anything that isn't "purchase.pending" / "purchase.success" gets skipped
    # (e.g. GHL refund webhooks, internal ops events).
    row = list(SAMPLE_ROW)
    row[0] = "order.refund"
    assert sp.parse_row(row, COL_MAP) is None


def test_parse_row_non_bu_product_returns_none():
    # Shared Xendit gateway routes other products (Emerge Book, test products)
    # through the same sheet. Those belong to a different dashboard — skip.
    row = list(SAMPLE_ROW)
    row[5] = "Emerge Book"
    assert sp.parse_row(row, COL_MAP) is None


def test_parse_row_pending_event_is_kept():
    # Pending rows still get ingested so the success row (same order_id) can
    # overwrite them on the next sync. The dashboard's PAID/FULLY_PAID filter
    # hides pending rows at query time.
    row = list(SAMPLE_ROW)
    row[0] = "purchase.pending"
    row[16] = ""          # no paid_at yet
    row[17] = "PENDING"   # real status
    result = sp.parse_row(row, COL_MAP)
    assert result is not None
    assert result["payment_status"] == "PENDING"
    assert result["paid_at"] is None


def test_parse_row_missing_order_id_returns_none():
    row = list(SAMPLE_ROW)
    row[10] = ""
    assert sp.parse_row(row, COL_MAP) is None


def test_parse_row_bad_amount_defaults_to_zero():
    row = list(SAMPLE_ROW)
    row[6] = "not-a-number"
    row[7] = ""
    row[8] = ""
    result = sp.parse_row(row, COL_MAP)
    assert result["amount"] == 0.0
    assert result["quantity"] == 0
    assert result["total"] == 0.0


def test_parse_row_normalizes_email_and_mobile():
    row = list(SAMPLE_ROW)
    row[3] = "  Wyne_Ramos@Yahoo.COM "
    row[4] = "+63 917 833 4375"
    result = sp.parse_row(row, COL_MAP)
    assert result["email"] == "wyne_ramos@yahoo.com"
    assert result["mobile"] == "9178334375"


def test_parse_row_populated_utm_sourse_is_extracted():
    # The day Scale Your Org starts filling the UTM SOURSE column, attribution
    # should flow through onto the purchase dict without any code change.
    row = list(SAMPLE_ROW)
    row[9] = "prime"
    result = sp.parse_row(row, COL_MAP)
    assert result["utm_source"] == "prime"


def test_parse_row_lowercases_utm_values():
    # 'Prime', 'PRIME', 'prime' must all aggregate to the same dashboard
    # bucket. Parser lowercases on ingest so the DB holds a single canonical
    # form — no case drift from GHL, manual share links, or ad tag mistakes.
    for raw, expected in [("Prime", "prime"), ("PRIME", "prime"), ("  GeNcYs  ", "gencys")]:
        row = list(SAMPLE_ROW)
        row[9] = raw
        result = sp.parse_row(row, COL_MAP)
        assert result["utm_source"] == expected, f"got {result['utm_source']!r} for {raw!r}"


def test_parse_row_session_id_from_extended_header():
    # Future-state: Scale Your Org adds bu_session_id + utm_medium + utm_campaign
    # as trailing columns. parse_row should pick them up automatically.
    header_full = SAMPLE_HEADER + ["UTM Medium", "UTM Campaign", "bu_session_id"]
    row_full = list(SAMPLE_ROW) + ["email", "bu_launch_2026", "9f7c3a-session-uuid"]
    col_map = sp.build_col_map(header_full)
    result = sp.parse_row(row_full, col_map)
    # UUID stays as-is (case-sensitive by convention)
    assert result["session_id"] == "9f7c3a-session-uuid"
    # UTMs lowercased
    assert result["utm_medium"] == "email"
    assert result["utm_campaign"] == "bu_launch_2026"


def test_parse_row_preserves_session_id_casing_when_mixed():
    # UUIDs are case-sensitive; don't lowercase them even though UTM values are.
    header_full = SAMPLE_HEADER + ["bu_session_id"]
    row_full = list(SAMPLE_ROW) + ["9F7C3A-SessionUUID"]
    col_map = sp.build_col_map(header_full)
    result = sp.parse_row(row_full, col_map)
    assert result["session_id"] == "9F7C3A-SessionUUID"


# ---------- match_purchase_to_participant ----------

PAID_AT = "2026-04-12T10:00:00Z"


def _pt(pid, email="", mobile="", session_id=None, created_at="", utm_source=None):
    """Build a participant dict for matcher tests (uses real DB field names)."""
    return {
        "id": pid,
        "email": email,
        "mobile_number": mobile,
        "session_id": session_id,
        "created_at": created_at,
        "utm_source": utm_source,
        "utm_medium": None,
        "utm_campaign": None,
        "utm_content": None,
    }


def test_match_by_session_id_is_highest_priority():
    # Even when email and mobile would also match, session_id wins because it's
    # the most specific signal (unique per browser).
    participants = [
        _pt("p_session", email="other@example.com", mobile="0000000000",
            session_id="sess-xyz", created_at="2026-04-11T12:00:00Z", utm_source="pancake"),
        _pt("p_email", email="wyne_ramos@yahoo.com", mobile="9178334375",
            created_at="2026-04-10T12:00:00Z", utm_source="prime"),
    ]
    pid, method = sp.match_purchase_to_participant(
        {"email": "wyne_ramos@yahoo.com", "mobile": "9178334375",
         "session_id": "sess-xyz", "paid_at": PAID_AT},
        participants,
    )
    assert pid == "p_session"
    assert method == "session_id"


def test_match_session_id_miss_falls_through_to_email():
    # If session_id is provided but no participant has it, fall back to email.
    participants = [
        _pt("p_email", email="wyne_ramos@yahoo.com", session_id="different-session",
            created_at="2026-04-11T12:00:00Z", utm_source="gencys"),
    ]
    pid, method = sp.match_purchase_to_participant(
        {"email": "wyne_ramos@yahoo.com", "mobile": "", "session_id": "sess-xyz",
         "paid_at": PAID_AT},
        participants,
    )
    assert pid == "p_email"
    assert method == "email"


def test_match_by_email():
    participants = [
        _pt("p1", email="wyne_ramos@yahoo.com", created_at="2026-04-11T12:00:00Z", utm_source="pancake"),
    ]
    pid, method = sp.match_purchase_to_participant(
        {"email": "wyne_ramos@yahoo.com", "mobile": "9178334375",
         "session_id": None, "paid_at": PAID_AT},
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
        {"email": "wyne_ramos@yahoo.com", "mobile": "9178334375",
         "session_id": None, "paid_at": PAID_AT},
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
        {"email": "wyne_ramos@yahoo.com", "mobile": "9178334375",
         "session_id": None, "paid_at": PAID_AT},
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
        {"email": "x@example.com", "mobile": "", "session_id": None, "paid_at": PAID_AT},
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
        {"email": "x@example.com", "mobile": "", "session_id": None, "paid_at": PAID_AT},
        participants,
    )
    assert pid == "p2"


def test_match_empty_email_and_mobile_returns_direct():
    pid, method = sp.match_purchase_to_participant(
        {"email": "", "mobile": "", "session_id": None, "paid_at": PAID_AT}, []
    )
    assert pid is None
    assert method == "direct"


def test_match_handles_participants_with_missing_fields():
    # Defensive: a participant row without created_at shouldn't crash
    participants = [
        {"id": "p1", "email": "x@example.com", "mobile_number": "",
         "session_id": None, "created_at": None},
    ]
    pid, method = sp.match_purchase_to_participant(
        {"email": "x@example.com", "mobile": "", "session_id": None, "paid_at": PAID_AT},
        participants,
    )
    assert pid == "p1"
    assert method == "email"


# ---------- _resolve_utm ----------

def test_resolve_utm_sheet_wins_over_participant():
    # When the purchase (sheet) has UTM, it's authoritative — that's the
    # attribution at the moment of payment.
    purchase = {"utm_source": "prime", "utm_medium": "cpc",
                "utm_campaign": None, "utm_content": None}
    participant = {"utm_source": "gencys", "utm_medium": "email",
                   "utm_campaign": "bu_april", "utm_content": "hero"}
    utm = sp._resolve_utm(purchase, participant)
    assert utm == {"utm_source": "prime", "utm_medium": "cpc",
                   "utm_campaign": "bu_april", "utm_content": "hero"}


def test_resolve_utm_participant_fills_gaps_when_sheet_blank():
    # Sheet UTM missing → fall back to participant's attribution from the
    # visit that led to the form fill.
    purchase = {"utm_source": None, "utm_medium": None,
                "utm_campaign": None, "utm_content": None}
    participant = {"utm_source": "gencys", "utm_medium": "email",
                   "utm_campaign": "bu_april", "utm_content": "hero"}
    utm = sp._resolve_utm(purchase, participant)
    assert utm["utm_source"] == "gencys"
    assert utm["utm_medium"] == "email"


def test_resolve_utm_no_participant_returns_sheet_only():
    purchase = {"utm_source": "prime", "utm_medium": None,
                "utm_campaign": None, "utm_content": None}
    utm = sp._resolve_utm(purchase, None)
    assert utm["utm_source"] == "prime"
    assert utm["utm_medium"] is None


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

    def fetch_participants(self, emails, mobiles, session_ids=None):
        hits = []
        for p in self.participants:
            p_email = (p.get("email") or "").lower().strip()
            p_mobile_norm = sp.normalize_mobile(p.get("mobile_number"))
            p_session = p.get("session_id")
            if (p_email in emails
                    or (p_mobile_norm and p_mobile_norm in mobiles)
                    or (p_session and session_ids and p_session in session_ids)):
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
    # Row 0 is the header; data rows follow.
    rows = [list(SAMPLE_HEADER), list(SAMPLE_ROW)]

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
    # Sheet UTM is empty on SAMPLE_ROW, so the participant's utm_source wins as fallback
    assert fake.upserted[0]["utm"]["utm_source"] == "pancake"
    assert result["rows_upserted"] == 1
    assert result["rows_matched"] == 1
    assert result["rows_unmatched"] == 0
    assert result["success"] is True


def test_run_sync_sheet_utm_overrides_participant_utm():
    # When the sheet has UTM for a row, it wins over the participant's — the
    # sheet value is the attribution at payment, participant's is at form-fill.
    fake = _FakeSupabase(participants=[
        _pt("p1", email="wyne_ramos@yahoo.com", created_at="2026-04-11T12:00:00Z",
            utm_source="pancake"),  # form-fill UTM
    ])
    row_with_sheet_utm = list(SAMPLE_ROW)
    row_with_sheet_utm[9] = "prime"  # sheet UTM SOURSE populated
    rows = [list(SAMPLE_HEADER), row_with_sheet_utm]

    sp.run_sync(
        read_rows=lambda: rows,
        upsert=fake.upsert,
        fetch_participants=fake.fetch_participants,
        fetch_unmatched=fake.fetch_unmatched,
        update_match=fake.update_match,
        write_log=fake.write_log,
    )

    assert fake.upserted[0]["utm"]["utm_source"] == "prime"  # sheet wins


def test_run_sync_unmatched_purchase_marked_direct():
    fake = _FakeSupabase(participants=[])
    rows = [list(SAMPLE_HEADER), list(SAMPLE_ROW)]

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
             "mobile": "", "session_id": None, "paid_at": "2026-04-12T10:00:00Z"},
        ],
    )

    sp.run_sync(
        read_rows=lambda: [list(SAMPLE_HEADER)],   # empty data rows; rematch still runs
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
        list(SAMPLE_HEADER),
        ["only", "two"],                # too short → header-driven parse returns None
        list(SAMPLE_ROW),                # valid
    ]

    result = sp.run_sync(
        read_rows=lambda: rows,
        upsert=fake.upsert,
        fetch_participants=fake.fetch_participants,
        fetch_unmatched=fake.fetch_unmatched,
        update_match=fake.update_match,
        write_log=fake.write_log,
    )

    assert result["rows_read"] == 3   # header + 2 data rows
    assert result["rows_upserted"] == 1
    assert result["success"] is True


def test_run_sync_fails_fast_when_header_missing_essentials():
    # If Scale Your Org nukes critical columns (e.g. removes 'Email' or
    # 'Reference Number'), refuse to process instead of silently upserting
    # garbage or skipping all rows without explanation.
    fake = _FakeSupabase()
    broken_header = ["Event Status", "Full Name", "Product Name"]   # no Email, no Reference Number
    rows = [broken_header, list(SAMPLE_ROW)]

    result = sp.run_sync(
        read_rows=lambda: rows,
        upsert=fake.upsert,
        fetch_participants=fake.fetch_participants,
        fetch_unmatched=fake.fetch_unmatched,
        update_match=fake.update_match,
        write_log=fake.write_log,
    )

    assert len(fake.upserted) == 0
    assert result["success"] is False
    assert any(e.get("phase") == "header" for e in result["errors"])


def test_run_sync_writes_audit_log():
    fake = _FakeSupabase()
    sp.run_sync(
        read_rows=lambda: [list(SAMPLE_HEADER)],
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
