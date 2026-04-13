"""Generate professional headshot-style photos for Business Unlocked summit speakers
and event atmosphere images using Nano Banana 2 (Gemini 3.1 Flash Image).

Output: /assets/images/speakers/
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load from crisis-proof-summit .env — same billing account as the rest of this project.
ENV_PATH = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/.env")
load_dotenv(ENV_PATH)

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print(
        "ERROR: GEMINI_API_KEY not found. Expected in "
        f"{ENV_PATH}",
        file=sys.stderr,
    )
    sys.exit(1)

MODEL_ID = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")

OUTPUT_DIR = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/images/speakers")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

IMAGES = [
    {
        "filename": "speaker-noel-wieneke.jpg",
        "label": "Jorge Noel Wieneke III — CEO/Entrepreneur",
        "prompt": (
            "Professional headshot portrait of a successful Filipino male entrepreneur in his 40s, "
            "wearing a dark polo shirt, warm confident smile, clean background, studio lighting, "
            "business magazine style photo, high quality, realistic"
        ),
    },
    {
        "filename": "speaker-nani-razon.jpg",
        "label": "Nani Razon — CEO",
        "prompt": (
            "Professional headshot portrait of a confident Filipino businesswoman in her 30s, "
            "wearing professional attire, warm smile, clean background, studio lighting, "
            "business magazine style photo, high quality, realistic"
        ),
    },
    {
        "filename": "speaker-migs-flores.jpg",
        "label": "Migs Flores — Life Coach",
        "prompt": (
            "Professional headshot portrait of an energetic Filipino male life coach in his early 30s, "
            "wearing a smart casual blazer, bright approachable smile, clean background, studio lighting, "
            "TED talk speaker style photo, high quality, realistic"
        ),
    },
    {
        "filename": "speaker-charlie-gengos.jpg",
        "label": "Charlie Gengos — Founder/Chairman",
        "prompt": (
            "Professional headshot portrait of a Filipino male entrepreneur and company founder in his late 30s, "
            "wearing a business shirt, determined confident expression, clean background, studio lighting, "
            "business profile photo, high quality, realistic"
        ),
    },
    {
        "filename": "event-atmosphere.jpg",
        "label": "Event Atmosphere — Summit Hall",
        "prompt": (
            "Wide shot of a large professional business summit in the Philippines, 2000 attendees "
            "in a modern conference hall, stage with LED screens, warm lighting, entrepreneurial energy, "
            "diverse Filipino audience taking notes, premium event atmosphere, cinematic wide angle"
        ),
    },
    {
        "filename": "event-networking.jpg",
        "label": "Networking Scene",
        "prompt": (
            "Filipino entrepreneurs networking at a premium business event, small groups talking, "
            "exchanging business cards, warm ambient lighting, professional but friendly atmosphere, "
            "diverse ages, modern venue, candid photo style"
        ),
    },
]


def generate(client: "genai.Client", image: dict) -> Path:
    filename = image["filename"]
    print(f"[generate] {image['label']} → {filename} …", flush=True)
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=image["prompt"],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )
    except Exception as exc:
        print(f"  ERROR on {filename}: {exc}", file=sys.stderr)
        raise

    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            out = OUTPUT_DIR / filename
            out.write_bytes(part.inline_data.data)
            print(f"  → {out}  ({len(part.inline_data.data):,} bytes)")
            return out

    raise RuntimeError(f"No image data returned for {filename}")


def main() -> int:
    client = genai.Client(api_key=API_KEY)

    results = []
    for image in IMAGES:
        try:
            path = generate(client, image)
            results.append((image["filename"], str(path), None))
        except Exception as exc:  # noqa: BLE001
            results.append((image["filename"], None, str(exc)))

    print("\n=== Generation complete ===")
    ok_count = 0
    for filename, path, err in results:
        if err is None:
            print(f"  OK  {filename}  {path}")
            ok_count += 1
        else:
            print(f"  FAIL  {filename}: {err}")

    print(f"\n{ok_count}/{len(IMAGES)} images generated successfully.")
    return 0 if ok_count == len(IMAGES) else 1


if __name__ == "__main__":
    sys.exit(main())
