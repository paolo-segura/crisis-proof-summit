"""Batch 2 hero image generator for BUSINESS UNLOCKED marketing kit.

Generates 7 editorial photojournalism heroes for Filipino SME ads + scarcity backdrops
via Gemini 3.1 Flash Image ("nano banana 2").
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
    print(f"ERROR: GEMINI_API_KEY not found in {ENV_PATH}.", file=sys.stderr)
    sys.exit(1)

MODEL_ID = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")
OUTPUT_DIR = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/generated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STYLE_ANCHOR = (
    "Editorial photojournalism / cinematic wide shot, Filipino context, "
    "Hannah Reyes Morales / Jes Aznar / Roger Deakins aesthetic, natural grain, "
    "shallow depth of field, no stock feel, no AI-smooth skin. NO text overlays, "
    "NO watermarks. Real brand logos (Meralco, Shell, Shopee, Lazada, TikTok Shop) "
    "are permitted but can be partially obscured. Palette: charcoal #1a1a2e, "
    "teal #0d9488, amber #f59e0b dominant; warm amber highlights, muted "
    "shadows. Vertical 4:5 composition (1080x1350) for ALL images. Massive "
    "NEGATIVE SPACE at the top 40% — critical."
)

SAMPLES = [
    {
        "id": "sample-11_A1-CURIOSITY-B_service",
        "prompt": (
            "Filipino sari-sari store or service shop at night. Lights blazing warm "
            "amber from inside the shop against a deep navy street exterior. A single "
            "silhouetted figure is visible inside, working — back-lit, faceless, "
            "mysterious. Moody, atmospheric, 'what's he doing in there' curiosity "
            "vibe. Pure atmosphere, NO faces, NO identifiable features. Negative "
            "space concentrated top-left of frame for headline overlay. Cinematic "
            "wide shot, shot from across the street, shallow DOF on the shop "
            "facade. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-12_A1-CURIOSITY-A_ecom",
        "prompt": (
            "Top-down flat lay of a Filipino eCommerce seller's desk. Objects: a "
            "CLOSED MacBook (lid down, not open), a ceramic mug half-full of kapeng "
            "barako, a few flat plastic packing pouches, a smartphone face-up "
            "showing a single notification on its lock screen, a ballpoint pen "
            "resting on an open notebook, a short stack of printed waybills, a "
            "small potted plant in the corner. Warm amber late-afternoon light "
            "raking in from one side casting long soft shadows across the wooden "
            "desk surface. NO hands, NO faces — pure object storytelling, curiosity-"
            "driving. Negative space at the top of the frame. Natural grain, "
            "shallow DOF. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-13_A1-CURIOSITY-C_b2b",
        "prompt": (
            "Close-up hero shot of a Filipino agency owner's hand (warm brown skin, "
            "mid-30s, subtle, no jewelry) reaching for a specific leather-bound "
            "notebook on a wooden desk. Only the hand, the notebook, and a partial "
            "desk surface are visible — nothing else. Moody side-light from a "
            "window raking across the notebook spine. Shallow depth of field "
            "focused on the notebook spine texture. Cinematic mystery, quiet "
            "decisive moment. Negative space at the top 40% of frame. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-14_A6-SEATS",
        "prompt": (
            "Interior of an empty Manila conference hall / training center similar "
            "to the Philippine Trade Training Center (PTTC) Global MSME Academy. "
            "Long rows of empty chairs stretching toward a stage. One section of "
            "seats illuminated by a single theatrical stage spotlight cutting "
            "through atmospheric haze. Tall windows at the back showing dusk blue "
            "hour sky outside. Cinematic wide shot, symmetrical perspective, "
            "massive negative space at the top of the frame for a '2,000 SEATS' "
            "headline overlay. Absolutely NO people in frame. Quiet anticipation "
            "mood. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-15_A6-DEADLINE",
        "prompt": (
            "Close-up of a Filipino wall calendar showing May 2026. The date 'May "
            "1, 2026' is clearly circled in red marker with a peso sign (₱) "
            "notation scrawled beside it. Early morning warm amber light pouring "
            "in from a window off-frame casting a soft directional glow across "
            "the paper. Shallow depth of field focused tightly on the circled "
            "date, rest of the calendar gently out of focus. Pure object-driven "
            "storytelling, NO hands, NO people. Negative space at the top of "
            "frame for headline. Natural paper grain texture visible. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-16_A6-PRICE-JUMP",
        "prompt": (
            "Close-up of Filipino 1000-peso bills (blue) and 500-peso bills "
            "(yellow) fanned out on a worn wooden desk surface beside a small "
            "calculator and a black ballpoint pen. Warm tungsten light from one "
            "side creating deep amber highlights on the bill edges and muted teal "
            "shadows in the creases. Shallow DOF focused on the fanned bills, "
            "calculator slightly out of focus in the background. NO hands, NO "
            "faces. Evocative of 'savings' and decisive financial moment. "
            "Negative space at the top 40% of frame. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "sample-17_A6-LAST-CHANCE",
        "prompt": (
            "Wide cinematic shot of a Manila event venue's main entrance door "
            "slowly closing. Warm amber interior light spilling out through the "
            "narrowing gap of the closing door onto the dark pavement. Dusk blue "
            "hour sky visible outside. A blurred banner reading 'BUSINESS UNLOCKED' "
            "is visible on the venue wall but significantly out of focus "
            "in the background. Cinematic last-chance mood — the viewer is "
            "arriving too late. Absolutely NO people visible. Massive negative "
            "space at the top of the frame for a headline. Shallow DOF on the "
            "door gap. " + STYLE_ANCHOR
        ),
    },
]


def generate(client, sample):
    print(f"[generate] {sample['id']} via {MODEL_ID} ...", flush=True)
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=sample["prompt"],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            mime = part.inline_data.mime_type or "image/png"
            ext = ".png" if "png" in mime else (".jpg" if "jpeg" in mime else ".bin")
            out = OUTPUT_DIR / f"{sample['id']}{ext}"
            out.write_bytes(part.inline_data.data)
            size = len(part.inline_data.data)
            print(f"  -> {out.name}  ({size:,} bytes)")
            return out, size
    raise RuntimeError(f"No image data returned for {sample['id']}")


def main():
    client = genai.Client(api_key=API_KEY)
    results = []
    for sample in SAMPLES:
        path = None
        size = None
        err = None
        for attempt in (1, 2):
            try:
                path, size = generate(client, sample)
                err = None
                break
            except Exception as exc:
                err = str(exc)
                print(f"  ATTEMPT {attempt} FAILED for {sample['id']}: {exc}", file=sys.stderr)
                if attempt == 1:
                    time.sleep(1.5)
        results.append((sample["id"], path, size, err))

    print("\n=== Batch 2 complete ===")
    for sid, path, size, err in results:
        if err is None:
            print(f"  OK    {sid}  {size:,} bytes  {path.name}")
        else:
            print(f"  FAIL  {sid}  {err}")
    return 0 if all(r[3] is None for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
