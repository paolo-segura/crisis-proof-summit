"""Compose a final ad creative from a nano banana hero image.

Variant-driven: pick a variant key from VARIANTS (CLI arg or first entry).
Each variant defines the hero image and the copy (headline L1/L2, subhead,
CTA text). Everything else — brand logos, strip layout, typography, spacing —
is shared across variants so we get consistent branding for the whole batch.

Usage:
    python compose_final.py                 # composes the default variant
    python compose_final.py A1-PAIN-A_ecom  # composes a specific variant
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Paths and brand
# ---------------------------------------------------------------------------
ROOT = Path("/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit")
EXPOU_LOGO = ROOT / "assets/images/expou-logo.png"
NBN_LOGO = ROOT / "assets/images/nbn-logo-transparent.png"
FONTS = ROOT / "assets/fonts"
GEN_DIR = ROOT / "assets/generated"

# Canvas
W, H = 1080, 1350
STRIP_H = 190

# Brand tokens
CHARCOAL = (26, 26, 46)
TEAL = (13, 148, 136)
TEAL_LIGHT = (20, 184, 166)
AMBER = (245, 158, 11)
AMBER_LIGHT = (251, 191, 36)
WHITE = (255, 255, 255)
MUTED = (107, 114, 128)

# Legacy aliases kept for clarity
NAVY = CHARCOAL
GOLD = TEAL

HELVETICA_TTC = "/System/Library/Fonts/HelveticaNeue.ttc"
HELVETICA_FACE = {"Regular": 0, "Bold": 1, "CondBold": 4, "Black": 9}


# ---------------------------------------------------------------------------
# Variant registry
# ---------------------------------------------------------------------------
CTAS = [
    "CLICK THE LINK TO LOCK YOUR SEAT",
    "CLICK LINK TO LOCK YOUR SEAT",
    "CLICK THE LINK  >>  LOCK YOUR SEAT",
]


def cta_at(i: int) -> str:
    return CTAS[i % len(CTAS)]


VARIANTS = {
    # ============================================================
    # Asset 1 PAIN × 3 avatars (pages 1-6, already shipped)
    # ============================================================
    "A1-PAIN-B_service": {
        "hero": "sample-1_A1-PAIN-B_service__3.1-flash-image.jpg",
        "headline_l1": "DIESEL JUST HIT",
        "headline_l2": "\u20b1172.",
        "subhead": "And your Meralco bill goes up again next month.",
        "cta": cta_at(0),
        "out": "final_A1-PAIN-B_service.png",
    },
    "A1-PAIN-A_ecom": {
        "hero": "sample-2_A1-PAIN-A_ecom__3.1-flash-image.jpg",
        "headline_l1": "0 ORDERS.",
        "headline_l2": "3 DAYS STRAIGHT.",
        "subhead": "Shopee kaltas. Lazada fees. TikTok shop tumatahimik.",
        "cta": cta_at(1),
        "out": "final_A1-PAIN-A_ecom.png",
    },
    "A1-PAIN-C_b2b": {
        "hero": "sample-4_A1-PAIN-C_b2b__3.1-flash-image.jpg",
        "headline_l1": "YOUR CLIENTS ARE",
        "headline_l2": "BROKE TOO.",
        "subhead": "\"Next week na lang pre.\" Paano ka maco-collect kung ang client mo walang pera?",
        "cta": cta_at(2),
        "out": "final_A1-PAIN-C_b2b.png",
    },

    # ============================================================
    # Asset 1 OUTCOME × 3 avatars (pages 7-12)
    # Framing: post-summit transformation, PCCI authority
    # ============================================================
    "A1-OUTCOME-B_service": {
        "hero": "sample-5_A1-OUTCOME-B_service.jpg",
        "headline_l1": "BUILD A BUSINESS",
        "headline_l2": "NA HINDI UMIIYAK.",
        "subhead": "PCCI sabi: MSMEs ang unang mababasag. May playbook kami para sa'yong ayaw.",
        "cta": cta_at(3),
        "out": "final_A1-OUTCOME-B_service.png",
    },
    "A1-OUTCOME-A_ecom": {
        "hero": "sample-6_A1-OUTCOME-A_ecom.jpg",
        "headline_l1": "THE SELLERS WHO",
        "headline_l2": "SURVIVE 2026.",
        "subhead": "Yung meron nang system, nakakaraos. Yung wala, sarado sa June. Nasa'n ka ngayon?",
        "cta": cta_at(4),
        "out": "final_A1-OUTCOME-A_ecom.png",
    },
    "A1-OUTCOME-C_b2b": {
        "hero": "sample-7_A1-OUTCOME-C_b2b.jpg",
        "headline_l1": "THE AGENCIES",
        "headline_l2": "STILL STANDING.",
        "subhead": "Hindi sila mas magaling sa'yo. May system lang sila para sa ganitong market.",
        "cta": cta_at(5),
        "out": "final_A1-OUTCOME-C_b2b.png",
    },

    # ============================================================
    # Asset 1 IDENTITY × 3 avatars (pages 13-18)
    # Framing: "for the owners who refuse to close"
    # ============================================================
    "A1-IDENTITY-B_service": {
        "hero": "sample-8_A1-IDENTITY-B_service.jpg",
        "headline_l1": "FOR OWNERS",
        "headline_l2": "WHO REFUSE",
        "headline_l3": "TO CLOSE.",
        "subhead": "Sa inyong tumutulong kahit umiiyak sa gabi. Eto ang araw para sa inyo.",
        "cta": cta_at(6),
        "out": "final_A1-IDENTITY-B_service.png",
    },
    "A1-IDENTITY-A_ecom": {
        "hero": "sample-9_A1-IDENTITY-A_ecom.jpg",
        "headline_l1": "FOR SELLERS",
        "headline_l2": "SAWA NA SA",
        "headline_l3": "BOOST POST.",
        "subhead": "Kung pagod ka na mag-pray pag nag-boost ka \u2014 eto ang actual playbook.",
        "cta": cta_at(7),
        "out": "final_A1-IDENTITY-A_ecom.png",
    },
    "A1-IDENTITY-C_b2b": {
        "hero": "sample-10_A1-IDENTITY-C_b2b.jpg",
        "headline_l1": "FOR THE ONES",
        "headline_l2": "WHO STAYED.",
        "subhead": "Kahit lahat kilala mong nagsara, ikaw tumutuloy. Eto ang system para di ka mahulog.",
        "cta": cta_at(8),
        "out": "final_A1-IDENTITY-C_b2b.png",
    },

    # ============================================================
    # Asset 1 CURIOSITY × 3 avatars (pages 19-24)
    # Framing: counter-intuitive hook, curiosity gap
    # ============================================================
    "A1-CURIOSITY-B_service": {
        "hero": "sample-11_A1-CURIOSITY-B_service.jpg",
        "headline_l1": "WHY 13 OWNERS",
        "headline_l2": "AREN'T PANICKING.",
        "subhead": "Habang lahat ng iba ay nagboost ng posts at nagpipray, sila may ginagawa na ibang bagay. Eto kung ano.",
        "cta": cta_at(9),
        "out": "final_A1-CURIOSITY-B_service.png",
    },
    "A1-CURIOSITY-A_ecom": {
        "hero": "sample-12_A1-CURIOSITY-A_ecom.jpg",
        "headline_l1": "THE SELLERS",
        "headline_l2": "WHO STOPPED",
        "headline_l3": "BOOSTING.",
        "subhead": "Tinanggal nila ang ₱500/day boost budget. Ang benta nila? Dumoble. Gagawin natin 'to sa May 9.",
        "cta": cta_at(10),
        "out": "final_A1-CURIOSITY-A_ecom.png",
    },
    "A1-CURIOSITY-C_b2b": {
        "hero": "sample-13_A1-CURIOSITY-C_b2b.jpg",
        "headline_l1": "ONE QUESTION",
        "headline_l2": "TO ASK YOUR",
        "headline_l3": "BROKE CLIENT.",
        "subhead": "Hindi \"kailan ka magbabayad?\". Ito 'yung tanong na lumalabas ng cash in 7 days.",
        "cta": cta_at(11),
        "out": "final_A1-CURIOSITY-C_b2b.png",
    },

    # ============================================================
    # Asset 6 Scarcity × 4 (pages 25-32)
    # Framing: urgency / deadline / seat count
    # ============================================================
    "A6-SEATS": {
        "hero": "sample-14_A6-SEATS.jpg",
        "headline_l1": "2,000 SEATS.",
        "headline_l2": "THE ROOM IS",
        "headline_l3": "FILLING FAST.",
        "subhead": "Hindi fake countdown. Actual bilang mula sa dashboard namin.",
        "cta": cta_at(12),
        "out": "final_A6-SEATS.png",
    },
    "A6-DEADLINE": {
        "hero": "sample-15_A6-DEADLINE.jpg",
        "headline_l1": "EARLY BIRD",
        "headline_l2": "ENDS MAY 1.",
        "subhead": "After that, ₱2,500 na. Meralco goes up in May. Lock in bago gawin nila 'yon for you.",
        "cta": cta_at(13),
        "out": "final_A6-DEADLINE.png",
    },
    "A6-PRICE-JUMP": {
        "hero": "sample-16_A6-PRICE-JUMP.jpg",
        "headline_l1": "SAVE \u20b1501",
        "headline_l2": "TODAY.",
        "subhead": "3 tanks ng motor mo. Or half ng Meralco bill (pre-April, to be fair).",
        "cta": cta_at(14),
        "out": "final_A6-PRICE-JUMP.png",
    },
    "A6-LAST-CHANCE": {
        "hero": "sample-17_A6-LAST-CHANCE.jpg",
        "headline_l1": "LAST SEATS.",
        "headline_l2": "DOORS CLOSE",
        "headline_l3": "MAY 9.",
        "subhead": "After that, wala na until next year. Kung hesitant ka since April, ngayon na ang decision.",
        "cta": cta_at(15),
        "out": "final_A6-LAST-CHANCE.png",
    },

    # ============================================================
    # Asset 3 Who Is This For × 4 (pages 33-40)
    # Framing: audience qualifier
    # ============================================================
    "A3-AFFIRMATIVE-B_service": {
        "hero": "sample-18_A3-AFFIRMATIVE-B_service__3.1-flash-image.jpg",
        "headline_l1": "ARE YOU THE",
        "headline_l2": "OWNER WHO",
        "headline_l3": "STILL OPENS?",
        "subhead": "Diesel up. Meralco up. Customers nag-tighten. Pero ikaw, bumubukas pa rin ng store every 9 AM. Eto ang para sa'yo.",
        "cta": cta_at(16),
        "out": "final_A3-AFFIRMATIVE-B_service.png",
    },
    "A3-AFFIRMATIVE-A_ecom": {
        "hero": "sample-19_A3-AFFIRMATIVE-A_ecom__3.1-flash-image.jpg",
        "headline_l1": "STILL PACKING",
        "headline_l2": "ORDERS AT",
        "headline_l3": "MIDNIGHT?",
        "subhead": "Zero order weeks, platform fees eating margins, pero tuloy ka pa rin. Itong araw para sa'yo.",
        "cta": cta_at(17),
        "out": "final_A3-AFFIRMATIVE-A_ecom.png",
    },
    "A3-AFFIRMATIVE-C_b2b": {
        "hero": "sample-20_A3-AFFIRMATIVE-C_b2b__3.1-flash-image.jpg",
        "headline_l1": "STILL ON",
        "headline_l2": "CLIENT CALLS",
        "headline_l3": "AT 9 PM?",
        "subhead": "Clients broke, retainers late, pero tuloy ka pa rin. Eto 'yung system para di ka masarado.",
        "cta": cta_at(18),
        "out": "final_A3-AFFIRMATIVE-C_b2b.png",
    },
    "A3-DISQUALIFIER": {
        "hero": "sample-21_A3-DISQUALIFIER.jpg",
        "headline_l1": "THIS DAY IS",
        "headline_l2": "NOT FOR YOU.",
        "subhead": "Kung gusto mo ng motivational speech, mali ka ng upuan. Ito execution room. May workbook. Bring a pen.",
        "cta": cta_at(19),
        "out": "final_A3-DISQUALIFIER.png",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def resize_cover(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_ratio = img.width / img.height
    dst_ratio = target_w / target_h
    if src_ratio > dst_ratio:
        new_h = target_h
        new_w = int(round(new_h * src_ratio))
    else:
        new_w = target_w
        new_h = int(round(new_w / src_ratio))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def gradient_overlay(w: int, h: int, top_alpha: int, bottom_alpha: int) -> Image.Image:
    grad = Image.new("L", (1, h), 0)
    for y in range(h):
        t = y / (h - 1) if h > 1 else 0
        alpha = int(round(top_alpha + (bottom_alpha - top_alpha) * t))
        grad.putpixel((0, y), alpha)
    grad = grad.resize((w, h))
    black = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    black.putalpha(grad)
    return black


def draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    xy: tuple,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    shadow: tuple = (0, 0, 0, 180),
    offset: int = 4,
    anchor: str = "la",
) -> None:
    draw.text((xy[0] + offset, xy[1] + offset), text, font=font, fill=shadow, anchor=anchor)
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


# ---------------------------------------------------------------------------
# Compose
# ---------------------------------------------------------------------------
def compose(variant_key: str) -> Path:
    if variant_key not in VARIANTS:
        raise KeyError(
            f"Unknown variant '{variant_key}'. Known: {list(VARIANTS.keys())}"
        )
    v = VARIANTS[variant_key]
    hero_path = GEN_DIR / v["hero"]
    out_path = GEN_DIR / v["out"]

    # --- Hero
    hero = Image.open(hero_path).convert("RGB")
    canvas = resize_cover(hero, W, H).convert("RGBA")

    # --- Top gradient (darken for top-left logo + headline legibility)
    # Bumped from 230→250 alpha and 0.55→0.65 H coverage after QA found
    # subhead text overlapping hero subjects on busy interior shots.
    top_grad = gradient_overlay(W, int(H * 0.65), top_alpha=250, bottom_alpha=0)
    canvas.alpha_composite(top_grad, (0, 0))

    # --- Bottom strip (solid navy)
    strip_h = STRIP_H
    strip = Image.new("RGBA", (W, strip_h), NAVY + (255,))
    canvas.alpha_composite(strip, (0, H - strip_h))
    # gold underline
    underline = Image.new("RGBA", (W, 6), GOLD + (255,))
    canvas.alpha_composite(underline, (0, H - strip_h - 6))

    draw = ImageDraw.Draw(canvas)

    # --- ExpoU logo top-left
    try:
        logo = Image.open(EXPOU_LOGO).convert("RGBA")
        logo_target_h = 70
        ratio = logo_target_h / logo.height
        logo = logo.resize((int(round(logo.width * ratio)), logo_target_h), Image.LANCZOS)
        canvas.alpha_composite(logo, (60, 50))
    except FileNotFoundError:
        print(f"[warn] ExpoU logo not found at {EXPOU_LOGO}")

    # --- Headline (2 lines, Poppins, white + gold accent)
    # Auto-fit: shrink font size until the text fits within (W - 120) so
    # long headlines don't run off the right edge on any variant.
    def fit_font(text: str, start_size: int, max_width: int) -> ImageFont.FreeTypeFont:
        size = start_size
        while size > 30:
            f = load_font("Poppins-Bold.ttf", size)
            bbox = draw.textbbox((0, 0), text, font=f)
            if (bbox[2] - bbox[0]) <= max_width:
                return f
            size -= 5
        return load_font("Poppins-Bold.ttf", 30)

    max_headline_w = W - 120  # 60px margin on each side
    has_l3 = bool(v.get("headline_l3"))
    # 3-line headlines need smaller max sizes so everything fits above the strip
    l1_start = 90 if has_l3 else 110
    l2_start = 130 if has_l3 else 170
    headline_l1 = fit_font(v["headline_l1"], l1_start, max_headline_w)
    headline_l2 = fit_font(v["headline_l2"], l2_start, max_headline_w)
    draw_text_with_shadow(draw, (60, 200), v["headline_l1"], headline_l1, WHITE)
    l1_bbox = draw.textbbox((60, 200), v["headline_l1"], font=headline_l1)
    l2_y = l1_bbox[3] - 10
    draw_text_with_shadow(draw, (60, l2_y), v["headline_l2"], headline_l2, GOLD)

    # Optional 3rd headline line (gold, continues L2 color)
    if has_l3:
        l2_bbox_tmp = draw.textbbox((60, l2_y), v["headline_l2"], font=headline_l2)
        l3_y = l2_bbox_tmp[3] - 10
        headline_l3 = fit_font(v["headline_l3"], l2_start, max_headline_w)
        draw_text_with_shadow(draw, (60, l3_y), v["headline_l3"], headline_l3, GOLD)
        # Subhead anchors to L3's bottom instead of L2's
        last_headline_y = l3_y
        last_headline_font = headline_l3
        last_headline_text = v["headline_l3"]
    else:
        last_headline_y = l2_y
        last_headline_font = headline_l2
        last_headline_text = v["headline_l2"]

    # --- Subhead (pushed below the last headline line for breathing room)
    # Auto-wrap: break the subhead into lines that each fit within max width.
    subhead_font = load_font("Poppins-Regular.ttf", 34)
    last_bbox = draw.textbbox(
        (60, last_headline_y), last_headline_text, font=last_headline_font
    )
    subhead_y = last_bbox[3] + 20
    subhead_max_w = W - 120

    def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list:
        words = text.split()
        lines: list = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), trial, font=font)
            if (bbox[2] - bbox[0]) <= max_w:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    subhead_lines = wrap_text(v["subhead"], subhead_font, subhead_max_w)
    # Line height = font ascent+descent + 6px
    sa, sd = subhead_font.getmetrics()
    subhead_line_h = sa + sd + 6
    for i, line in enumerate(subhead_lines):
        draw_text_with_shadow(
            draw,
            (60, subhead_y + i * subhead_line_h),
            line,
            subhead_font,
            MUTED,
        )

    # --- Bottom strip content (no price — strict rule)
    strip_y = H - strip_h
    line1_font = load_font("Poppins-Bold.ttf", 38)
    line2_font = load_font("Poppins-Regular.ttf", 22)
    line3_font = load_font("Poppins-Bold.ttf", 24)

    def ascent_descent(f: ImageFont.FreeTypeFont) -> tuple:
        return f.getmetrics()

    gap = 14
    heights = []
    for f in (line1_font, line2_font, line3_font):
        a, d = ascent_descent(f)
        heights.append(a + d)
    total_h = sum(heights) + gap * 2
    block_top = strip_y + (strip_h - total_h) // 2

    y1 = block_top
    draw.text((60, y1), "MAY 9 · PTTC PASAY", font=line1_font, fill=WHITE)
    y2 = y1 + heights[0] + gap
    draw.text((60, y2), "9 AM – 6 PM · SATURDAY", font=line2_font, fill=MUTED)
    y3 = y2 + heights[1] + gap
    draw.text((60, y3), v["cta"], font=line3_font, fill=AMBER)

    # --- NBN event logo (transparent), ~2x size, bottom-right of strip
    try:
        nbn = Image.open(NBN_LOGO).convert("RGBA")
        max_h = strip_h - 28
        max_w = int(W * 0.42)
        ratio = max_h / nbn.height
        new_w = int(round(nbn.width * ratio))
        if new_w > max_w:
            ratio = max_w / nbn.width
            new_w = max_w
            new_h = int(round(nbn.height * ratio))
        else:
            new_h = max_h
        nbn = nbn.resize((new_w, new_h), Image.LANCZOS)
        canvas.alpha_composite(
            nbn,
            (W - nbn.width - 50, strip_y + (strip_h - nbn.height) // 2),
        )
    except FileNotFoundError:
        print(f"[warn] NBN logo not found at {NBN_LOGO}")

    canvas.convert("RGB").save(out_path, "PNG", optimize=True)
    print(f"[ok] {variant_key} → {out_path} ({out_path.stat().st_size:,} bytes)")
    return out_path


def main() -> None:
    if len(sys.argv) > 1:
        keys = sys.argv[1:]
    else:
        keys = [list(VARIANTS.keys())[0]]
    for k in keys:
        compose(k)


if __name__ == "__main__":
    main()
