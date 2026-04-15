/**
 * Business Unlocked Summit — Participant Details webhook
 *
 * This Google Apps Script receives POSTs from the Vercel serverless
 * function `api/submit-participant.py` and appends a row to the
 * "Participants" sheet.
 *
 * Setup (see apps-script/SETUP.md for full walkthrough):
 *  1. Open your Google Sheet → Extensions → Apps Script
 *  2. Paste this file into Code.gs and save
 *  3. Deploy → New deployment → Type: Web app
 *     - Execute as: Me
 *     - Who has access: Anyone
 *  4. Copy the Web app URL and set it as APPS_SCRIPT_WEBHOOK_URL
 *     in your Vercel project's environment variables
 */

// Name of the sheet/tab to write into. Must exist.
var SHEET_NAME = 'Participants';

// Column order — must match the header row in the sheet.
var COLUMNS = [
  'submitted_at',
  'full_name',
  'email',
  'mobile_number',
  'describes_you',
  'business_type',
  'referred_by',
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_content',
  'session_id',
  'page_url',
  'user_agent'
];

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return _json({ ok: false, error: 'Empty request body' });
    }

    var data;
    try {
      data = JSON.parse(e.postData.contents);
    } catch (err) {
      return _json({ ok: false, error: 'Invalid JSON' });
    }

    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(SHEET_NAME);
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      sheet.appendRow(COLUMNS);
    }

    // Ensure header row exists
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(COLUMNS);
    }

    var row = COLUMNS.map(function (col) {
      var val = data[col];
      return val === undefined || val === null ? '' : String(val);
    });
    sheet.appendRow(row);

    return _json({ ok: true });
  } catch (err) {
    return _json({ ok: false, error: String(err) });
  }
}

function doGet() {
  return _json({ ok: true, message: 'Business Unlocked Summit participant webhook is live.' });
}

function _json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
