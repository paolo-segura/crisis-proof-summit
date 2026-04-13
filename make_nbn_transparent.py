"""Knock the solid black background out of nbn-logo.png and save as a
transparent PNG for compositing on ad backgrounds.

Strategy: convert to RGBA, treat any pixel within a black threshold as
transparent. Feather the edges slightly so shield/text don't get a hard halo.
"""
from pathlib import Path
from PIL import Image

SRC = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/images/nbn-logo.png")
DST = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/images/nbn-logo-transparent.png")

THRESHOLD = 30  # 0-255: pixels whose max RGB channel is <= this become transparent


def main() -> None:
    img = Image.open(SRC).convert("RGBA")
    pixels = img.load()
    w, h = img.size
    removed = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            maxc = max(r, g, b)
            if maxc <= THRESHOLD:
                # full transparent
                pixels[x, y] = (0, 0, 0, 0)
                removed += 1
            elif maxc <= THRESHOLD + 20:
                # soft edge: scale alpha by how far above threshold the pixel is
                falloff = int(round(255 * (maxc - THRESHOLD) / 20))
                pixels[x, y] = (r, g, b, min(a, falloff))
    img.save(DST, "PNG", optimize=True)
    print(
        f"[ok] {DST.name}  {w}x{h}  {removed:,} pixels knocked to transparent"
    )


if __name__ == "__main__":
    main()
