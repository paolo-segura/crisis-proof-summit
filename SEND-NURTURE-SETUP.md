# Send-Nurture Setup Guide

Lifecycle email system for Business Unlocked paid customers. Sends 9 emails from purchase through post-event.

---

## 1. Run the Supabase migration

Go to the Supabase dashboard → SQL Editor, then paste and run:

```
supabase/migrations/20260417_create_bu_email_log.sql
```

This creates `new_business_normal_email_log` with a UNIQUE constraint on `(email, email_number)` so emails are never sent twice.

---

## 2. Set env vars in Vercel

In your Vercel project → Settings → Environment Variables, add:

| Variable | Required | Notes |
|---|---|---|
| `BREVO_API_KEY` | Yes | Brevo transactional API key (not the SMTP password) |
| `SENDER_EMAIL` | No | Default: `success@exponential-university.live` |
| `SENDER_NAME` | No | Default: `Business Unlocked` |
| `NURTURE_START_PAID_AT` | No | ISO timestamp. Only process customers who paid on/after this date. Leave blank to process all paid customers. Example: `2026-04-01T00:00:00+00:00` |

`SUPABASE_URL` and `SUPABASE_SERVICE_KEY` should already be set from sync-payments setup.

---

## 3. Run a dry-run to verify

After deploying, run:

```bash
curl -H "Authorization: Bearer YOUR_CRON_SECRET" \
  "https://businessunlocked.ph/api/send-nurture?dry_run=true"
```

If you haven't set `CRON_SECRET`, you can call the URL directly from your browser in the Vercel preview URL (non-production environments skip auth).

**Expected output:**

```json
{
  "checked": 5,
  "sent": 3,
  "skipped": 0,
  "errors": [],
  "details": [
    {
      "to": "customer@example.com",
      "name": "Juan Cruz",
      "email_num": 1,
      "subject": "Congratulations — you're in. Here's what happens next.",
      "message_id": null,
      "status": "dry_run"
    }
  ],
  "dry_run": true
}
```

`dry_run=true` means emails are NOT sent but log entries ARE written with `dry_run=true` in the DB. This lets you verify the scheduling logic without spamming real customers.

To re-run dry-run without the DB getting in the way, delete the dry_run log rows first:

```sql
delete from new_business_normal_email_log where dry_run = true;
```

---

## 4. Enable the cron

In `vercel.json`, move the entry from `_crons_disabled` into the `crons` array:

```json
"crons": [
  { "path": "/api/sync-payments", "schedule": "*/15 * * * *" },
  { "path": "/api/abandoned-cart", "schedule": "*/15 * * * *" },
  { "path": "/api/send-nurture", "schedule": "0 1 * * *" }
]
```

Then remove it from `_crons_disabled`. Deploy to activate.

The cron runs at **1:00 AM UTC = 9:00 AM Manila** daily.

---

## 5. Monitor in Supabase

After each run, check:

```sql
select email, email_number, subject, sent_at, message_id, dry_run
from new_business_normal_email_log
order by sent_at desc
limit 50;
```

Each row is one email sent. The UNIQUE constraint on `(email, email_number)` means the same email is never sent twice to the same customer.

---

## 6. Email schedule reference

| # | Type | Trigger | Template |
|---|---|---|---|
| 1 | after_paid +0d | Same day as payment | nurture-1-problem.html |
| 2 | after_paid +2d | 2 days after payment | nurture-2-pillars.html |
| 3 | after_paid +5d | 5 days after payment | nurture-3-social-proof.html |
| 4 | after_paid +10d | 10 days after payment | nurture-4-vip-spotlight.html |
| 5 | after_paid +15d | 15 days after payment | nurture-5-urgency.html |
| 6 | before_event -3d | May 6 (3 days before) | countdown-3days.html |
| 7 | before_event -1d | May 8 (1 day before) | countdown-1day.html |
| 8 | before_event -0d | May 9 (day of event) | countdown-dayof.html |
| 9 | after_event +1d | May 10 (day after) | post-event.html |

Note: emails 6-8 are date-based, not purchase-based. All customers who paid by that date receive them.

---

## 7. Rollback

**Disable the cron:** Move the entry back to `_crons_disabled` in `vercel.json` and deploy.

**Delete log entries to allow resend:**
```sql
-- Delete a specific email for a specific customer
delete from new_business_normal_email_log
where email = 'customer@example.com' and email_number = 1;

-- Delete all dry_run entries
delete from new_business_normal_email_log where dry_run = true;

-- Delete all log entries (full reset — use with caution)
truncate new_business_normal_email_log;
```
