# Crisis-Proof Business Summit — Project Instructions

## Overview
One-page sales/checkout site for the Crisis-Proof Business Summit event. Includes UTM tracking, admin reporting dashboard, and email sequences.

## Event Details
- **Event:** Crisis-Proof Business Summit
- **Date:** May 10, 2026 (Sunday), 9AM-6PM (PHT / UTC+8)
- **Venue:** Philippine Trade Training Center - Global MSME Academy, Sen. Gil J. Puyat Ave, Pasay, Metro Manila
- **Organizers:** Exponential University + Gencys Group
- **Capacity:** 1,500 pax
- **Rates:** Early Bird P1,999 | Regular P2,500 | VIP P5,000

## Tech Stack
- Plain HTML/CSS/JS (NO React, NO Next.js, NO build tools)
- Supabase for UTM tracking + sales data
- Vercel for hosting + Python serverless functions
- Paymongo for payments (link TBD)
- Chart.js (CDN) for admin dashboard charts
- Google Fonts: Oswald, Rajdhani, Inter, Space Grotesk

## Branding
- Dark navy-black background (#0a0e1a)
- Gold accents (#d4a542) for primary highlights
- Teal accents (#3bb5c4) for secondary highlights
- Match the event poster in `../crisis-proof-sales-page/event-poster.png`

## UTM Sources (12)
pancake, abundance, rtd, rdr, infotxt, gencys, prime, expou, lumina, bamboo, univoice, aiu

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
- Event poster: `../crisis-proof-sales-page/event-poster.png`
- Rates image: `../crisis-proof-sales-page/rates-and-inclusions.jpg`
