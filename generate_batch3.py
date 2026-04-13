"""Batch 3 — "Who Is This For" audience-qualifier hero images.

Four editorial photojournalism heroes for the BUSINESS UNLOCKED
Filipino SME marketing kit. Nano Banana 2 (Gemini 3.1 Flash Image).
"""
import os
import sys
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

MODEL_ID = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")
OUTPUT_DIR = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/generated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STYLE_ANCHOR = (
    "Editorial photojournalism, Filipino SME context, Hannah Reyes Morales / "
    "Jes Aznar aesthetic, natural grain, 85mm lens feel, shallow depth of field, "
    "no stock feel, no AI-smooth skin. NO text overlays, NO watermarks. Real brand "
    "logos permitted but partially obscured. Palette: charcoal #1a1a2e, teal "
    "#0d9488, amber #f59e0b dominant; warm amber highlights, muted shadows. "
    "Vertical 4:5 composition (1080x1350). Massive NEGATIVE SPACE at the top 40% "
    "for headline overlay — critical."
)

SAMPLES = [
    {
        "id": "sample-18_A3-AFFIRMATIVE-B_service",
        "prompt": (
            "Hero shot for a Filipino marketing ad. Subject: a Filipino service "
            "business owner, early 40s, masculine, warm brown skin, in a simple "
            "working shirt, mid-task at his shop during opening hours — he runs "
            "either a small appliance / aircon repair shop, a sari-sari store, a "
            "food cart, or a neighborhood salon. Capture him doing the actual work: "
            "hands busy with a tool, a product, or prepping an order. A customer "
            "is just off-frame (implied by posture, not shown). His expression: "
            "determined, focused, in-the-flow — not posed, not smiling at camera, "
            "not defeated. Modest Manila streetside shop interior, authentic "
            "clutter, warm tungsten work light cutting through ambient daylight "
            "from the street. Hero anchored bottom-center of the frame, massive "
            "clean negative space in the top 40% (plain wall, ceiling, or soft "
            "out-of-focus background) for a headline overlay. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-19_A3-AFFIRMATIVE-A_ecom",
        "prompt": (
            "Wide-ish hero shot for a Filipino eCommerce marketing ad. Subject: "
            "a Filipina eCom seller, late 20s to early 30s, warm brown skin, "
            "casual home clothes, hair pulled back, sitting on the floor of a "
            "modest Manila apartment packing online orders late at night. A stack "
            "of 20+ already-packed plastic mailer / bubble wrap orders sits on "
            "the floor beside her, half-finished orders in front of her. A wall "
            "clock is clearly visible in the frame showing roughly 11 PM / near "
            "midnight. Single warm tungsten ceiling bulb, small electric fan "
            "running, a mug of kapeng barako (brewed dark coffee) going cold on "
            "the floor. Her expression: tired but determined, focused — not "
            "defeated, not crying. Real lived-in clutter, not staged. Massive "
            "clean negative space in the top 40% of the frame for a headline "
            "overlay (ceiling, wall, or dark ambient space above her). "
            + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-20_A3-AFFIRMATIVE-C_b2b",
        "prompt": (
            "Hero shot for a Filipino B2B agency marketing ad. Subject: a Filipino "
            "B2B agency owner, 30s to early 40s, warm brown skin, collared shirt "
            "or simple tee, sitting at his home office desk on a late-night client "
            "video call. He wears headphones or earbuds, is taking notes in a "
            "physical notebook with a pen in hand, laptop screen glow lighting his "
            "face from below, a single warm desk lamp as the other light source. "
            "Out the window behind him, a 9 PM Manila cityscape with faint "
            "high-rise lights visible through a reflection or soft bokeh. His "
            "expression: serious, engaged, professional — not defeated, not "
            "stressed-out. The laptop screen shows an abstracted video-call grid "
            "(no real Zoom / Meet / Teams branding — invented generic UI). Massive "
            "clean negative space in the top 40% of the frame for a headline "
            "overlay. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-21_A3-DISQUALIFIER",
        "prompt": (
            "Counter-narrative hero shot for a Filipino marketing ad — evocative "
            "of 'this is NOT what we do.' Subject: a completely empty motivational "
            "seminar / workshop room, rows and rows of empty folding chairs facing "
            "a stage at the far end. On the stage, a large projection screen "
            "displays a cheesy slogan slide reading 'MANIFEST ABUNDANCE' in "
            "generic bold sans-serif (this text IS the slide content, not an "
            "overlay — it is part of the in-world projected image). In the "
            "foreground, in sharp focus on the dusty floor between two chair rows, "
            "a single crumpled goal-setting worksheet lies abandoned. Cold, muted, "
            "dim overhead fluorescent lighting — sterile, institutional, a little "
            "sad. NO people anywhere in the frame. Color palette leans cold and "
            "muted (teal shadows, dim off-white fluorescents, hints of cold navy), "
            "with only the faintest warm amber glow from the projector. Wide shot, "
            "low angle from the floor level near the worksheet, massive clean "
            "negative space in the top 40% (ceiling, upper walls) for a headline "
            "overlay. " + STYLE_ANCHOR
        ),
    },
]


def generate(client: "genai.Client", sample: dict) -> Path:
    print(f"[generate] {sample['id']} via {MODEL_ID} ...", flush=True)
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=sample["prompt"],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            mime = part.inline_data.mime_type or "image/png"
            ext = ".png" if "png" in mime else (".jpg" if "jpeg" in mime else ".bin")
            model_tag = MODEL_ID.replace("gemini-", "").replace("-preview", "")
            out = OUTPUT_DIR / f"{sample['id']}__{model_tag}{ext}"
            out.write_bytes(part.inline_data.data)
            print(f"  -> {out}  ({len(part.inline_data.data):,} bytes)")
            return out
    raise RuntimeError(f"No image data returned for {sample['id']}")


def generate_with_retry(client, sample):
    try:
        return generate(client, sample), None
    except Exception as exc:  # noqa: BLE001
        print(f"  first attempt failed: {exc}", file=sys.stderr)
        print(f"  retrying {sample['id']} once ...", flush=True)
        try:
            return generate(client, sample), None
        except Exception as exc2:  # noqa: BLE001
            return None, str(exc2)


def main() -> int:
    client = genai.Client(api_key=API_KEY)
    results = []
    for sample in SAMPLES:
        path, err = generate_with_retry(client, sample)
        results.append((sample["id"], path, err))

    print("\n=== Batch 3 complete ===")
    ok_count = 0
    for sid, path, err in results:
        if err is None and path is not None:
            size = path.stat().st_size
            print(f"  OK   {sid}: {path.name}  ({size:,} bytes)")
            ok_count += 1
        else:
            print(f"  FAIL {sid}: {err}")
    print(f"\n{ok_count}/{len(results)} succeeded")
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
