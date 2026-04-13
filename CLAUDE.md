# BUSINESS UNLOCKED — Project Instructions

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
- Speakers section hidden by default (no speakers confirmed yet)

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
