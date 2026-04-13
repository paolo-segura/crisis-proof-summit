"""One-shot retry for scene 20 with maximally aggressive anti-text guardrails.

Initial pass had legible 'SELF HELP BOOK' / 'SELF-HELP' text leak. This re-roll
removes the book entirely as a typographic surface and reframes the cover as
a textureless solid color block, with the red X being the only graphic.
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
MODEL_ID = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")
OUTPUT_DIR = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/generated")

STYLE_ANCHOR = (
    " Editorial photojournalism, Filipino SME context, Hannah Reyes Morales / "
    "Jes Aznar aesthetic, natural grain, 85mm lens feel, shallow depth of field, "
    "no stock feel, no AI-smooth skin. NO text overlays, NO watermarks, NO "
    "signage with legible words — any text in frame must be intentionally out "
    "of focus or cropped so characters are unreadable. Palette: dark navy "
    "#1a1a2e, teal #0d9488, amber #f59e0b dominant; warm highlights, muted "
    "teal shadows. Vertical 4:5 composition (1080x1350 portrait). Massive "
    "NEGATIVE SPACE in the top 40% for headline overlay — critical."
)

PROMPT = (
    "Macro close-up of a generic hardcover book lying face-up on a plain "
    "wooden desk. CRITICAL: the book cover is COMPLETELY BLANK — solid dark "
    "navy cloth texture, NO printed letters at all, NO title, NO author name, "
    "NO subtitle, NO publisher logo, NO spine text, NO sticker, NO label of "
    "any kind. Just a smooth blank navy hardcover. A sharp bright red marker "
    "has drawn a big thick X across the entire blank cover (the X is the "
    "ONLY graphic element on the book). Hard directional light from above "
    "casting strong shadows. The book sits alone on raw wood — NO other "
    "props, NO notebook, NO pen, NO post-its, NO papers, NO walls visible "
    "in background, NO posters, NO vision boards. ABSOLUTELY ZERO READABLE "
    "LETTERS ANYWHERE in the entire frame. Treat any text as forbidden. "
    "Forbidden words to never render: 'SELF HELP', 'ABUNDANCE', 'MANIFEST', "
    "'MINDSET', 'GROWTH', 'SUCCESS', or any English or Tagalog word. Heavy "
    "blur pass on anything text-like. Text softness +10. If you are tempted "
    "to add a title, instead make the cover even more blank. The book is a "
    "PROP, not a publication." + STYLE_ANCHOR
)


def main() -> int:
    client = genai.Client(api_key=API_KEY)
    print(f"[retry] 20_A3-DISQUALIFIER_v2.jpg via {MODEL_ID} ...", flush=True)
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=PROMPT,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            out = OUTPUT_DIR / "20_A3-DISQUALIFIER_v2.jpg"
            out.write_bytes(part.inline_data.data)
            print(f"  -> {out}  ({len(part.inline_data.data):,} bytes)")
            return 0
    print("ERROR: no image data returned", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
