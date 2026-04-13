"""Build 6 perform-editing-operations batches for Set B.

Maps Set B variant keys -> (asset_id, fill_element_id, text_element_id) based on
the transaction's returned pages/fills/richtexts. Reads the captions from
captions_setb_parsed.json and emits one JSON file per batch.
"""
import json
from pathlib import Path

ROOT = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit")
CAPS = json.loads((ROOT / "captions_setb_parsed.json").read_text())

# (variant_key, asset_id, fill_element_id, text_element_id, ad_page, caption_page)
PAIRS = [
    ("A1-PAIN-B_service_v2",       "MAHGlYiwcxY", "PBlHnMtdwpqf96fm", "PBpQtgnYDlCRg2CQ-LBdP1tTWdPBPWDPh", 1, 2),
    ("A1-PAIN-A_ecom_v2",          "MAHGlYYReRc", "PB7lnYKV7JmQZqKC", "PBpM3461YcRBJdJz-LBRcwKRn7ywXgKxq", 3, 4),
    ("A1-PAIN-C_b2b_v2",           "MAHGldwiNvo", "PB6S8Yg9Zf6lXglg", "PBqBr4NyZlZYqF4B-LBvysYPWsx9b7nR7", 5, 6),
    ("A1-OUTCOME-B_service_v2",    "MAHGlWnQ-E0", "PBjkDmyJYNb7nTCb", "PBc7M3jkJb4rLhL3-LBpRrZpRvYKSvW92", 7, 8),
    ("A1-OUTCOME-A_ecom_v2",       "MAHGlfGV8aE", "PBglK4Gk8P3VcN9H", "PBHQYvNj5MMC2N4n-LBNyWXdyZx2v7W51", 9, 10),
    ("A1-OUTCOME-C_b2b_v2",        "MAHGlSZ5y3Q", "PB6WNprxyKhKwNQx", "PBHk89RQr7DhkHgR-LBZSZBLbCF1zlVD8", 11, 12),
    ("A1-IDENTITY-B_service_v2",   "MAHGlRh-6kg", "PBwNcf5TXlj5Kkh1", "PBQ0JyZpMLxDnmzm-LBGXJssw6WdPpzk3", 13, 14),
    ("A1-IDENTITY-A_ecom_v2",      "MAHGlQ5QMW0", "PB5t7TZWXGSzhMCX", "PB1wLz1r7jcfwC33-LBkW7BKB9vPgWpXn", 15, 16),
    ("A1-CURIOSITY-B_service_v2",  "MAHGlcRw2mM", "PBGK1j8DzT0msDmD", "PB1JypllDdLq7P63-LBH1RWjmRbmbY90h", 17, 18),
    ("A1-CURIOSITY-A_ecom_v2",     "MAHGlYq9ky0", "PB3zzQk3dXVSzP4T", "PBqGYKm64k4522Df-LBfZ88plCG5hdRRl", 19, 20),
    ("A6-EARLYBIRD-CLOCK",         "MAHGlRz-tzs", "PBJ2LM4kNtmvZsBl", "PBZPTL5T8jBnhZvq-LB64GXMPWNnwjzQt", 21, 22),
    ("A6-EARLYBIRD-20PERCENT",     "MAHGlVKTha4", "PBzM0k1lXxskY71H", "PBB2BPNDp8f62hbL-LBCkKLdKvqGj6xdf", 23, 24),
    ("A6-EARLYBIRD-MAY1-LINE",     "MAHGldSytDA", "PBzszW7FB11cgxX9", "PBQRfmygm3yWQC58-LBdwzTtHw7PHg2J9", 25, 26),
    ("A6-EARLYBIRD-LAST-48HRS",    "MAHGlR-bt4w", "PBh5czQy3VcRwPzF", "PBQ31rGJb91ljvRP-LBmlYctnXzJVWLDg", 27, 28),
    ("A6-SEATS-FILLING",           "MAHGlUAOfsY", "PB3v87Xn8bWLZ3gW", "PBRKjHg6zRLqS87B-LBPdCgCbHVBktrGS", 29, 30),
    ("A6-DOORS-CLOSING",           "MAHGlfhoBdI", "PBsD7Kwxsh9yYzDg", "PBj9YVdSVV6TwNRp-LBKJWywDFYZMcwKP", 31, 32),
    ("A3-AFFIRMATIVE-B_service_v2","MAHGlZf6eZ4", "PB28zT36x2M0Dk3M", "PBYtV56cbFJlvsKj-LB1Rf0m5xLwx7v54", 33, 34),
    ("A3-AFFIRMATIVE-A_ecom_v2",   "MAHGlVrs0K0", "PB9LYdF7tJ0vhLbS", "PB3D163WYsMnPNQD-LBQqcr3VNQlQlmrM", 35, 36),
    ("A3-AFFIRMATIVE-C_b2b_v2",    "MAHGlWNsORA", "PBWf63NP0Yfhfn46", "PBFGqvBpYXKsMMJ9-LB5HFy0pMLkBXzvT", 37, 38),
    ("A3-DISQUALIFIER_v2",         "MAHGlYrorBU", "PBbwqjvSRQ7yhjFm", "PBHxm8JTPH1JPcr0-LBDjVW7xyp7cZVTR", 39, 40),
]

# The full ordered pages array from the transaction response (all 40 pages, is_responsive=false)
PAGES_ORDER = [
    "PBlHnMtdwpqf96fm","PBpQtgnYDlCRg2CQ","PB7lnYKV7JmQZqKC","PBpM3461YcRBJdJz",
    "PB6S8Yg9Zf6lXglg","PBqBr4NyZlZYqF4B","PBjkDmyJYNb7nTCb","PBc7M3jkJb4rLhL3",
    "PBglK4Gk8P3VcN9H","PBHQYvNj5MMC2N4n","PB6WNprxyKhKwNQx","PBHk89RQr7DhkHgR",
    "PBwNcf5TXlj5Kkh1","PBQ0JyZpMLxDnmzm","PB5t7TZWXGSzhMCX","PB1wLz1r7jcfwC33",
    "PBGK1j8DzT0msDmD","PB1JypllDdLq7P63","PB3zzQk3dXVSzP4T","PBqGYKm64k4522Df",
    "PBJ2LM4kNtmvZsBl","PBZPTL5T8jBnhZvq","PBzM0k1lXxskY71H","PBB2BPNDp8f62hbL",
    "PBzszW7FB11cgxX9","PBQRfmygm3yWQC58","PBh5czQy3VcRwPzF","PBQ31rGJb91ljvRP",
    "PB3v87Xn8bWLZ3gW","PBRKjHg6zRLqS87B","PBsD7Kwxsh9yYzDg","PBj9YVdSVV6TwNRp",
    "PB28zT36x2M0Dk3M","PBYtV56cbFJlvsKj","PB9LYdF7tJ0vhLbS","PB3D163WYsMnPNQD",
    "PBWf63NP0Yfhfn46","PBFGqvBpYXKsMMJ9","PBbwqjvSRQ7yhjFm","PBHxm8JTPH1JPcr0",
]
PAGES = [{"page_id": p, "is_responsive": False} for p in PAGES_ORDER]

# 6 batches: (name, start_pair_idx, end_pair_idx_exclusive)
BATCHES = [
    ("batch1", 0, 3),    # pairs 1-3  (pages 1-6)
    ("batch2", 3, 6),    # pairs 4-6  (pages 7-12)
    ("batch3", 6, 10),   # pairs 7-10 (pages 13-20)
    ("batch4", 10, 13),  # pairs 11-13 (pages 21-26)  early-bird sub1
    ("batch5", 13, 16),  # pairs 14-16 (pages 27-32)  scarcity sub2
    ("batch6", 16, 20),  # pairs 17-20 (pages 33-40)  audience + disqualifier
]


def build_batch(name: str, start: int, end: int):
    ops = []
    for (key, asset_id, fill_el, text_el, ad_page, cap_page) in PAIRS[start:end]:
        caption = CAPS.get(key)
        if caption is None:
            raise KeyError(f"no caption for {key}")
        ops.append({
            "type": "update_fill",
            "element_id": fill_el,
            "asset_type": "image",
            "asset_id": asset_id,
            "alt_text": f"{key} Set B creative",
        })
        ops.append({
            "type": "replace_text",
            "element_id": text_el,
            "text": caption,
        })
    first_ad_page = PAIRS[start][4]
    payload = {
        "transaction_id": "470000083744640536",
        "operations": ops,
        "pages": PAGES,
        "page_index": first_ad_page,
    }
    return payload


for (name, start, end) in BATCHES:
    payload = build_batch(name, start, end)
    path = ROOT / f"setb_{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    size_kb = path.stat().st_size / 1024
    n_ops = len(payload["operations"])
    pair_keys = [PAIRS[i][0] for i in range(start, end)]
    print(f"[ok] {name}: {n_ops} ops, {size_kb:.1f} KB, pages {PAIRS[start][4]}-{PAIRS[end-1][5]}")
    print(f"     variants: {pair_keys}")
