"""Re-roll 4 NB2 heroes that failed QA.

- A6-DEADLINE: calendar with garbled day names → re-roll with NO text on calendar
- A3-DISQUALIFIER: stray "ABUNDANCE" ghost text on chair → re-roll without text
- A1-OUTCOME-C_b2b: stray MERALCO sticker AI-pasted on laptop → re-roll without stickers
- A6-PRICE-JUMP: literal cash hero flirts with "no price on ads" rule → concept swap to
  a calendar with May 1 circled + May 2 X'd out (keeps the deadline framing)

Each re-roll overwrites its existing sample file so compose_final.py picks it up.
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
    print("ERROR: GEMINI_API_KEY not found", file=sys.stderr)
    sys.exit(1)

MODEL_ID = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")
OUT_DIR = Path(
    "/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/generated"
)

STYLE_ANCHOR = (
    "Editorial photojournalism, Filipino SME context, Hannah Reyes Morales / "
    "Jes Aznar aesthetic, natural grain, 85mm lens feel, shallow depth of field, "
    "no stock feel, no AI-smooth skin. NO text overlays, NO watermarks, NO ghost "
    "text artifacts, NO floating letters or words anywhere in the frame, NO "
    "typography visible except where explicitly described. Palette: charcoal "
    "#1a1a2e, teal #0d9488, amber #f59e0b dominant; warm amber highlights, muted "
    "shadows. Vertical 4:5 composition (1080x1350 portrait). Massive NEGATIVE "
    "SPACE at the top 40% for headline overlay \u2014 critical."
)

FIXES = [
    {
        "id": "sample-15_A6-DEADLINE",
        "prompt": (
            f"{STYLE_ANCHOR} "
            "Close-up hero shot of a simple Filipino wall calendar hanging on a "
            "whitewashed concrete wall. A single date square \u2014 May 1 \u2014 "
            "is circled heavily in red permanent marker, forming a clear red "
            "circle around ONE date. Warm early-morning sunlight spills across "
            "the calendar from the left, casting a soft diagonal shadow. Shallow "
            "depth of field keeps the circled date pin-sharp while the rest of "
            "the month softly defocuses. CRITICAL: NO legible day-header row, NO "
            "month title text \u2014 those areas should be intentionally out of "
            "focus or cropped out so no AI-generated typography is visible. Only "
            "the red circle and the date grid of numbers are readable. Negative "
            "space at the TOP of the frame for a headline overlay."
        ),
    },
    {
        "id": "sample-21_A3-DISQUALIFIER",
        "prompt": (
            f"{STYLE_ANCHOR} "
            "Wide interior shot of an empty Filipino motivational seminar hall "
            "at end of day. Rows of empty plastic stacking chairs in a bare "
            "concrete auditorium. Dim fluorescent light overhead, cold muted "
            "palette, long shadows across the floor. A single crumpled sheet of "
            "A4 paper sits on the floor in the center of frame, slightly in focus. "
            "CRITICAL: absolutely NO text anywhere \u2014 no projected slides, "
            "no writing on chairs, no floating letters, no labels on walls. The "
            "projector screen at the front should be turned OFF / dark / blank. "
            "No AI-generated text or word artifacts anywhere in the frame. "
            "Cinematic wide shot, negative space at the top for a headline overlay."
        ),
    },
    {
        "id": "sample-7_A1-OUTCOME-C_b2b",
        "prompt": (
            f"{STYLE_ANCHOR} "
            "Filipino agency owner / coach in his early 30s, casual business "
            "shirt, closing his plain silver laptop at end of day in a small "
            "Manila co-working space. Standing at the window looking out at the "
            "Manila skyline at dusk, faint high-rise silhouettes in the distance, "
            "warm sunset band on the horizon fading into deep navy sky. His "
            "reflection softly in the glass. CRITICAL: the laptop lid must be "
            "plain brushed aluminum or silver \u2014 NO stickers, NO brand logos, "
            "NO Meralco sticker, NO fruit logos, NO text on the laptop surface "
            "whatsoever. No ghost text in the background. Quiet contemplation, "
            "forward-looking. Top 40% of the frame clear for headline overlay."
        ),
    },
    {
        "id": "sample-16_A6-PRICE-JUMP",
        "prompt": (
            f"{STYLE_ANCHOR} "
            "Tight close-up on a Filipino desk calendar, two dates side-by-side: "
            "May 1 is circled in red marker with a small gold star beside it, "
            "May 2 has a bold red X drawn through it. Shallow depth of field on "
            "the two dates, rest of the calendar softly blurred. Warm tungsten "
            "desk-lamp light from the upper-left, moody low-key exposure. A "
            "single pen rests half-in-frame beside the calendar. CRITICAL: NO "
            "legible day-header row, NO month name typography, NO ghost text "
            "anywhere \u2014 only the red circle, the gold star, and the red X "
            "should be readable. No peso bills, no cash, no money on screen. "
            "Object-driven. Top of frame clear for headline overlay."
        ),
    },
]


def generate_one(client: "genai.Client", fix: dict) -> bool:
    out = OUT_DIR / f"{fix['id']}.jpg"
    print(f"[re-roll] {fix['id']} \u2026", flush=True)
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=fix["prompt"],
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
            for part in response.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    out.write_bytes(part.inline_data.data)
                    print(f"  \u2192 {out.name}  ({len(part.inline_data.data):,} bytes)")
                    return True
            print(f"  no image data (attempt {attempt + 1})")
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR attempt {attempt + 1}: {exc}")
        time.sleep(1.0)
    print(f"  FAIL: {fix['id']}")
    return False


def main() -> int:
    client = genai.Client(api_key=API_KEY)
    ok = 0
    for fix in FIXES:
        if generate_one(client, fix):
            ok += 1
        time.sleep(0.8)
    print(f"\n=== Re-roll complete: {ok}/{len(FIXES)} OK ===")
    return 0 if ok == len(FIXES) else 1


if __name__ == "__main__":
    sys.exit(main())
