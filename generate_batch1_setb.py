"""Batch 1 Set B: Generate 6 alternate hero images for BUSINESS UNLOCKED.

Set B reuses the same A1 PAIN/OUTCOME slots as Set A but with fundamentally
different scenes (different camera angles, props, settings, moments). All
images go through Nano Banana 2 (gemini-3.1-flash-image-preview), saved as
{NN}_{variant_key}.jpg in assets/generated/. NO baked text — headlines are
overlaid later in Pillow.
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
    "no stock feel, no AI-smooth skin. NO text overlays, NO watermarks, NO "
    "signage with legible words — any text in frame must be intentionally out "
    "of focus or cropped so characters are unreadable. Real brand logos allowed "
    "but partially obscured. Palette: charcoal #1a1a2e, teal #0d9488, amber "
    "#f59e0b dominant; warm amber highlights, muted shadows. Vertical 4:5 "
    "composition (1080x1350 portrait). Massive NEGATIVE SPACE in the top 40% "
    "for headline overlay — critical."
)

HEROES = [
    {
        "filename": "01_A1-PAIN-B_service_v2.jpg",
        "prompt": (
            "Filipino service business owner (early 40s, masculine, work-worn, "
            "warm brown skin) standing just inside the entrance of his small "
            "shop — a repair shop, printing press, or laundromat — looking "
            "down at his phone screen with visible concern. The phone shows a "
            "weather warning app (content intentionally blurred so no legible "
            "text). Outside the shop window: the first heavy drops of tropical "
            "rain hitting the pavement, a half-rolled-down metal awning, an "
            "overcast sky going dim. Overhead tungsten light glowing warm "
            "inside, cold blue-grey storm light outside creating a split color "
            "contrast. He grips the phone tightly. Hero anchored bottom-right. "
            "Negative space top-left 40%. " + STYLE_ANCHOR
        ),
    },
    {
        "filename": "02_A1-PAIN-A_ecom_v2.jpg",
        "prompt": (
            "Young Filipina eCommerce seller (mid-20s, simple t-shirt, messy "
            "ponytail, no makeup) at a cluttered home desk — leaning forward "
            "toward an open laptop showing a TikTok Shop seller dashboard "
            "(screen content intentionally out of focus / unreadable blur). "
            "Her fingers hover over the trackpad mid-refresh gesture, eyebrows "
            "raised with quiet stress. Empty coffee mug, printer with no "
            "waybills coming out, small electric fan. Late afternoon Manila "
            "light through jalousie windows, warm orange cast on her face, "
            "cool blue on the walls. Hero anchored center-right, negative "
            "space top-left 40%. " + STYLE_ANCHOR
        ),
    },
    {
        "filename": "03_A1-PAIN-C_b2b_v2.jpg",
        "prompt": (
            "Filipino agency owner (early 30s, casual button-down shirt, warm "
            "brown skin, slightly tired eyes) sitting alone at a small "
            "co-working desk at night, staring silently at his laptop screen. "
            "On the screen: a chat interface window (ChatGPT/Claude style) "
            "with a long text response visible but intentionally unreadable / "
            "blurred. Next to the laptop, a printed client deliverable — the "
            "two side-by-side suggest the AI just produced something that "
            "matches his work. Flat expression, hand on chin. Dim overhead "
            "lights, cool blue screen glow on his face. Negative space "
            "top-left 40%. " + STYLE_ANCHOR
        ),
    },
    {
        "filename": "04_A1-OUTCOME-B_service_v2.jpg",
        "prompt": (
            "Filipino small business owner (early 40s, masculine, confident) "
            "standing in front of a brand-new second-location storefront at "
            "sunrise — ribbon-cutting moment, or just after. Warm golden hour "
            "light bathing the facade, signage above is intentionally out of "
            "focus / blurred so no letters readable. Pride in his posture, "
            "tape measure in back pocket, keys in hand. Faint crowd of family "
            "or staff blurred in the background. Empty street suggesting early "
            "morning. Hero anchored bottom-center-right, massive negative "
            "space in the top-left 40%. " + STYLE_ANCHOR
        ),
    },
    {
        "filename": "05_A1-OUTCOME-A_ecom_v2.jpg",
        "prompt": (
            "Filipina eCommerce seller (late 20s, casual home clothes, calm "
            "focused expression) at a home desk with THREE devices visible: "
            "laptop (center), tablet (left), phone (right). Each screen shows "
            "a different sales dashboard (content intentionally blurred / "
            "unreadable). A tiny notification popup visible on the phone "
            "screen, similar on the laptop. She's glancing at the phone while "
            "her hand rests on the laptop trackpad. Warm tungsten desk lamp, "
            "soft pink-gold afternoon light from a window, calm competent "
            "energy (not frantic). Negative space top-left 40%. " + STYLE_ANCHOR
        ),
    },
    {
        "filename": "06_A1-OUTCOME-C_b2b_v2.jpg",
        "prompt": (
            "Filipino agency owner (early 30s, crisp button-down shirt, "
            "confident posture) seated across a modern small office table, "
            "signing a printed document with a heavy ballpoint pen. On the "
            "table between him and the (out-of-frame) client: a rate card "
            "printed on clean white paper (numbers intentionally out of focus "
            "/ blurred), a fountain pen box, two cups of kapeng barako. Soft "
            "natural window light from the left, warm wood desk surface, "
            "modern minimalist office. A slight smile. Hero anchored "
            "bottom-right, negative space top-left 40%. " + STYLE_ANCHOR
        ),
    },
]


def generate_one(client, hero, attempt=1):
    print(f"[{hero['filename']}] attempt {attempt} via {MODEL_ID} ...", flush=True)
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
            out = OUTPUT_DIR / hero["filename"]
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
            results.append((hero["filename"], str(out), size, None))
        except Exception as exc:
            print(f"  FAIL {hero['filename']}: {exc}", file=sys.stderr)
            results.append((hero["filename"], None, 0, str(exc)))
        # Gentle pacing between calls
        time.sleep(1.5)

    print("\n=== Batch 1 Set B complete ===")
    for fname, path, size, err in results:
        if err:
            print(f"  {fname}: FAIL — {err}")
        else:
            print(f"  {fname}: {size:,} bytes  {path}")
    return 0 if all(err is None for _, _, _, err in results) else 1


if __name__ == "__main__":
    sys.exit(main())
