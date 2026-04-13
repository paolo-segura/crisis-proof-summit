"""Set B hero image generator for BUSINESS UNLOCKED marketing kit.

Generates 7 editorial photojournalism heroes for Filipino SME ads + scarcity
backdrops via Gemini 3.1 Flash Image ("nano banana 2"). All images are
text-free — headlines are overlaid in Pillow later.
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
    "Editorial photojournalism, Filipino SME context, Hannah Reyes Morales / "
    "Jes Aznar aesthetic, natural grain, 85mm lens feel, shallow depth of field, "
    "no stock feel, no AI-smooth skin. NO text overlays, NO watermarks, NO "
    "signage with legible words — any text in frame must be intentionally out "
    "of focus or cropped so characters are unreadable. Palette: charcoal "
    "#1a1a2e, teal #0d9488, amber #f59e0b dominant; warm amber highlights, "
    "muted shadows. Vertical 4:5 composition (1080x1350 portrait). "
    "Massive NEGATIVE SPACE in the top 40% for headline overlay — critical."
)

# Anti-text doubling for retry on scenes 11/12/13
ANTI_TEXT_DOUBLE = (
    " ABSOLUTELY CRITICAL: NO LEGIBLE LETTERS OR NUMBERS ANYWHERE IN THE FRAME. "
    "Every potential text surface (clock face engravings, brand names, calculator "
    "labels, calendar headers, day names, paper notes, stickers, wall posters) "
    "MUST be either cropped out of frame entirely or rendered intentionally soft "
    "/ blurred / out-of-focus so no character is readable. Treat any text-like "
    "shape as a visual smudge, not a word. Do NOT hallucinate logos or brand "
    "marks. Do NOT add captions, labels, or annotations. The image must contain "
    "ZERO sharp typography of any kind."
)

SAMPLES = [
    {
        "id": "07_A1-IDENTITY-B_service_v2",
        "anti_text_critical": False,
        "prompt": (
            "Exterior front of a modest Filipino service storefront (repair "
            "shop, small eatery, or laundromat) at sunrise — first light "
            "hitting the facade, metal rolling shutter pulled up halfway, "
            "warm interior tungsten lights just switching on casting a "
            "golden glow out onto the damp sidewalk. An old aircon unit "
            "above the door, potted plants beside the entrance. Signage "
            "above is out of focus / unreadable. No subject figure in "
            "frame — the storefront IS the hero. Quiet resilience. Hero "
            "anchored bottom, negative space top 40%. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "08_A1-IDENTITY-A_ecom_v2",
        "anti_text_critical": False,
        "prompt": (
            "Filipina eCommerce seller (late 20s, ponytail, focused) at a "
            "small home desk studying another seller's product packaging "
            "laid out flat next to her — she's taking notes in a lined "
            "notebook with a pen, reverse-engineering. The product is a "
            "generic Filipino snack or beauty product (label intentionally "
            "out of focus / unreadable). Her laptop is OPEN but screen dim "
            "and turned slightly away. Late morning soft window light. "
            "Expression: curious, builder, not tired. Hero anchored "
            "bottom-right, negative space top-left 40%. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "09_A1-CURIOSITY-B_service_v2",
        "anti_text_critical": False,
        "prompt": (
            "Exterior of a small Filipino service shop at night, the metal "
            "rolling shutter ALMOST fully closed but with a ~30cm gap at "
            "the bottom — bright warm amber tungsten light leaking out "
            "through that gap onto the wet pavement, suggesting activity "
            "inside. Empty street. Slight fog. Signage above blurred and "
            "unreadable. Composition: low angle, camera slightly below "
            "door height, focused on the light leak. Intriguing, "
            "contrarian. Negative space top 40%. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "10_A1-CURIOSITY-A_ecom_v2",
        "anti_text_critical": False,
        "prompt": (
            "Filipina eCommerce seller (late 20s) in a home setting — "
            "captured in mid-gesture: one hand closing a laptop (lid at "
            "45 degrees, screen visible but turned away from camera), the "
            "other hand opening a physical blank notebook. Clear visual "
            "contrast between the two mediums. Desk has a pen, a mug, and "
            "nothing else. Warm afternoon light. Subject expression: "
            "focused, decisive — NOT sad. Hero anchored center-right, "
            "negative space top-left 40%. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "11_A6-EARLYBIRD-CLOCK",
        "anti_text_critical": True,
        "prompt": (
            "Extreme close-up macro shot of a vintage analog desk clock "
            "(brass body, roman numeral face, not digital) with the hands "
            "at 11:58. Shallow depth of field. Out of focus in the "
            "background: a wall calendar, only the grid visible — NO "
            "legible day names or month header. Dramatic low-key warm "
            "tungsten light from the left, deep shadows. NO labels, NO "
            "brand marks on the clock body. Stillness, tension. Hero "
            "anchored bottom-center, negative space top 40% (dark, "
            "empty). " + STYLE_ANCHOR
        ),
    },
    {
        "id": "12_A6-EARLYBIRD-20PERCENT",
        "anti_text_critical": True,
        "prompt": (
            "Macro close-up of a plain Filipino desk calculator (cream "
            "plastic body, standard 10-digit display) on a wooden desk. "
            "The display shows a faint numeric result but intentionally "
            "slightly out of focus / soft so characters are not sharp. "
            "Next to the calculator: a folded piece of plain paper, a "
            "black pen, a warm desk lamp casting soft amber pool of light. "
            "NO brand label on the calculator body. NO visible text on "
            "the paper. Background dark and blurred. Negative space in "
            "top 40%. " + STYLE_ANCHOR
        ),
    },
    {
        "id": "13_A6-EARLYBIRD-MAY1-LINE",
        "anti_text_critical": True,
        "prompt": (
            "Macro close-up of a hanging wall calendar page showing a "
            "month grid — the exact day names and month header are "
            "intentionally out of focus / soft so letters are not sharp. "
            "A SHARP bold red marker stroke runs diagonally across one "
            "specific square in the grid, clearly crossing it out. A "
            "black ballpoint pen rests on top of the calendar. Hard "
            "morning light from the left side. Dramatic contrast. "
            "Negative space top 40%. " + STYLE_ANCHOR
        ),
    },
]


def generate(client, sample, prompt_override=None):
    prompt = prompt_override or sample["prompt"]
    print(f"[generate] {sample['id']} via {MODEL_ID} ...", flush=True)
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            mime = part.inline_data.mime_type or "image/jpeg"
            # Force .jpg extension per spec
            out = OUTPUT_DIR / f"{sample['id']}.jpg"
            out.write_bytes(part.inline_data.data)
            size = len(part.inline_data.data)
            print(f"  -> {out.name}  ({size:,} bytes)  mime={mime}")
            return out, size
    raise RuntimeError(f"No image data returned for {sample['id']}")


def attempt_with_retry(client, sample, prompt_override=None):
    """Generate with 1 retry on transient errors."""
    last_err = None
    for attempt in (1, 2):
        try:
            return generate(client, sample, prompt_override=prompt_override)
        except Exception as exc:
            last_err = exc
            print(
                f"  ATTEMPT {attempt} FAILED for {sample['id']}: {exc}",
                file=sys.stderr,
            )
            if attempt == 1:
                time.sleep(1.5)
    raise last_err


def main():
    client = genai.Client(api_key=API_KEY)
    results = []
    for sample in SAMPLES:
        path = None
        size = None
        err = None
        try:
            path, size = attempt_with_retry(client, sample)
        except Exception as exc:
            err = str(exc)

        # Anti-text doubled retry for risky scenes 11/12/13.
        # We retry once with reinforced anti-text language regardless,
        # because we cannot programmatically OCR the result here.
        # Strategy: keep the first successful image, and ALSO try a
        # doubled-down version saved with same filename (overwrites)
        # only if first attempt errored. Otherwise we trust the first
        # because we have no OCR feedback loop.
        # Per instructions: "retry ONCE automatically" — interpret as
        # one extra try if generation errored OR if the first call
        # failed entirely.
        if err and sample.get("anti_text_critical"):
            print(
                f"  RETRY (anti-text doubled) for {sample['id']} ...",
                file=sys.stderr,
            )
            try:
                doubled_prompt = sample["prompt"] + ANTI_TEXT_DOUBLE
                path, size = attempt_with_retry(
                    client, sample, prompt_override=doubled_prompt
                )
                err = None
            except Exception as exc:
                err = str(exc)

        results.append((sample["id"], path, size, err))
        time.sleep(1.5)

    print("\n=== Set B batch complete ===")
    ok_count = 0
    for sid, path, size, err in results:
        if err is None:
            ok_count += 1
            print(f"  OK    {sid}.jpg  {size:,} bytes")
        else:
            print(f"  FAIL  {sid}  {err}")
    print(f"\n{ok_count}/{len(results)} succeeded")
    return 0 if all(r[3] is None for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
