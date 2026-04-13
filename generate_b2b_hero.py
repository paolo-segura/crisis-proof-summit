"""Generate the A1-PAIN-C B2B/agency/coach hero via Nano Banana 2.

Same style family as sample 1 & 2: editorial photojournalism, Filipino SME
context, object-driven pain, negative space for a text overlay at the top.

Avatar: Filipino agency owner / coach / B2B consultant whose clients are
themselves SMEs being squeezed — so the pain here is "my clients can't pay".
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
    print("ERROR: GEMINI_API_KEY not found", file=sys.stderr)
    sys.exit(1)

MODEL_ID = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")
OUT = Path(
    "/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/generated/"
    "sample-4_A1-PAIN-C_b2b__3.1-flash-image.jpg"
)
OUT.parent.mkdir(parents=True, exist_ok=True)

PROMPT = (
    "Editorial photojournalism style, over-the-shoulder hero shot for a "
    "Philippine B2B service business / coach / agency marketing ad. Subject: "
    "a Filipino agency owner / coach in his early 30s, casual business shirt, "
    "sitting at a small co-working or home-office desk in Metro Manila, looking "
    "at his laptop with quiet worry — not cinematic despair. On the laptop "
    "screen: a messaging app with multiple client conversations visible, each "
    "ending in messages like 'next week na lang pre', 'di pa kasi nakakabayad "
    "ung client ko', 'sorry extend pa' — the messages should be readable but "
    "small, the vibe is 'all my clients are also struggling'. On the desk: a "
    "printed client proposal, a half-drunk mug of kapeng barako, a notebook "
    "with handwritten rates in peso (₱ symbols visible but numbers blurred), "
    "a silent phone showing unread notifications. Window light from the side, "
    "Manila late-afternoon warm-cool balance, slight haze. Mood: quiet "
    "helplessness, the kind where you realize the problem isn't you — it's "
    "that the whole market is squeezed. Palette: charcoal and warm amber "
    "dominate, with muted teal in the shadows. Vertical 4:5 composition (exactly "
    "1080x1350 portrait), hero subject anchored bottom-right, massive NEGATIVE "
    "SPACE in the top-left 40% for a headline overlay — critical. No text "
    "overlays, no watermarks. 85mm feel, shallow depth of field on the laptop "
    "screen, natural grain, no AI-smooth skin. Real brand logos (like iMessage, "
    "WhatsApp) are acceptable but should be partially obscured. Hannah Reyes "
    "Morales / Jes Aznar aesthetic."
)


def main() -> int:
    client = genai.Client(api_key=API_KEY)
    print(f"[generate] A1-PAIN-C B2B via {MODEL_ID} …", flush=True)
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=PROMPT,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
    except Exception as exc:
        print(f"  ERROR: {exc}", file=sys.stderr)
        return 1

    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            OUT.write_bytes(part.inline_data.data)
            print(f"  → {OUT}  ({len(part.inline_data.data):,} bytes)")
            return 0
    print("  ERROR: no image data in response", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
