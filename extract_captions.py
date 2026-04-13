"""Parse captions_v2.txt and emit a JSON map of variant_key -> caption body.

Each entry is delimited by:
===============================================================================
<VARIANT_KEY>
Headline: ...
Avatar: ...
Anchors: ...
===============================================================================

<body>


The body ends at the next "=========" line (or EOF).
"""
import json
import re
from pathlib import Path

SRC = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/captions_v2.txt")
DST = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/captions_v2.json")

HEADER_RE = re.compile(
    r"^={60,}\n([A-Z][A-Za-z0-9_\-]+)\nHeadline:.*?\n(?:Avatar:.*?\n)?(?:Anchors:.*?\n)?={60,}\n",
    re.MULTILINE,
)


def main() -> None:
    text = SRC.read_text()
    positions = []
    for m in HEADER_RE.finditer(text):
        positions.append((m.group(1), m.end()))

    captions = {}
    for i, (key, body_start) in enumerate(positions):
        body_end = positions[i + 1][1] - len(positions[i + 1][0]) - 200 if i + 1 < len(positions) else len(text)
        # More robust: body ends at the next "======" header line
        next_header = text.find("\n======", body_start)
        body_end = next_header if next_header != -1 else len(text)
        body = text[body_start:body_end].strip()
        captions[key] = body

    DST.write_text(json.dumps(captions, ensure_ascii=False, indent=2))
    print(f"[ok] parsed {len(captions)} captions")
    for k, v in captions.items():
        first_line = v.split("\n", 1)[0][:60]
        print(f"  {k}: {len(v)} chars  {first_line!r}")


if __name__ == "__main__":
    main()
