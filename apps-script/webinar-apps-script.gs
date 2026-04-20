/**
 * Business Unlocked — Pre-Event Webinar Funnel
 * Google Apps Script: append registrations to a Sheet.
 *
 * HOW TO DEPLOY (one-time):
 *   1. Open your Google Sheet (the one that will store registrations).
 *   2. Extensions → Apps Script → paste this ENTIRE file (replace the default).
 *   3. Click "Deploy" → "New deployment"
 *        Type: Web app
 *        Execute as: Me (your Google account)
 *        Who has access: Anyone
 *        → Click Deploy → Authorize.
 *   4. Copy the Web app URL. Paste into Vercel env as SHEETS_WEBHOOK_URL.
 *
 * HOW TO UPDATE (after any code change):
 *   Deploy → Manage deployments → pencil ✏️ → Version: "New version" → Deploy.
 *   (If you forget "New version", the old code keeps running — that's the #1
 *   reason this integration appears to break.)
 */

// All config lives inside functions so top-level parse errors can't hide it.

function doPost(e) {
  var SHEET_NAME = 'Registrations';
  try {
    var data = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    var sheet = _bu_getSheet(SHEET_NAME);

    sheet.appendRow([
      new Date(),                                 // timestamp
      data.name || '',
      data.email || '',
      data.phone || '',
      data.marketing_consent ? 'TRUE' : 'FALSE',
      data.utm_source || '',
      data.utm_medium || '',
      data.utm_campaign || '',
      data.utm_content || '',
      data.utm_term || '',
      data.referrer || '',
      data.user_agent || ''
    ]);

    return _bu_json({ ok: true });
  } catch (err) {
    return _bu_json({ ok: false, error: String(err) });
  }
}

function doGet() {
  return ContentService
    .createTextOutput('ok — BU webinar signup intake')
    .setMimeType(ContentService.MimeType.TEXT);
}

function _bu_getSheet(name) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    sheet.appendRow([
      'timestamp', 'name', 'email', 'phone', 'marketing_consent',
      'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
      'referrer', 'user_agent'
    ]);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function _bu_json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
