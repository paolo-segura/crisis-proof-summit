"""Set B variant registry — extends compose_final.VARIANTS at runtime.

Set A (committed to DAHGg4QhXK4) lives in compose_final.VARIANTS.
Set B adds 20 new variant keys, each with `_v2` suffix for the A1/A3 angles
and fresh keys for the expanded A6 block.

Hero filename convention (enforced across all 3 hero agents):
    {NN}_{variant_key}.jpg        e.g. 01_A1-PAIN-B_service_v2.jpg
    NN = zero-padded pair number 01..20

Usage:
    python compose_set_b.py                    # composes ALL 20 Set B variants
    python compose_set_b.py A6-EARLYBIRD-CLOCK # composes a specific one
"""
import sys

from compose_final import VARIANTS, cta_at, compose


SET_B_VARIANTS = {
    # ============================================================
    # 1-6  A1 PAIN x3 + A1 OUTCOME x3 (hero batch 1)
    # ============================================================
    "A1-PAIN-B_service_v2": {
        "hero": "01_A1-PAIN-B_service_v2.jpg",
        "headline_l1": "\u20b159 PESO.",
        "headline_l2": "BAGYO ULIT.",
        "subhead": "Supplier costs tumataas, staff salary due, tapos typhoon warning sa phone mo. Sino maglalabas ng plano?",
        "cta": cta_at(0),
        "out": "final_A1-PAIN-B_service_v2.png",
    },
    "A1-PAIN-A_ecom_v2": {
        "hero": "02_A1-PAIN-A_ecom_v2.jpg",
        "headline_l1": "REFRESH.",
        "headline_l2": "STILL ZERO.",
        "subhead": "TikTok Shop bagong fee structure. Cart mo empty. Boost budget mo lumalaki. May magbabago ba?",
        "cta": cta_at(1),
        "out": "final_A1-PAIN-A_ecom_v2.png",
    },
    "A1-PAIN-C_b2b_v2": {
        "hero": "03_A1-PAIN-C_b2b_v2.jpg",
        "headline_l1": "AI JUST WROTE",
        "headline_l2": "YOUR DECK.",
        "subhead": "Na-realize ng client mo kaya niyang gawin mag-isa. Eto 'yung quarter na dapat may bagong offer ka.",
        "cta": cta_at(2),
        "out": "final_A1-PAIN-C_b2b_v2.png",
    },
    "A1-OUTCOME-B_service_v2": {
        "hero": "04_A1-OUTCOME-B_service_v2.jpg",
        "headline_l1": "SECOND BRANCH.",
        "headline_l2": "SAME YEAR.",
        "subhead": "Yung mga may system ngayon, sila ang magbubukas ng pangalawa. Meron para sa'yo kung gagawin mo ang May 9.",
        "cta": cta_at(3),
        "out": "final_A1-OUTCOME-B_service_v2.png",
    },
    "A1-OUTCOME-A_ecom_v2": {
        "hero": "05_A1-OUTCOME-A_ecom_v2.jpg",
        "headline_l1": "3 CHANNELS.",
        "headline_l2": "1 INVENTORY.",
        "subhead": "Hindi ka na dependent sa isang Shopee algorithm. Ito 'yung setup ng sellers na hindi masarado ngayong 2026.",
        "cta": cta_at(4),
        "out": "final_A1-OUTCOME-A_ecom_v2.png",
    },
    "A1-OUTCOME-C_b2b_v2": {
        "hero": "06_A1-OUTCOME-C_b2b_v2.jpg",
        "headline_l1": "RAISE YOUR",
        "headline_l2": "RATES TWICE.",
        "subhead": "Habang iba nagdi-discount para hindi maiwan, ikaw nag-premium. Ito 'yung positioning play para sa market na 'to.",
        "cta": cta_at(5),
        "out": "final_A1-OUTCOME-C_b2b_v2.png",
    },

    # ============================================================
    # 7-13  A1 IDENTITY x2 + A1 CURIOSITY x2 + A6 EARLYBIRD x3 (hero batch 2)
    # ============================================================
    "A1-IDENTITY-B_service_v2": {
        "hero": "07_A1-IDENTITY-B_service_v2.jpg",
        "headline_l1": "YOU SURVIVED",
        "headline_l2": "2020.",
        "headline_l3": "2026 IS NEXT.",
        "subhead": "Hindi ka swerte. May ginagawa kang tama. Eto ang araw para ma-system 'yon bago bumagsak ulit ang market.",
        "cta": cta_at(6),
        "out": "final_A1-IDENTITY-B_service_v2.png",
    },
    "A1-IDENTITY-A_ecom_v2": {
        "hero": "08_A1-IDENTITY-A_ecom_v2.jpg",
        "headline_l1": "YOU STUDY",
        "headline_l2": "EVERY WIN.",
        "subhead": "While iba nagmu-mura sa platform, ikaw nagre-reverse engineer. Ikaw 'yung builder. Eto ang laro mo.",
        "cta": cta_at(7),
        "out": "final_A1-IDENTITY-A_ecom_v2.png",
    },
    "A1-CURIOSITY-B_service_v2": {
        "hero": "09_A1-CURIOSITY-B_service_v2.jpg",
        "headline_l1": "CLOSED DOORS.",
        "headline_l2": "LIGHTS ON.",
        "subhead": "Ano ginagawa ng 13 tindahang mukhang sarado pero tumatakbo pa rin? Eto ang sagot sa May 9.",
        "cta": cta_at(8),
        "out": "final_A1-CURIOSITY-B_service_v2.png",
    },
    "A1-CURIOSITY-A_ecom_v2": {
        "hero": "10_A1-CURIOSITY-A_ecom_v2.jpg",
        "headline_l1": "LAPTOP CLOSED.",
        "headline_l2": "BENTA UP.",
        "subhead": "You're offline but your sales still keep going up.",
        "cta": cta_at(9),
        "out": "final_A1-CURIOSITY-A_ecom_v2.png",
    },
    "A6-EARLYBIRD-CLOCK": {
        "hero": "11_A6-EARLYBIRD-CLOCK.jpg",
        "headline_l1": "11:59 PM.",
        "headline_l2": "MAY 1.",
        "subhead": "After this, \u20b1501 mas mahal. Hindi fake urgency \u2014 actual deadline ng early bird window.",
        "cta": cta_at(10),
        "out": "final_A6-EARLYBIRD-CLOCK.png",
    },
    "A6-EARLYBIRD-20PERCENT": {
        "hero": "12_A6-EARLYBIRD-20PERCENT.jpg",
        "headline_l1": "20% OFF.",
        "headline_l2": "UNTIL MAY 1.",
        "subhead": "\u20b11,999 vs \u20b12,500. Math check: \u20b1501 savings = 20.04%. Auto-applied sa early bird window \u2014 walang code.",
        "cta": cta_at(11),
        "out": "final_A6-EARLYBIRD-20PERCENT.png",
    },
    "A6-EARLYBIRD-MAY1-LINE": {
        "hero": "13_A6-EARLYBIRD-MAY1-LINE.jpg",
        "headline_l1": "LINE IN",
        "headline_l2": "THE SAND:",
        "headline_l3": "MAY 1.",
        "subhead": "Before \u2014 \u20b11,999. After \u2014 \u20b12,500. Walang extension, walang 'text me lang'. Hard stop.",
        "cta": cta_at(12),
        "out": "final_A6-EARLYBIRD-MAY1-LINE.png",
    },

    # ============================================================
    # 14-20  A6 EARLYBIRD 1 + A6 general x2 + A3 x4 (hero batch 3)
    # ============================================================
    "A6-EARLYBIRD-LAST-48HRS": {
        "hero": "14_A6-EARLYBIRD-LAST-48HRS.jpg",
        "headline_l1": "48 HOURS.",
        "headline_l2": "SAVE \u20b1501.",
        "subhead": "Early bird closes May 1, 11:59 PM. Yung mga nasa fence since April \u2014 this is your window.",
        "cta": cta_at(13),
        "out": "final_A6-EARLYBIRD-LAST-48HRS.png",
    },
    "A6-SEATS-FILLING": {
        "hero": "15_A6-SEATS-FILLING.jpg",
        "headline_l1": "SEATS",
        "headline_l2": "FILLING.",
        "subhead": "2,000 capacity. Actual bilang mula sa dashboard namin \u2014 hindi fake countdown. Check mo ngayon.",
        "cta": cta_at(14),
        "out": "final_A6-SEATS-FILLING.png",
    },
    "A6-DOORS-CLOSING": {
        "hero": "16_A6-DOORS-CLOSING.jpg",
        "headline_l1": "PINTO.",
        "headline_l2": "NAGSASARA.",
        "subhead": "After May 9, wala na 'to until next year. Kung hesitant ka since April, eto 'yung last call.",
        "cta": cta_at(15),
        "out": "final_A6-DOORS-CLOSING.png",
    },
    "A3-AFFIRMATIVE-B_service_v2": {
        "hero": "17_A3-AFFIRMATIVE-B_service_v2.jpg",
        "headline_l1": "6 AM.",
        "headline_l2": "BUKAS NA",
        "headline_l3": "TINDAHAN MO.",
        "subhead": "Kahit gulo sa labas, tuloy ka pa rin. Eto 'yung araw para gawing system ang dedication mo.",
        "cta": cta_at(16),
        "out": "final_A3-AFFIRMATIVE-B_service_v2.png",
    },
    "A3-AFFIRMATIVE-A_ecom_v2": {
        "hero": "18_A3-AFFIRMATIVE-A_ecom_v2.jpg",
        "headline_l1": "12 MIDNIGHT.",
        "headline_l2": "NAGPAPACK KA.",
        "subhead": "Sa mundo ng boost post at motivational speech, ikaw eto \u2014 actual worker. Para sa'yo 'to.",
        "cta": cta_at(17),
        "out": "final_A3-AFFIRMATIVE-A_ecom_v2.png",
    },
    "A3-AFFIRMATIVE-C_b2b_v2": {
        "hero": "19_A3-AFFIRMATIVE-C_b2b_v2.jpg",
        "headline_l1": "9 PM.",
        "headline_l2": "ON THE MRT.",
        "headline_l3": "STILL WORKING.",
        "subhead": "Client call habang umuuwi, laptop sa ilalim ng braso. Eto 'yung araw para may system ka na matatawag na 'ayos'.",
        "cta": cta_at(18),
        "out": "final_A3-AFFIRMATIVE-C_b2b_v2.png",
    },
    "A3-DISQUALIFIER_v2": {
        "hero": "20_A3-DISQUALIFIER_v2.jpg",
        "headline_l1": "NOT FOR",
        "headline_l2": "MANIFESTORS.",
        "subhead": "Kung gusto mo 'abundance' + 'align your energy' \u2014 wrong room. Ito execution. May workbook. Bring a pen.",
        "cta": cta_at(19),
        "out": "final_A3-DISQUALIFIER_v2.png",
    },
}


# Register into the shared compose_final dict
VARIANTS.update(SET_B_VARIANTS)


def main() -> None:
    if len(sys.argv) > 1:
        keys = sys.argv[1:]
    else:
        keys = list(SET_B_VARIANTS.keys())
    for k in keys:
        compose(k)


if __name__ == "__main__":
    main()
