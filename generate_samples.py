"""Nano Banana (Gemini 2.5 Flash Image) sample generator for BUSINESS UNLOCKED marketing kit.

Generates 3 sample hero images per the default visual direction:
- Sample 1: A1-PAIN-B (Service business avatar) — Meralco bill pain
- Sample 2: A1-PAIN-A (eCom seller avatar)     — Shopee dashboard pain
- Sample 3: A11 D-30 Countdown                   — Gas station dusk atmosphere

Approach: nano banana generates hero imagery only. Brand text/logos/CTAs
are overlaid in Canva later via perform-editing-operations.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load the Gemini key from the crisis-proof-summit .env (client-specific — ExpoU/Gencys)
# DO NOT fall back to other clients' keys (e.g. Furvana) — that's a billing attribution bug.
ENV_PATH = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/.env")
load_dotenv(ENV_PATH)

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print(
        "ERROR: GEMINI_API_KEY not found. Expected in "
        f"{ENV_PATH}. Do NOT reuse a key from another client project.",
        file=sys.stderr,
    )
    sys.exit(1)

# Model ID — Paolo's production pick: Nano Banana 2 (Gemini 3.1 Flash Image).
# Alternatives: "gemini-3-pro-image-preview" (NB Pro, highest quality / slowest)
# or "gemini-2.5-flash-image" (NB1, original / weakest). Override via GEMINI_IMAGE_MODEL.
# If this errors with 404, run with LIST_MODELS=1 to rediscover available IDs.
MODEL_ID = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")

OUTPUT_DIR = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/generated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Sample prompts (hero imagery only — no brand text, no captions baked in)
# ---------------------------------------------------------------------------
SAMPLES = [
    {
        "id": "sample-1_A1-PAIN-B_service",
        "asset": "Asset 1 PAIN — Service business avatar",
        "aspect": "4:5",
        "prompt": (
            "Editorial photojournalism style, close-up hero shot for a Filipino "
            "small business marketing ad. Subject: a Filipino small business "
            "owner's hand (40s, work-worn, masculine, warm brown skin, slightly "
            "greasy from a long shift) holding up a crumpled Meralco electricity "
            "bill where the peso amount is blurred but visibly much higher than "
            "expected. On the wooden table below, partially visible: a diesel "
            "pump receipt and a small ledger notebook. Dramatic side-lit by a "
            "single warm window, deep shadows, shallow depth of field, 85mm lens "
            "feel. Background is a modest Filipino sari-sari store interior, "
            "softly out of focus, with hints of teal and navy in the shadows and "
            "a warm golden highlight on the bill. Mood: quiet desperation, not "
            "cinematic melodrama. Photojournalist Hannah Reyes Morales aesthetic. "
            "No text, no watermarks, no logos, no faces in frame. Vertical 4:5 "
            "composition with negative space at the top 40% for a headline overlay. "
            "Shot on Leica, natural grain, no AI-smooth skin."
        ),
    },
    {
        "id": "sample-2_A1-PAIN-A_ecom",
        "asset": "Asset 1 PAIN — eCom seller avatar",
        "aspect": "4:5",
        "prompt": (
            "Editorial photojournalism, over-the-shoulder hero shot for a "
            "Philippine eCommerce seller marketing ad. Subject: a young Filipina "
            "business owner (late 20s, casual home clothes, ponytail, warm brown "
            "skin) sitting at a small cluttered home office desk looking at a "
            "laptop screen. On the laptop: an abstracted online marketplace "
            "seller dashboard (no real Shopee or Lazada branding — invented "
            "generic 'seller center' UI with orange-red accent) showing a "
            "prominent '0 ORDERS' indicator and a list of deductions in peso "
            "symbols. Her posture: slumped forward, one hand on her forehead, "
            "quiet frustration, not crying. Desk details: a half-empty mug of "
            "kapeng barako, a small electric fan, stacked packing pouches ready "
            "for shipping, afternoon Manila light through a jalousie window. "
            "Mood: muted, honest, photojournalism — not stock. Color palette: "
            "warm ambers and muted teals in the shadows. No text overlays, no "
            "logos, no brand names visible. Vertical 4:5 composition with "
            "negative space at the top for a headline. Shot with natural grain, "
            "85mm feel, shallow depth of field on the face, laptop screen still "
            "legible."
        ),
    },
    {
        "id": "sample-3_A11_D30_countdown",
        "asset": "Asset 11 D-30 Countdown — atmospheric background",
        "aspect": "1:1",
        "prompt": (
            "Cinematic wide shot for a Philippine marketing countdown ad "
            "background. Subject: a Metro Manila gas station at dusk, Shell or "
            "Petron-style pump (invented generic branding — red and yellow "
            "abstract signage, NO real brand logos), large digital price "
            "display visible in the background showing blurred peso diesel "
            "prices, a single tricycle silhouette waiting at the pump. Sky: "
            "dramatic teal-to-navy gradient with a golden sunset band along "
            "the horizon, faint Manila high-rise silhouettes in the distance, "
            "a hint of atmospheric haze. Mood: end-of-day tension, quiet "
            "uncertainty, forward-looking. Color palette strictly: charcoal "
            "(#1a1a2e), teal (#0d9488), amber (#f59e0b), on pure black. Lighting: "
            "golden-hour rim light + cool ambient fill. Square 1:1 composition, "
            "horizon in the lower third, massive negative sky in the upper two "
            "thirds for a huge '30 DAYS' headline overlay (no text baked in). "
            "Cinematic, grainy, Roger Deakins wide-format feel. NO people, NO "
            "faces, NO text, NO watermarks, NO real brand logos."
        ),
    },
]


def list_available_image_models(client: "genai.Client") -> None:
    """Print models that support image generation for this API key."""
    print("[list] Available models supporting generateContent with IMAGE output:")
    try:
        for m in client.models.list():
            name = getattr(m, "name", "")
            actions = getattr(m, "supported_actions", None) or getattr(
                m, "supported_generation_methods", []
            )
            if "generateContent" in str(actions) and "image" in name.lower():
                print(f"  - {name}")
    except Exception as exc:  # noqa: BLE001
        print(f"  (list failed: {exc})")


def generate(client: "genai.Client", sample: dict) -> Path:
    print(f"[generate] {sample['id']} ({sample['aspect']}) via {MODEL_ID} …", flush=True)
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=sample["prompt"],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )
    except Exception as exc:
        print(f"  ERROR on {sample['id']}: {exc}", file=sys.stderr)
        raise

    # Walk the response for inline image data
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            mime = part.inline_data.mime_type or "image/png"
            ext = ".png" if "png" in mime else (".jpg" if "jpeg" in mime else ".bin")
            model_tag = MODEL_ID.replace("gemini-", "").replace("-preview", "")
            out = OUTPUT_DIR / f"{sample['id']}__{model_tag}{ext}"
            out.write_bytes(part.inline_data.data)
            print(f"  → {out}  ({len(part.inline_data.data):,} bytes)")
            return out

    raise RuntimeError(f"No image data returned for {sample['id']}")


def main() -> int:
    client = genai.Client(api_key=API_KEY)
    if os.environ.get("LIST_MODELS") == "1":
        list_available_image_models(client)
        return 0
    results = []
    for sample in SAMPLES:
        try:
            path = generate(client, sample)
            results.append((sample["id"], str(path), None))
        except Exception as exc:  # noqa: BLE001
            results.append((sample["id"], None, str(exc)))

    print("\n=== Generation complete ===")
    for sid, path, err in results:
        status = "OK" if err is None else f"FAIL: {err}"
        print(f"  {sid}: {status}  {path or ''}")
    return 0 if all(err is None for _, _, err in results) else 1


if __name__ == "__main__":
    sys.exit(main())
