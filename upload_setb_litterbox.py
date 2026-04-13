"""Upload 20 Set B composites to litterbox.catbox.moe in parallel. Prints a JSON
dict of variant_key -> public URL. Uses time=1h expiry (standard for the pipeline)."""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

GEN = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/generated")

# Ordered list of (pair_index, variant_key, final_png_filename)
PAIRS = [
    (1, "A1-PAIN-B_service_v2"),
    (2, "A1-PAIN-A_ecom_v2"),
    (3, "A1-PAIN-C_b2b_v2"),
    (4, "A1-OUTCOME-B_service_v2"),
    (5, "A1-OUTCOME-A_ecom_v2"),
    (6, "A1-OUTCOME-C_b2b_v2"),
    (7, "A1-IDENTITY-B_service_v2"),
    (8, "A1-IDENTITY-A_ecom_v2"),
    (9, "A1-CURIOSITY-B_service_v2"),
    (10, "A1-CURIOSITY-A_ecom_v2"),
    (11, "A6-EARLYBIRD-CLOCK"),
    (12, "A6-EARLYBIRD-20PERCENT"),
    (13, "A6-EARLYBIRD-MAY1-LINE"),
    (14, "A6-EARLYBIRD-LAST-48HRS"),
    (15, "A6-SEATS-FILLING"),
    (16, "A6-DOORS-CLOSING"),
    (17, "A3-AFFIRMATIVE-B_service_v2"),
    (18, "A3-AFFIRMATIVE-A_ecom_v2"),
    (19, "A3-AFFIRMATIVE-C_b2b_v2"),
    (20, "A3-DISQUALIFIER_v2"),
]


def upload(idx: int, key: str) -> tuple:
    path = GEN / f"final_{key}.png"
    if not path.exists():
        return idx, key, None, f"missing file: {path}"
    cmd = [
        "curl", "-sS",
        "-F", "reqtype=fileupload",
        "-F", "time=1h",
        "-F", f"fileToUpload=@{path}",
        "https://litterbox.catbox.moe/resources/internals/api.php",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return idx, key, None, "timeout"
    url = res.stdout.strip()
    if not url.startswith("https://"):
        return idx, key, None, f"unexpected response: {res.stdout!r} stderr={res.stderr!r}"
    return idx, key, url, None


def main():
    results = {}
    errors = []
    # Litterbox is fine with 4 concurrent uploads
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(upload, idx, key) for idx, key in PAIRS]
        for fut in as_completed(futures):
            idx, key, url, err = fut.result()
            if err:
                errors.append((idx, key, err))
                print(f"[FAIL] {idx:02d} {key}: {err}", file=sys.stderr, flush=True)
            else:
                results[key] = {"idx": idx, "url": url}
                print(f"[ok] {idx:02d} {key} -> {url}", flush=True)

    out_path = GEN.parent.parent / "setb_litterbox_urls.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\n[ok] wrote {out_path}")
    if errors:
        print(f"\n[fail] {len(errors)} uploads failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
