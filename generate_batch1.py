"""Batch 1: Generate 6 hero images for BUSINESS UNLOCKED marketing kit.

Uses Nano Banana 2 (gemini-3.1-flash-image-preview) to produce editorial
photojournalism heroes for Filipino SME avatars (service, eCom, b2b).
Saves each as <id>.jpg in assets/generated/. Sequential, with 1 retry on
transient errors. NO text overlays baked in — headlines go on in Canva.
"""
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

ENV_PATH = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/.env")
load_dotenv(ENV_PATH)

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print(f"ERROR: GEMINI_API_KEY not found in {ENV_PATH}", file=sys.stderr)
    sys.exit(1)

MODEL_ID = "gemini-3.1-flash-image-preview"
OUTPUT_DIR = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/generated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STYLE_ANCHOR = (
    "Editorial photojournalism, Filipino SME context, Hannah Reyes Morales / "
    "Jes Aznar aesthetic, natural grain, 85mm lens feel, shallow depth of field, "
    "no stock feel, no AI-smooth skin. NO text overlays, NO watermarks. Real "
    "brand logos (Meralco, Shell, Shopee, Lazada, TikTok Shop) are permitted "
    "but can be partially obscured. Palette: charcoal #1a1a2e, teal #0d9488, "
    "amber #f59e0b dominant; warm amber highlights, muted shadows. Vertical "
    "4:5 composition (1080x1350 portrait). Massive NEGATIVE SPACE at the top "
    "40% for headline overlay — critical."
)

HEROES = [
    {
        "id": "sample-5_A1-OUTCOME-B_service",
        "prompt": (
            "Filipino small business owner (early 40s, masculine, work-worn, "
            "warm brown skin) at his small service business storefront — a "
            "modest sari-sari store or repair shop or barbershop — at dawn. "
            "He is turning on the lights and opening the metal rolling "
            "shutter, expression of quiet determination. NOT desperation — "
            "he is still standing, still showing up. Warm amber tungsten "
            "light glowing from inside the shop, cool navy dawn light on the "
            "street behind him. Hero subject anchored in the bottom-right "
            "third of the frame; negative space in the top-left 40% for a "
            "headline overlay. Honest, weathered, hopeful. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-6_A1-OUTCOME-A_ecom",
        "prompt": (
            "Young Filipina eCommerce seller (late 20s, ponytail, casual home "
            "clothes like a plain t-shirt) in a cluttered home office, calmly "
            "packing orders into bubble-wrap pouches with a clear, focused "
            "expression. Stack of printed waybills, roll of packing tape, "
            "ceramic mug of kapeng barako, laptop visible but not dominant in "
            "the frame. Afternoon Manila light streaming in through jalousie "
            "(louver) windows. Quiet focus — not slumped, not exhausted. Hero "
            "anchored bottom-right, negative space top-left 40% for headline. "
            + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-7_A1-OUTCOME-C_b2b",
        "prompt": (
            "Filipino agency owner or coach (early 30s, casual business "
            "shirt, warm brown skin) closing his laptop at end of day in a "
            "small Manila co-working space. Standing at the window looking "
            "out at the Manila skyline at dusk. Blurred high-rise skyline in "
            "the background, faint reflection of his silhouette in the glass. "
            "Contemplative, not defeated — a man who just decided something. "
            "Negative space in the top-left 40% for a headline overlay. "
            + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-8_A1-IDENTITY-B_service",
        "prompt": (
            "Close-up hero shot of a Filipino small business owner's cash "
            "drawer half-open at the counter of his modest service shop. "
            "Strong weathered masculine hands visible counting small peso "
            "bills and coins — 20s, 50s, 100s, a few coins. NO face visible "
            "in frame — only the hands and the cash drawer dominate. "
            "Tungsten light from directly above, deep shadows around the "
            "edges, a single warm golden highlight on the cash. Determined, "
            "not sad — the hands of someone who works. Negative space in the "
            "top-left 40% for a headline overlay. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-9_A1-IDENTITY-A_ecom",
        "prompt": (
            "Young Filipina eCommerce seller (late 20s, ponytail, casual home "
            "clothes) reviewing a handwritten checklist of daily tasks, pen "
            "in hand, brow slightly furrowed with focus. Beside her: a neat "
            "stack of 10 to 15 packed orders ready to ship (brown kraft "
            "mailers, bubble pouches). Morning Manila light coming through a "
            "window, small electric fan visible on the desk. Subtle pride, "
            "quiet competence — NOT exhaustion. Hero anchored center-right, "
            "negative space top-left for a headline overlay. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-10_A1-IDENTITY-C_b2b",
        "prompt": (
            "Filipino agency owner (early 30s, casual business shirt) writing "
            "a client plan on an open notebook at his desk, pen in hand, "
            "intense focus. Behind him, softly out of focus: a whiteboard "
            "with hand-drawn framework diagrams (boxes, arrows). On the desk: "
            "a half-finished ceramic mug of kapeng barako, a closed laptop. "
            "Determined, in flow. Top of the canvas clear for a headline "
            "overlay — negative space in the top 40%. " + STYLE_ANCHOR
        ),
    },
]


def generate_one(client, hero, attempt=1):
    print(f"[{hero['id']}] attempt {attempt} via {MODEL_ID} ...", flush=True)
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=hero["prompt"],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )
    except Exception as exc:
        if attempt == 1:
            print(f"  transient error: {exc} — retrying once", file=sys.stderr)
            time.sleep(1.5)
            return generate_one(client, hero, attempt=2)
        raise

    for part in response.candidates[0].content.parts:
        inline = getattr(part, "inline_data", None)
        if inline and inline.data:
            out = OUTPUT_DIR / f"{hero['id']}.jpg"
            out.write_bytes(inline.data)
            size = len(inline.data)
            print(f"  OK -> {out.name} ({size:,} bytes)")
            return out, size, None

    # No image in response — retry once
    if attempt == 1:
        print("  no image returned — retrying once", file=sys.stderr)
        time.sleep(1.5)
        return generate_one(client, hero, attempt=2)
    raise RuntimeError("no image data returned after retry")


def main():
    client = genai.Client(api_key=API_KEY)
    results = []
    for hero in HEROES:
        try:
            out, size, _ = generate_one(client, hero)
            results.append((hero["id"], str(out), size, None))
        except Exception as exc:
            print(f"  FAIL {hero['id']}: {exc}", file=sys.stderr)
            results.append((hero["id"], None, 0, str(exc)))
        # Gentle pacing between calls
        time.sleep(0.8)

    print("\n=== Batch 1 complete ===")
    for rid, path, size, err in results:
        if err:
            print(f"  {rid}: FAIL — {err}")
        else:
            print(f"  {rid}: {size:,} bytes  {path}")
    return 0 if all(err is None for _, _, _, err in results) else 1


if __name__ == "__main__":
    sys.exit(main())
