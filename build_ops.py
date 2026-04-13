"""Build the ops array + pages array for the massive Canva perform-editing-operations call.

Reads:
- captions_v2.json
- variant → asset_id mapping (hardcoded from upload responses)

Emits:
- crisis-proof-summit/canva_ops.json with:
    {"operations": [...], "pages": [...], "page_index": 7}
"""
import json
from pathlib import Path

ROOT = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit")

# Variant → Canva asset ID (from our uploads)
ASSET_IDS = {
    "A1-OUTCOME-B_service": "MAHGjbC9KE4",
    "A1-OUTCOME-A_ecom": "MAHGjf70QxI",
    "A1-OUTCOME-C_b2b": "MAHGjuG_03I",  # v2 (Meralco sticker fixed)
    "A1-IDENTITY-B_service": "MAHGjWI0-yk",
    "A1-IDENTITY-A_ecom": "MAHGjWYUWX8",
    "A1-IDENTITY-C_b2b": "MAHGjmsTw7M",
    "A1-CURIOSITY-B_service": "MAHGjoO5d-o",
    "A1-CURIOSITY-A_ecom": "MAHGjkGmUAY",
    "A1-CURIOSITY-C_b2b": "MAHGjoxWIx0",
    "A6-SEATS": "MAHGjqfJ15A",
    "A6-DEADLINE": "MAHGjpboR7A",  # v2 (calendar fixed)
    "A6-PRICE-JUMP": "MAHGjvZC0ng",  # v2 (calendar concept swap)
    "A6-LAST-CHANCE": "MAHGjqbX0aw",
    "A3-AFFIRMATIVE-B_service": "MAHGjv8xTe4",  # v2 (gradient fix)
    "A3-AFFIRMATIVE-A_ecom": "MAHGjiPy3lo",  # v2 (gradient fix)
    "A3-AFFIRMATIVE-C_b2b": "MAHGjkPB6U0",
    "A3-DISQUALIFIER": "MAHGjo7l9qc",  # v3 (clean room, no ghost text)
}

# Page mapping: pages 7..39 (odd = ad, even = caption), in the order we want
# the kit to appear on screen. Order: all OUTCOME, all IDENTITY, all CURIOSITY,
# all scarcity, then audience qualifier.
VARIANT_ORDER = [
    "A1-OUTCOME-B_service",
    "A1-OUTCOME-A_ecom",
    "A1-OUTCOME-C_b2b",
    "A1-IDENTITY-B_service",
    "A1-IDENTITY-A_ecom",
    "A1-IDENTITY-C_b2b",
    "A1-CURIOSITY-B_service",
    "A1-CURIOSITY-A_ecom",
    "A1-CURIOSITY-C_b2b",
    "A6-SEATS",
    "A6-DEADLINE",
    "A6-PRICE-JUMP",
    "A6-LAST-CHANCE",
    "A3-AFFIRMATIVE-B_service",
    "A3-AFFIRMATIVE-A_ecom",
    "A3-AFFIRMATIVE-C_b2b",
    "A3-DISQUALIFIER",
]

# Page data from the Canva start-editing-transaction response (just now)
PAGES = [
    ("PBlHnMtdwpqf96fm", 1),
    ("PBpQtgnYDlCRg2CQ", 2),
    ("PB7lnYKV7JmQZqKC", 3),
    ("PBpM3461YcRBJdJz", 4),
    ("PB6S8Yg9Zf6lXglg", 5),
    ("PBqBr4NyZlZYqF4B", 6),
    ("PBjkDmyJYNb7nTCb", 7),
    ("PBc7M3jkJb4rLhL3", 8),
    ("PBglK4Gk8P3VcN9H", 9),
    ("PBHQYvNj5MMC2N4n", 10),
    ("PB6WNprxyKhKwNQx", 11),
    ("PBHk89RQr7DhkHgR", 12),
    ("PBwNcf5TXlj5Kkh1", 13),
    ("PBQ0JyZpMLxDnmzm", 14),
    ("PB5t7TZWXGSzhMCX", 15),
    ("PB1wLz1r7jcfwC33", 16),
    ("PBGK1j8DzT0msDmD", 17),
    ("PB1JypllDdLq7P63", 18),
    ("PB3zzQk3dXVSzP4T", 19),
    ("PBqGYKm64k4522Df", 20),
    ("PBJ2LM4kNtmvZsBl", 21),
    ("PBZPTL5T8jBnhZvq", 22),
    ("PBzM0k1lXxskY71H", 23),
    ("PBB2BPNDp8f62hbL", 24),
    ("PBzszW7FB11cgxX9", 25),
    ("PBQRfmygm3yWQC58", 26),
    ("PBh5czQy3VcRwPzF", 27),
    ("PBQ31rGJb91ljvRP", 28),
    ("PB3v87Xn8bWLZ3gW", 29),
    ("PBRKjHg6zRLqS87B", 30),
    ("PBsD7Kwxsh9yYzDg", 31),
    ("PBj9YVdSVV6TwNRp", 32),
    ("PB28zT36x2M0Dk3M", 33),
    ("PBYtV56cbFJlvsKj", 34),
    ("PB9LYdF7tJ0vhLbS", 35),
    ("PB3D163WYsMnPNQD", 36),
    ("PBWf63NP0Yfhfn46", 37),
    ("PBFGqvBpYXKsMMJ9", 38),
    ("PBbwqjvSRQ7yhjFm", 39),
    ("PBHxm8JTPH1JPcr0", 40),
]

# Caption element IDs by caption page index (from the transaction response)
CAPTION_ELEMENTS = {
    8: "PBc7M3jkJb4rLhL3-LBpRrZpRvYKSvW92",
    10: "PBHQYvNj5MMC2N4n-LBNyWXdyZx2v7W51",
    12: "PBHk89RQr7DhkHgR-LBZSZBLbCF1zlVD8",
    14: "PBQ0JyZpMLxDnmzm-LBGXJssw6WdPpzk3",
    16: "PB1wLz1r7jcfwC33-LBkW7BKB9vPgWpXn",
    18: "PB1JypllDdLq7P63-LBH1RWjmRbmbY90h",
    20: "PBqGYKm64k4522Df-LBfZ88plCG5hdRRl",
    22: "PBZPTL5T8jBnhZvq-LB64GXMPWNnwjzQt",
    24: "PBB2BPNDp8f62hbL-LBCkKLdKvqGj6xdf",
    26: "PBQRfmygm3yWQC58-LBdwzTtHw7PHg2J9",
    28: "PBQ31rGJb91ljvRP-LBmlYctnXzJVWLDg",
    30: "PBRKjHg6zRLqS87B-LBPdCgCbHVBktrGS",
    32: "PBj9YVdSVV6TwNRp-LBKJWywDFYZMcwKP",
    34: "PBYtV56cbFJlvsKj-LB1Rf0m5xLwx7v54",
    36: "PB3D163WYsMnPNQD-LBQqcr3VNQlQlmrM",
    38: "PBFGqvBpYXKsMMJ9-LB5HFy0pMLkBXzvT",
    40: "PBHxm8JTPH1JPcr0-LBDjVW7xyp7cZVTR",
}


def main() -> None:
    captions = json.loads((ROOT / "captions_v2.json").read_text())
    assert len(VARIANT_ORDER) == 17
    assert len(CAPTION_ELEMENTS) == 17

    operations = []
    for i, variant_key in enumerate(VARIANT_ORDER):
        ad_page_num = 7 + i * 2  # 7, 9, 11, ... 39
        caption_page_num = ad_page_num + 1  # 8, 10, 12, ... 40
        ad_page_id = next(pid for pid, pn in PAGES if pn == ad_page_num)
        caption_element_id = CAPTION_ELEMENTS[caption_page_num]
        asset_id = ASSET_IDS[variant_key]
        caption_text = captions[variant_key]

        operations.append({
            "type": "update_fill",
            "element_id": ad_page_id,
            "asset_type": "image",
            "asset_id": asset_id,
            "alt_text": f"{variant_key} final creative",
        })
        operations.append({
            "type": "replace_text",
            "element_id": caption_element_id,
            "text": caption_text,
        })

    pages = [{"page_id": pid, "is_responsive": False} for pid, _ in PAGES]
    payload = {
        "operations": operations,
        "pages": pages,
        "page_index": 7,
    }
    out = ROOT / "canva_ops.json"
    out.write_text(json.dumps(payload, ensure_ascii=False))
    print(f"[ok] wrote {out.name}  ({len(operations)} operations, {len(pages)} pages)")


if __name__ == "__main__":
    main()
