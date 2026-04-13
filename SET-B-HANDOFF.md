# Set B Handoff — Crisis-Proof Summit creative sprint

**Read this entire doc before doing anything.** It's the full brief for Set B so a fresh Claude session can execute without reloading the full Set A conversation.

---

## What happened before this (Set A is SHIPPED)

20 ad/caption pairs were generated, composed, QA'd, and committed to Canva file `DAHGg4QhXK4` ([CLAUDE] CRISIS PROOF: KCL COPY, canva.link/gdu3jbyzs4g88dn). Full process details are in the `paid-ad-campaign-pipeline` skill — read that first if you need the workflow: `~/.claude/skills/paid-ad-campaign-pipeline/SKILL.md`.

The `assets/generated/` folder has been wiped clean (Set A files deleted to save disk). You start fresh.

---

## What Set B is

Second creative kit for BUSINESS UNLOCKED summit — **same 20-pair shape, different heroes, different copy, expanded early-bird urgency**. Target Canva file: `DAHGlfgiIUU` ([SET B] CRISIS PROOF: KCL COPY, canva.link/gl6lyi1jsmqiqhf), 40 pages, odd=ad/even=caption just like Set A.

**Paolo wants:**
1. Fresh visual angles for every hero — NOT a re-roll of Set A's scenes
2. Meaningfully different captions — new hooks, new objections, real A/B variants vs Set A
3. Expanded early-bird urgency: **6 scarcity variants** (4 dedicated to early-bird deadline + 2 general) instead of Set A's 4
4. Dropped the weakest Set A angle (A1-CURIOSITY-C_b2b) — Set B has 10 A1 variants (3+3+2+2) instead of 12 (3+3+3+3)

---

## Event facts (unchanged from Set A — do not re-research)

- **Title:** BUSINESS UNLOCKED
- **Date:** May 9, 2026 (Saturday) 9 AM – 6 PM
- **Venue:** PTTC Pasay — Philippine Trade Training Center, Sen. Gil Puyat Ave
- **Organizers:** Exponential University (ExpoU) + Gencys Group
- **Rates:** Early Bird ₱1,999 (until May 1) | Regular ₱2,500 (May 2 on) | VIP ₱5,000
- **Registration link:** `https://www.exponential-university.live/the-new-business-normal` (paste in captions with 👉 prefix)
- **Value stack to reference in every caption:** Crisis-Proof Blueprint · 2 new revenue streams · 7-day execution plan · AI + content plan · 3 connections
- **Risk reversal to reference:** "refund agad kung walang sulit sa unang oras"
- **Red lines:** NO Marcos stroke claims · NO fake urgency/countdowns · NO price on the ads themselves (only in captions)

---

## The locked template

File: `crisis-proof-summit/compose_final.py`. Reuse its helpers (`render_creative`, auto-fit headlines, auto-wrap subhead, metrics-based strip centering). Don't modify its VARIANTS dict for Set A — add Set B entries either there with `_v2` suffix OR in a new `compose_set_b.py` that imports from `compose_final`.

Template specs (locked, DO NOT CHANGE):
- Canvas 1080×1350
- Top-left: ExpoU logo only (`assets/images/expou-logo.png`)
- Bottom-right of strip: NBN transparent logo (`assets/images/nbn-logo-transparent.png`), max ~42% canvas width
- Bottom navy strip (190px): 3 lines, metrics-based spacing — MAY 9 · PTTC PASAY / 9 AM – 6 PM · SATURDAY / CTA
- Top gradient alpha 250 covering 0.65*H (bumped during Set A QA to fix text overlap)
- **NEVER on ads:** price, refund badge, duplicate date lockup, duplicate brand logo
- Headlines auto-fit, Poppins Bold font at `assets/fonts/Poppins-Bold.ttf`, body uses macOS HelveticaNeue.ttc (Inter fallback)
- `→` arrow doesn't render in HelveticaNeue — use `>>` in CTAs

## CTA rotation (cycle across variants)
1. `CLICK THE LINK TO LOCK YOUR SEAT`
2. `CLICK LINK TO LOCK YOUR SEAT`
3. `CLICK THE LINK  >>  LOCK YOUR SEAT`

## Model lock
`gemini-3.1-flash-image-preview` (Nano Banana 2). API key at `crisis-proof-summit/.env` → `GEMINI_API_KEY`. Python venv: `/Users/paolosegura/Documents/Claude Builds/furvana-social-scheduler/.venv/bin/python`. Reference pattern: `crisis-proof-summit/generate_samples.py`.

---

## Set B variant matrix (20 pairs, approved)

| # | Pages | Variant key | Hook angle | Pain anchor | Visual direction (must differ from Set A) |
|---|---|---|---|---|---|
| 1 | 1–2 | A1-PAIN-B_service_v2 | Pain | H3 peso + H9 typhoon | Filipino service biz owner reading a weather warning on phone, rain starting, shuttered awning |
| 2 | 3–4 | A1-PAIN-A_ecom_v2 | Pain | H7 TikTok Shop fees | eCom seller refreshing an empty cart dashboard on TikTok Shop, fingers hovering |
| 3 | 5–6 | A1-PAIN-C_b2b_v2 | Pain | H8 AI replacement (NOT broke clients) | Agency owner staring at a ChatGPT/Claude response that looks like his deliverable |
| 4 | 7–8 | A1-OUTCOME-B_service_v2 | Outcome | H6 PCCI | Owner at 2nd location grand opening, confidence, sunrise |
| 5 | 9–10 | A1-OUTCOME-A_ecom_v2 | Outcome | diversified channels | eCom seller with 3 devices showing different sales channels, order notifications |
| 6 | 11–12 | A1-OUTCOME-C_b2b_v2 | Outcome | premium positioning | Agency owner signing new retainer, rate card visible, higher numbers |
| 7 | 13–14 | A1-IDENTITY-B_service_v2 | Identity | survivor | Storefront at sunrise, lights coming on, resilience |
| 8 | 15–16 | A1-IDENTITY-A_ecom_v2 | Identity | builder | Seller studying a competitor's product + notebook |
| 9 | 17–18 | A1-CURIOSITY-B_service_v2 | Curiosity | contrarian | Closed shop with bright light leaking out — "what's inside?" |
| 10 | 19–20 | A1-CURIOSITY-A_ecom_v2 | Curiosity | off-platform secret | Seller closing laptop + opening physical notebook — gesture of switching mediums |
| 11 | 21–22 | **A6-EARLYBIRD-CLOCK** | Urgency — EARLY BIRD | deadline | Close-up on old analog clock at 11:59 PM with May 1 calendar in background |
| 12 | 23–24 | **A6-EARLYBIRD-20PERCENT** | Urgency — EARLY BIRD | **20% off framing** | Calculator showing "₱1,999 / ₱2,500 = 0.7996" result, warm desk lamp. Headline: "20% OFF / UNTIL MAY 1." Math verified: ₱501/₱2,500 = 20.04% |
| 13 | 25–26 | **A6-EARLYBIRD-MAY1-LINE** | Urgency — EARLY BIRD | line in the sand | Calendar with red line drawn through May 1, "AFTER THIS" note |
| 14 | 27–28 | **A6-EARLYBIRD-LAST-48HRS** | Urgency — EARLY BIRD | 48h countdown | Phone screen with a 48:00:00 countdown timer, coffee on desk |
| 15 | 29–30 | A6-SEATS-FILLING | Scarcity | seat count | Dashboard screen showing seat count ticker, moody office lit |
| 16 | 31–32 | A6-DOORS-CLOSING | Scarcity | last chance | Venue double-door mid-close at dusk, light spilling out |
| 17 | 33–34 | A3-AFFIRMATIVE-B_service_v2 | Audience | morning open | Owner at 6 AM prepping equipment, warm interior |
| 18 | 35–36 | A3-AFFIRMATIVE-A_ecom_v2 | Audience | packing midnight | Pulled-back warehouse shot, Filipina seller surrounded by packed orders |
| 19 | 37–38 | A3-AFFIRMATIVE-C_b2b_v2 | Audience | 9 PM call | Agency owner on phone walking onto MRT/LRT train home, laptop under arm |
| 20 | 39–40 | A3-DISQUALIFIER_v2 | Not for you | anti-motivational | Crossed-out "MANIFEST ABUNDANCE" self-help book on a desk, X in red marker |

**CRITICAL:**
- Every caption must be NOT a rewrite of Set A's caption — new hook, new objection handler, new angle on the same pain
- Every NB2 hero prompt must EXPLICITLY differ from Set A (Set A's heroes used: Meralco bill held up / dashboard laptop / broke-client messaging app / dawn storefront / packing orders / agency window dusk / cash drawer / reviewing checklist / writing plan / sari-sari night / flat-lay desk / hand reaching book / empty PTTC hall / calendar red circle / cash bills / venue door / mid-task service shop / packing late night / late client call / empty seminar room + crumpled worksheet)
- A3-DISQUALIFIER had TWO re-rolls in Set A to kill "ABUNDANCE" ghost text — when writing the prompt, explicitly forbid all text overlays and anything with projector/slogan/signage
- A6-DEADLINE had a re-roll to kill garbled day-header text — for calendar shots, explicitly say "NO legible day names, intentionally out of focus or cropped"

---

## Execution order (same as Set A, but faster because template is already tuned)

1. **Draft variant spec** — add 20 entries to `compose_set_b.py` (or compose_final.py with `_v2` keys). Each needs: hero filename, headline_l1/l2/optional l3, subhead, cta (rotated), out filename.

2. **Dispatch 4 parallel agents:**
   - Agent 1: Hero batch 1 — 6 NB2 generations (A1 variants 1–6)
   - Agent 2: Hero batch 2 — 7 NB2 generations (A1 variants 7–10 + A6 earlybird × 3)
   - Agent 3: Hero batch 3 — 7 NB2 generations (A6 earlybird 4 + A6 general × 2 + A3 × 4)
   - Agent 4: Caption writer — 20 fresh captions to `captions_v2_setb.txt`
   - All agents read from memory: `reference_ph_taglish_voice.md`, `project_ph_sme_context_apr2026.md`, `reference_hormozi_suby_ad_rules.md`

3. **Compose all 20 via Python** — single script run, reuses template

4. **QA pass** — dispatch one QA agent with the 20 final PNGs + captions_v2_setb.txt, check same criteria as Set A (headline fit, subhead wrap, hero-vs-avatar match, voice/link/hashtags)

5. **Fix failures** — may include gradient re-compose + hero re-roll. Budget 3–6 fixes.

6. **Upload 20 composites to Canva library** via litterbox (time=1h expiry) → `upload-asset-from-url`

7. **Start editing transaction** on `DAHGlfgiIUU` → get all page_ids + caption element_ids

8. **Stage 40 operations in 5 batches** (same pattern as Set A — 5 × `perform-editing-operations` calls on the same open transaction, each ~6-8 ops, because >10K token payloads fail):
   - Batch 1: 3 pairs (pages 1–6)
   - Batch 2: 3 pairs (pages 7–12)
   - Batch 3: 4 pairs (pages 13–20)
   - Batch 4: 6 pairs (pages 21–32) — the scarcity block
   - Batch 5: 4 pairs (pages 33–40)

9. **Show Paolo thumbnails** from the final staged response

10. **Wait for explicit "commit"**, then `commit-editing-transaction`

11. **Clean up** — delete `assets/generated/` files after commit to save disk

---

## Key file paths (on disk)

- Template: `/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/compose_final.py`
- Env: `/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/.env` (GEMINI_API_KEY set)
- Venv: `/Users/paolosegura/Documents/Claude Builds/furvana-social-scheduler/.venv/bin/python`
- NB2 reference: `/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/generate_samples.py`
- Set A captions (for voice reference): `/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/captions.txt` + `captions_v2.txt`
- Branding: `/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/images/{expou-logo.png, nbn-logo-transparent.png}`
- Fonts: `/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/fonts/Poppins-Bold.ttf`
- Output dir (empty): `/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/assets/generated/`
- This handoff: `/Users/paolosegura/Documents/Claude Builds/crisis-proof-summit/SET-B-HANDOFF.md`

## Memory pointers

- `project_crisis_proof_sprint.md` — sprint state with Set A shipped + Set B approved matrix
- `project_crisis_proof_summit.md` — event fundamentals
- `project_ph_sme_context_apr2026.md` — 10 pain hooks with citations
- `reference_ph_taglish_voice.md` — voice bible (60/40 code switch, openers, objection handlers)
- `reference_hormozi_suby_ad_rules.md` — 12-rule DR framework
- Skill: `~/.claude/skills/paid-ad-campaign-pipeline/SKILL.md` — the reusable 8-phase pipeline

## Constraint reminders (learned from Set A — don't repeat the mistakes)

1. **Canva MCP rejects files >128 pages.** Set B file is 40 — fine.
2. **MCP can't insert new text elements.** Only modify existing. Blank pages can only receive `update_fill`. Caption pages have pre-existing placeholder text I can `replace_text` on.
3. **Inline JSON payload >10K tokens fails.** Split large ops into 5 batches on the same open transaction.
4. **NB2 always hallucinates rendered text.** Any signs/bills/screens MUST be prompted as "intentionally out of focus / unreadable / blurred" or NB2 will spell-mangle them.
5. **A3-DISQUALIFIER style needs 2x re-roll budget.** NB2 keeps inserting "ABUNDANCE" / "MANIFEST" ghost text in empty-room shots. Use explicit anti-text negative prompts.
6. **Gradient top_alpha=250 / 0.65*H is the locked value.** Don't experiment — Set A's 230/0.55 caused subhead overlap on busy interiors.
7. **Agent filename conventions drift.** Set A had some agents save `sample-N_<key>.jpg` and others `sample-N_<key>__3.1-flash-image.jpg`. Pick ONE convention in the agent prompt and enforce it.
8. **Never commit without explicit user approval.** Always stage, show thumbnail, wait for "commit".
9. **Captions with >10K chars in JSON payload will break perform-editing-operations inline.** Split batches to stay under.
10. **NEVER reuse another client's API key.** Only the ExpoU .env at `crisis-proof-summit/.env`.

---

## First action when a new Claude session picks this up

1. Invoke the skill: `Skill tool` with `paid-ad-campaign-pipeline`
2. Read this handoff doc
3. Read `project_crisis_proof_sprint.md` from memory
4. Start at **step 1 — draft variant spec** in the execution order above
5. Pause at step 9 (show Paolo thumbnails) and wait for approval

Let's go.
