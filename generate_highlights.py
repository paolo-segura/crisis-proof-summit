"""Generate value stack / highlights section images for Business Unlocked summit
using Nano Banana 2 (Gemini 3.1 Flash Image).

Output: /assets/images/highlights/
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
    print(
        "ERROR: GEMINI_API_KEY not found. Expected in "
        f"{ENV_PATH}",
        file=sys.stderr,
    )
    sys.exit(1)

MODEL_ID = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")

OUTPUT_DIR = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/images/highlights")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

IMAGES = [
    {
        "filename": "highlight-blueprint.jpg",
        "label": "Cashflow Blueprint — Entrepreneur writing at conference",
        "prompt": (
            "Wide landscape photo of a focused Filipino woman entrepreneur writing in a business workbook "
            "at a professional conference, pen in hand, warm ambient lighting, shallow depth of field, "
            "authentic candid moment, editorial photography style, high quality, 16:9 aspect ratio"
        ),
    },
    {
        "filename": "highlight-presence.jpg",
        "label": "Presence Map — Collaborative strategy session",
        "prompt": (
            "Wide landscape photo of Filipino entrepreneurs collaborating around a strategy board at a "
            "business workshop, pointing at a visibility map diagram, engaged expressions, warm lighting, "
            "professional event venue, editorial photography, high quality, 16:9 aspect ratio"
        ),
    },
    {
        "filename": "highlight-sales.jpg",
        "label": "Hybrid Sales Plan — Entrepreneur on laptop/phone",
        "prompt": (
            "Wide landscape photo of a young Filipino entrepreneur working on a laptop showing e-commerce "
            "dashboards, smartphone nearby with sales notifications, modern coworking space, warm natural "
            "lighting, authentic candid shot, editorial photography, high quality, 16:9 aspect ratio"
        ),
    },
    {
        "filename": "highlight-adaptability.jpg",
        "label": "Adaptability Canvas — Brainstorming innovation session",
        "prompt": (
            "Wide landscape photo of diverse Filipino entrepreneurs in an innovation brainstorming session, "
            "sticky notes on wall, one person presenting ideas, energetic collaborative atmosphere, modern "
            "conference room, warm lighting, editorial photography, high quality, 16:9 aspect ratio"
        ),
    },
    {
        "filename": "highlight-action.jpg",
        "label": "7-Day Action Card — Accountability partner handshake",
        "prompt": (
            "Wide landscape photo of two Filipino entrepreneurs exchanging business cards and smiling at a "
            "networking event, warm ambient lighting, genuine connection moment, professional but friendly "
            "atmosphere, editorial photography style, high quality, 16:9 aspect ratio"
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
