# BUSINESS UNLOCKED — Project Instructions

## ⚠️ MANDATORY PRE-PUSH CHECKLIST — MOBILE SPEAKERS REGRESSION

**This section has silently disappeared on mobile MULTIPLE times. Before any `git push` that touches `index.html`, `css/style.css`, `js/main.js`, or anything that could affect layout/animation — you MUST verify:**

1. Open `/the-new-business-normal` at mobile widths (320 / 375 / 414 / 767px). DevTools device toolbar is fine.
2. Scroll to `#speakers`. Confirm ALL of the following render fully visible (no blank area, no clipped cards):
   - 🏛️ **The Legacy Builders** — 4 cards (Jorge, Paco, Gina, Jojo)
   - 💻 **The Digital Natives** — 7 cards (Steve, Kristine, Jonah, Jeff, Charlie, Nani, Migs)
   - 🤖 **The AI Edge** — 1 card (Jay Jazmines)
   - Total: 12 speakers (in `index.html` they render as one flat grid; in `business-unlocked.html` they render in three bucket grids)
3. Each card shows: photo (≈200×290 on mobile), name, title, and full hook paragraph. Photo must NOT overflow or collapse to 0 height.
4. Confirm the section is actually opacity:1 (the `.animate-in` class flips to `.visible` via IntersectionObserver — if JS breaks, the whole section stays opacity:0 and looks "missing").

**Known regression causes to check first:**
- **Root cause of the Apr 24, 2026 regression (DO NOT reintroduce):** `initScrollAnimations` in `js/main.js` used `IntersectionObserver` with `threshold: 0.1`. `#speakers` after the 3-bucket restructure is ~8000px tall on mobile — 10% of 8000 is 800px, but a mobile viewport is only 568–844px. The threshold could never be met, so `.visible` was never added, so `.animate-in` stayed at `opacity:0`. Fix: `threshold: 0, rootMargin: '0px 0px -10% 0px'` + a scroll/touch fallback that force-reveals all `.animate-in` elements. **If anyone changes `threshold` on that observer, the speakers section dies on mobile again.**
- A new rule under `@media (max-width: 767px)` that accidentally sets `display: none`, `height: 0`, `overflow: hidden` with clipped children, or `grid-template-columns: 0`.
- `.speakers-grid-single` (AI Edge bucket) leaking its desktop-only `grid-template-columns: 260px 1fr` rule to mobile — AI Edge card must stack vertically on mobile like the others.
- Adjacent section (brand logos strip, stakes frame) growing tall enough to push `#speakers` off a short-viewport scroll, combined with `overflow: hidden` on an ancestor.
- Browser cache on Paolo's phone — when reporting "fixed", do a hard reload / clear cache before confirming.

**If you regress this again, the rule is: revert the push, then fix. Do NOT patch forward.**

## Overview
Two parallel workstreams in this folder:
1. **Sales page** — one-page checkout site with Hormozi/Suby conversion funnel
2. **Marketing kit** — 13-asset paid social kit produced in Canva. Source of truth: `MARKETING-KIT-PLAN.md`. Editable Canva file (ONLY ONE ALLOWED): `DAHGg4QhXK4` — [CLAUDE] CRISIS PROOF: KCL COPY. Do not create new Canva designs.

## Event Details (rebranded Apr 12, 2026)
- **Title:** BUSINESS UNLOCKED
- **Subtitle:** Turn Crisis into Cashflow
- **Tagline:** "Turn Crisis into Cashflow. Unlock Your Business."
- **Date:** May 9, 2026 (Saturday), 9AM-6PM (PHT / UTC+8)
- **Venue:** Philippine Trade Training Center - Global MSME Academy, Sen. Gil J. Puyat Ave, Pasay, Metro Manila
- **Organizers:** Exponential University + Gencys Group
- **Capacity:** 2,000 pax
- **Rates:** Early Bird P1,999 | Regular P2,500 | VIP P5,000

## Tech Stack
- Plain HTML/CSS/JS (NO React, NO Next.js, NO build tools)
- Supabase for UTM tracking + sales data
- Vercel for hosting + Python serverless functions
- Paymongo for payments (link TBD)
- Chart.js (CDN) for admin dashboard charts
- Google Fonts: Poppins, Lora

## Branding
- Clean warm white background (#FAFAF9)
- Teal accents (#0D9488) for primary highlights
- Amber accents (#F59E0B) for secondary highlights
- Match the event poster in `../crisis-proof-sales-page/event-poster-no-qr-new-2.png`

## UTM Sources (14)
pancake, abundance, rtd, rdr, infotxt, gencys, prime, expou, lumina, bamboo, univoice, aiu, packpoint, youniq

## Key Rules
- Mobile-first design (320px base, breakpoints at 768px and 1024px)
- No frameworks or build steps — everything runs from static files + Vercel serverless
- Supabase anon key for inserts only (RLS insert-only policy), service-role key server-side only
- All emails use inline CSS, 600px max-width, branded dark/gold/teal theme
- Countdown timer must use PHT (UTC+8) timezone
- Speakers section (`#speakers`) is LIVE with 12 confirmed speakers across 3 buckets — see the pre-push checklist at the top of this file. Do NOT hide it.

## File Structure
```
index.html          — Sales page + checkout
admin.html          — Reporting dashboard
css/style.css       — All styles
js/main.js          — Countdown, FAQ, scroll
js/utm.js           — UTM tracking + Supabase logging
js/supabase-client.js — Supabase init
js/admin.js         — Dashboard logic
api/report.py       — Vercel serverless admin API
emails/             — 9 HTML email templates
vercel.json         — Vercel config
```

## Source Materials
- Event brief: `../crisis-proof-sales-page/Event Brief_ Crisis-Proof Summit.pdf`
- Event poster: `../crisis-proof-sales-page/event-poster-no-qr-new-2.png`
- Rates image: `../crisis-proof-sales-page/rates-and-inclusions.jpg`
- Brand deck: `../crisis-proof-sales-page/The_New_Business_Normal_Summit_Brand_Deck-1.pdf`

## Vercel Env Vars — Zoom ticket launch (added 2026-04-23)

These must be set in Vercel before deploying the `feature/messaging-zoom-v2` branch:

| Env var | Required? | Notes |
|---|---|---|
| `BU_ZOOM_JOIN_URL` | Yes (ops) | Full Zoom join URL for the May 9 live stream. Until provisioned, Zoom buyers receive a "link coming 24h before" fallback — email still sends, does NOT crash. |
| `BREVO_API_KEY` | Already set | Existing var — no change needed. If absent, all confirmation emails are skipped (logged). |
| `BREVO_SENDER_EMAIL` | Already set | Existing var — defaults to `hello@exponential-university.live`. |
| `BREVO_SENDER_NAME` | Already set | Existing var — defaults to `Business Unlocked`. |

The Zoom confirmation email template is at `emails/post-purchase-zoom.html`.
The in-person confirmation email template is at `emails/post-purchase-inperson.html`.
Both are rendered and sent inline by `api/xendit-webhook.py` on every PAID event.
