# Payment Sync — One-Time Manual Setup

These steps must be completed before the cron job can read from the Scale Your Org sheet. ~15 minutes total.

## 1. Create the bridge Google Sheet

1. Open <https://sheets.new> in your Google account (the one that has View access to the Scale Your Org payments sheet).
2. Name it: **BU Payments Bridge**
3. Rename the first tab to **payments**.
4. In cell **A1**, paste:

   ```
   =IMPORTRANGE("<SCALE_YOUR_ORG_SHEET_URL>", "<SOURCE_TAB>!A:Z")
   ```

   Replace `<SCALE_YOUR_ORG_SHEET_URL>` with the full URL of the view-only payments sheet, and `<SOURCE_TAB>` with the tab name (e.g., `Sheet1`).
5. Click the cell → "Allow access" when the popup appears.
6. Copy the bridge sheet's URL. The sheet ID is the long string between `/d/` and `/edit`. Save it — you'll need it for `BRIDGE_SHEET_ID`.

## 2. Create a Google Cloud service account

1. Go to <https://console.cloud.google.com/>.
2. Create a new project: **business-unlocked-sync** (or reuse an existing project).
3. Enable the Sheets API: **APIs & Services → Library → Google Sheets API → Enable**.
4. Create a service account: **IAM & Admin → Service Accounts → Create**.
   - Name: `bu-payments-sync`
   - Skip role assignment (Sheets access is granted per-sheet, not via IAM).
5. Open the new service account → **Keys → Add key → Create new key → JSON**. Save the JSON file.
6. Copy the service account's email (looks like `bu-payments-sync@<project>.iam.gserviceaccount.com`).

## 3. Share the bridge sheet with the service account

1. Open the bridge sheet → **Share**.
2. Paste the service account email. Role: **Viewer**. Uncheck "Notify". Share.

## 4. Add the secrets to Vercel

In Vercel project settings → **Environment Variables**, add:

| Name | Value |
|---|---|
| `BRIDGE_SHEET_ID` | The sheet ID from step 1.6 |
| `BRIDGE_SHEET_TAB` | `payments` |
| `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON` | The entire contents of the service account JSON file (paste as a single-line string) |
| `CRON_SECRET` | A long random string (e.g., `openssl rand -hex 32` output). Vercel will inject this into cron requests as `Authorization: Bearer <value>`. The endpoint refuses requests in production without this. |

Existing vars that must also be present: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ADMIN_PASSWORD`.

## 5. Done

The cron job will pick up the new env vars on the next deploy.
