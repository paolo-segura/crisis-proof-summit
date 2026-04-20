/**
 * Business Unlocked — Pre-Event Webinar Funnel
 * Google Apps Script: append registrations + expose them for the reminder cron.
 *
 * HOW TO DEPLOY (one-time):
 *   1. Open your Google Sheet (the one that will store registrations).
 *   2. Extensions → Apps Script → paste this ENTIRE file (replace the default).
 *   3. In Apps Script: Project Settings → Script properties → add
 *        SHEETS_READ_SECRET = <any random string you choose>
 *      (Use the SAME value for the SHEETS_READ_SECRET env var on Vercel.)
 *   4. Click "Deploy" → "New deployment"
 *        Type: Web app
 *        Execute as: Me (your Google account)
 *        Who has access: Anyone
 *        → Click Deploy → Authorize.
 *   5. Copy the Web app URL. Paste into Vercel env as SHEETS_WEBHOOK_URL.
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

function doGet(e) {
  var action = (e && e.parameter && e.parameter.action) || '';

  if (action === 'list') {
    var expected = PropertiesService.getScriptProperties().getProperty('SHEETS_READ_SECRET');
    var provided = (e && e.parameter && e.parameter.secret) || '';
    if (!expected || provided !== expected) {
      return _bu_json({ ok: false, error: 'forbidden' });
    }
    try {
      var sheet = _bu_getSheet('Registrations');
      var values = sheet.getDataRange().getValues();
      if (values.length < 2) return _bu_json({ ok: true, rows: [] });
      var headers = values[0];
      var rows = [];
      for (var i = 1; i < values.length; i++) {
        var row = {};
        for (var j = 0; j < headers.length; j++) {
          row[String(headers[j])] = values[i][j];
        }
        rows.push(row);
      }
      return _bu_json({ ok: true, rows: rows });
    } catch (err) {
      return _bu_json({ ok: false, error: String(err) });
    }
  }

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
