"""One-shot script to chroma-key solid backgrounds out of speaker brand logos."""
from PIL import Image
import numpy as np
from pathlib import Path

LOGOS_DIR = Path(__file__).parent / "assets" / "Company Logos"


def chroma_key(
    in_path,
    out_path,
    bg_sample="corners",
    bg_threshold=40,
    edge_softness=25,
    recolor=None,
    crop_padding=8,
):
    img = Image.open(in_path).convert("RGBA")
    arr = np.array(img).astype(np.float32)
    h, w = arr.shape[:2]

    if bg_sample == "corners":
        corners = np.array([
            arr[2:8, 2:8, :3].reshape(-1, 3),
            arr[2:8, w - 8:w - 2, :3].reshape(-1, 3),
            arr[h - 8:h - 2, 2:8, :3].reshape(-1, 3),
            arr[h - 8:h - 2, w - 8:w - 2, :3].reshape(-1, 3),
        ])
        bg = corners.reshape(-1, 3).mean(axis=0)
    else:
        bg = np.array(bg_sample, dtype=np.float32)

    rgb = arr[:, :, :3]
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))

    alpha = np.clip((dist - bg_threshold) / edge_softness, 0.0, 1.0) * 255.0
    arr[:, :, 3] = alpha

    if recolor is not None:
        recolor_arr = np.array(recolor, dtype=np.float32)
        opaque_mask = alpha > 5
        arr[opaque_mask, 0] = recolor_arr[0]
        arr[opaque_mask, 1] = recolor_arr[1]
        arr[opaque_mask, 2] = recolor_arr[2]

    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")

    if crop_padding is not None:
        bbox = out.getbbox()
        if bbox:
            x0, y0, x1, y1 = bbox
            x0 = max(0, x0 - crop_padding)
            y0 = max(0, y0 - crop_padding)
            x1 = min(out.width, x1 + crop_padding)
            y1 = min(out.height, y1 + crop_padding)
            out = out.crop((x0, y0, x1, y1))

    out.save(out_path, "PNG")
    print(f"  -> {out_path.name} ({out.size[0]}x{out.size[1]})")


def run():
    print("Dear Face: keying teal bg, recoloring logo to black")
    chroma_key(
        LOGOS_DIR / "dearface-logo-original.png",
        LOGOS_DIR / "dearface-logo.png",
        bg_threshold=55,
        edge_softness=30,
        recolor=(0, 0, 0),
    )

    print("SkinPotions: keying pink bg")
    chroma_key(
        LOGOS_DIR / "skinpotions-logo-original.png",
        LOGOS_DIR / "skinpotions-logo.png",
        bg_threshold=45,
        edge_softness=25,
    )

    print("New Moon: keying off-white bg (tighter threshold, peach is light)")
    chroma_key(
        LOGOS_DIR / "newmoon-logo-original.png",
        LOGOS_DIR / "newmoon-logo.png",
        bg_threshold=18,
        edge_softness=20,
    )

    print("Kanna Beauty: keying near-white bg")
    chroma_key(
        LOGOS_DIR / "kanna-logonew-original.png",
        LOGOS_DIR / "kanna-logonew.png",
        bg_threshold=22,
        edge_softness=22,
    )

    print("done")


if __name__ == "__main__":
    run()
