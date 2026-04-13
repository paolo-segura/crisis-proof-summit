"""Batch 3 — Set B: urgency/scarcity + audience-qualifier hero images.

Seven editorial photojournalism heroes for the BUSINESS UNLOCKED
Filipino SME marketing kit. Nano Banana 2 (Gemini 3.1 Flash Image).

Filenames are STRICT — they map directly to the kit's overlay step.
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

MODEL_ID = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")
OUTPUT_DIR = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/generated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STYLE_ANCHOR = (
    " Editorial photojournalism, Filipino SME context, Hannah Reyes Morales / "
    "Jes Aznar aesthetic, natural grain, 85mm lens feel, shallow depth of field, "
    "no stock feel, no AI-smooth skin. NO text overlays, NO watermarks, NO "
    "signage with legible words — any text in frame must be intentionally out "
    "of focus or cropped so characters are unreadable. Palette: charcoal "
    "#1a1a2e, teal #0d9488, amber #f59e0b dominant; warm amber highlights, muted "
    "shadows. Vertical 4:5 composition (1080x1350 portrait). Massive "
    "NEGATIVE SPACE in the top 40% for headline overlay — critical."
)

SAMPLES = [
    {
        "filename": "14_A6-EARLYBIRD-LAST-48HRS.jpg",
        "prompt": (
            "Overhead flat-lay macro shot of a dark wooden desk. On it: a "
            "smartphone lying flat, screen ON, showing only a large white "
            "digital countdown display reading something like 48:00:00 "
            "(hours:minutes:seconds) — big plain numbers, NO app name, NO "
            "notification banner, NO status bar icons. Beside the phone: a "
            "half-empty cup of barako coffee, a black ballpoint pen, a small "
            "notebook (closed). Hard late-night tungsten light from the "
            "top-left creating long shadows. No hands in frame. Hero "
            "composition anchored bottom half, top 40% dark and empty."
            + STYLE_ANCHOR
        ),
    },
    {
        "filename": "15_A6-SEATS-FILLING.jpg",
        "prompt": (
            "Moodily lit small office at night — a large desktop monitor on a "
            "clean desk displays a dashboard interface. The screen content is "
            "intentionally out of focus / blurred so individual numbers and "
            "labels are unreadable, but the overall shape suggests a ticker "
            "or counter widget. The only crisp element on screen is a "
            "teal-colored progress bar about 60% filled. Low-key tungsten "
            "desk lamp, the monitor is the brightest element in frame. No "
            "person visible, no window chrome / browser tabs / text labels. "
            "Empty black office chair visible partially. Negative space top "
            "40%." + STYLE_ANCHOR
        ),
    },
    {
        "filename": "16_A6-DOORS-CLOSING.jpg",
        "prompt": (
            "Dramatic wide shot of a large pair of glass-and-metal double "
            "doors at an event venue — caught in the moment of closing, a "
            "60cm gap still open, warm golden interior lighting spilling out "
            "onto the cool blue dusk outside. Silhouette of a figure inside, "
            "out of focus, suggesting activity. Signage above the doors "
            "intentionally out of focus / cropped / unreadable. Low angle, "
            "85mm compression, rich cinematic depth. Negative space top 40% "
            "(dark dusk sky)." + STYLE_ANCHOR
        ),
    },
    {
        "filename": "17_A3-AFFIRMATIVE-B_service_v2.jpg",
        "prompt": (
            "Filipino service business owner (early 40s, masculine, work-worn) "
            "at 6 AM prepping equipment inside his small shop — turning on "
            "the coffee machine in a small eatery, or the clipper station in "
            "a barbershop, or the sewing machine at a tailor. Warm interior "
            "tungsten light, soft cool dawn light from the front window. The "
            "whole scene feels like the first breath of the day. Expression: "
            "calm, methodical, proud. Hero anchored center-right, negative "
            "space top-left 40%." + STYLE_ANCHOR
        ),
    },
    {
        "filename": "18_A3-AFFIRMATIVE-A_ecom_v2.jpg",
        "prompt": (
            "Wide pulled-back shot (camera further than batch 1 eCom shots) "
            "of a Filipina eCommerce seller (late 20s) in a small garage or "
            "converted room filled with packed orders — stacks of brown kraft "
            "mailers on the floor, shelves of inventory behind her, a folding "
            "table in the center. She's mid-motion taping a box. Harsh "
            "overhead fluorescent light. Expression: focused, tired but "
            "resolute. NOT a close-up — full-body shot showing the scale of "
            "the operation. Wider environment angle. Negative space top 40%."
            + STYLE_ANCHOR
        ),
    },
    {
        "filename": "19_A3-AFFIRMATIVE-C_b2b_v2.jpg",
        "prompt": (
            "Filipino agency owner (early 30s, crisp button-down, messenger "
            "bag) stepping onto an LRT/MRT train carriage — one foot on the "
            "train, phone held to ear mid-call, laptop under his arm. Moving "
            "commuters blurred around him. Warm station lighting contrasted "
            "with the cool fluorescent train interior. Late evening (9 PM) "
            "feel. The moment captures a man who is working RIGHT NOW, in "
            "motion. Hero anchored bottom-center, negative space top 40%."
            + STYLE_ANCHOR
        ),
    },
    {
        "filename": "20_A3-DISQUALIFIER_v2.jpg",
        "prompt": (
            "Macro close-up of a generic self-help hardcover book lying "
            "face-up on a plain wooden desk. The book cover has large printed "
            "type BUT every single letter is intentionally soft / out of "
            "focus / unreadable — blurred to the point where you can only "
            "tell there IS text without being able to read any word. A sharp "
            "bright red marker has drawn a big thick X across the entire "
            "cover (the X is the only crisp graphic element). Hard "
            "directional light from above. No other props. No side text, no "
            "spine text, no legible author line. NO motivational slogans on "
            "walls or notebooks in frame. NO vision boards, NO post-it notes "
            "with words, NO projector screens. Absolutely NO readable letters "
            "anywhere — heavy blur pass on all type, text softness +10. "
            "Forbidden: self-help slogans, motivational signage, vision "
            "boards, any rendered words like 'ABUNDANCE' or 'MANIFEST'."
            + STYLE_ANCHOR
        ),
    },
]


def generate(client: "genai.Client", sample: dict) -> Path:
    print(f"[generate] {sample['filename']} via {MODEL_ID} ...", flush=True)
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=sample["prompt"],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            out = OUTPUT_DIR / sample["filename"]
            out.write_bytes(part.inline_data.data)
            print(f"  -> {out}  ({len(part.inline_data.data):,} bytes)")
            return out
    raise RuntimeError(f"No image data returned for {sample['filename']}")


def generate_with_retry(client, sample):
    try:
        return generate(client, sample), None
    except Exception as exc:  # noqa: BLE001
        print(f"  first attempt failed: {exc}", file=sys.stderr)
        print(f"  retrying {sample['filename']} once ...", flush=True)
        time.sleep(2.0)
        try:
            return generate(client, sample), None
        except Exception as exc2:  # noqa: BLE001
            return None, str(exc2)


def main() -> int:
    client = genai.Client(api_key=API_KEY)
    results = []
    for sample in SAMPLES:
        path, err = generate_with_retry(client, sample)
        results.append((sample["filename"], path, err))
        time.sleep(1.5)

    print("\n=== Batch 3 Set B complete ===")
    ok_count = 0
    for fname, path, err in results:
        if err is None and path is not None:
            size = path.stat().st_size
            print(f"  OK   {fname}  ({size:,} bytes)")
            ok_count += 1
        else:
            print(f"  FAIL {fname}: {err}")
    print(f"\n{ok_count}/{len(results)} succeeded")
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
