"""Second re-roll for A3-DISQUALIFIER — first attempt still had ghost text.

Strategy: instead of asking for an empty motivational hall (NB2 keeps adding
motivational slogans), change the concept to a pure environmental shot with
ZERO suggestion of text/slogans. Empty classroom at dusk, pure object-driven.
"""
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

ENV = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/.env")
load_dotenv(ENV)
API_KEY = os.environ["GEMINI_API_KEY"]
MODEL_ID = "gemini-3.1-flash-image-preview"
OUT = Path(
    "/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/generated/"
    "sample-21_A3-DISQUALIFIER.jpg"
)

PROMPT = (
    "Editorial photojournalism, Filipino context, cinematic wide shot. Interior "
    "of a completely EMPTY Filipino training room / classroom at dusk. Rows of "
    "plastic stacking chairs (teal/green) facing a bare concrete wall. A single "
    "open metal folding chair in the center foreground tipped slightly askew, "
    "completely empty. Cool fluorescent overhead light, muted palette of dark "
    "teal and navy, long shadows across the floor. The wall at the front of "
    "the room is a PURE BARE CONCRETE WALL \u2014 no projector, no screen, no "
    "slideshow, no whiteboard, no poster, no framed picture, nothing with text "
    "or typography or letters anywhere. Absolutely NO signs, NO words, NO "
    "writing, NO ghost text, NO floating letters on chairs, on the floor, on "
    "the walls, on any surface. If any text appears in the image it must be "
    "removed. Pure empty-room atmosphere only. 85mm lens feel, shallow depth "
    "of field, natural grain, Roger Deakins cinematic mood. Vertical 4:5 "
    "composition (1080x1350). Top 40% of the frame is clear negative space "
    "(empty ceiling / bare wall) for a headline text overlay to be added later."
)


def main() -> int:
    client = genai.Client(api_key=API_KEY)
    for attempt in range(3):
        print(f"[retry A3-DISQUALIFIER] attempt {attempt + 1} \u2026", flush=True)
        try:
            r = client.models.generate_content(
                model=MODEL_ID,
                contents=PROMPT,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
            for part in r.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    OUT.write_bytes(part.inline_data.data)
                    print(f"  \u2192 {OUT.name}  ({len(part.inline_data.data):,} bytes)")
                    return 0
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {exc}")
        time.sleep(1.0)
    return 1


if __name__ == "__main__":
    sys.exit(main())
