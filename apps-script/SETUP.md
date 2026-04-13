# Participant Details — Google Sheet + Apps Script setup

This is the one-time setup to wire the `/participant-details` form into a
Google Sheet. Takes ~5 minutes.

---

## Step 1 — Create the Google Sheet

1. Go to https://sheets.new (or Google Drive → New → Google Sheet).
2. Rename it: **Crisis-Proof Summit — Participants**.
3. Rename the first tab to exactly `Participants` (case-sensitive).
4. Paste this as the header row (row 1):

   ```
   submitted_at	full_name	email	mobile_number	describes_you	business_type	referred_by	utm_source	utm_medium	utm_campaign	utm_content	session_id	page_url	user_agent
   ```

   Tip: copy the line above, click cell A1, and paste — Google Sheets will
   split it across columns automatically.

---

## Step 2 — Add the Apps Script

1. In the sheet: **Extensions → Apps Script**.
2. A new tab opens with a default `Code.gs`.
3. Delete everything in `Code.gs`.
4. Copy the contents of [`Code.gs`](./Code.gs) (this folder) and paste it in.
5. Click the floppy-disk icon to save. Name the project
   **Crisis-Proof Participant Webhook**.

---

## Step 3 — Deploy as a Web App

1. Click **Deploy → New deployment**.
2. Click the gear icon next to "Select type" → choose **Web app**.
3. Fill in:
   - **Description:** `Participant webhook v1`
   - **Execute as:** `Me (your@email.com)`
   - **Who has access:** `Anyone`  *(this does NOT make your sheet public — only the script endpoint)*
4. Click **Deploy**.
5. Google will ask you to authorize the script. Click **Authorize access**,
   pick your account, click **Advanced → Go to Crisis-Proof Participant Webhook (unsafe)**,
   then **Allow**. (The "unsafe" warning is normal for personal scripts — you wrote it.)
6. Copy the **Web app URL**. It looks like:
   `https://script.google.com/macros/s/AKfycb.../exec`

---

## Step 4 — Add the URL to Vercel

1. Open your Crisis-Proof Summit project in Vercel.
2. Settings → Environment Variables.
3. Add a new variable:
   - **Name:** `APPS_SCRIPT_WEBHOOK_URL`
   - **Value:** the URL you copied in Step 3
   - **Environments:** check Production, Preview, and Development
4. Click Save.
5. Redeploy the latest production build (Deployments → … → Redeploy)
   so the new env var takes effect.

---

## Step 5 — Test it

1. Visit `https://<your-domain>/participant-details`
2. Fill out the form with test data and submit.
3. Open the Google Sheet — a new row should appear within a second.

If nothing shows up:
- Check Vercel → Deployments → [latest] → Functions → `submit-participant`
  for runtime logs.
- Re-open Apps Script → Executions to see if the webhook was hit.
- Make sure the env var name is exactly `APPS_SCRIPT_WEBHOOK_URL` (no typos).

---

## Updating the script later

If you edit `Code.gs`:
1. Save.
2. **Deploy → Manage deployments → pencil icon on the active deployment
   → Version: New version → Deploy**.
3. The URL stays the same, so you do NOT need to update Vercel.
