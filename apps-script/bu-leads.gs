/**
 * Business Unlocked — BU Leads Sheet intake webhook
 *
 * Receives POSTs from api/register-lead.py and appends a lead row to the
 * "BU Leads" sheet tab.
 *
 * DEPLOY INSTRUCTIONS (do this once after pasting):
 *   1. Open your NEW Google Sheet (create one named "BU Leads").
 *   2. Extensions → Apps Script → paste this entire file (replace the default Code.gs).
 *   3. Save (Ctrl+S / Cmd+S).
 *   4. Click "Deploy" → "New deployment".
 *        Type: Web app
 *        Execute as: Me (your Google account)
 *        Who has access: Anyone (even anonymous)
 *   5. Authorize when prompted.
 *   6. Copy the Web app URL.
 *   7. In Vercel → project settings → Environment Variables, add:
 *        BU_LEADS_APPS_SCRIPT_URL = <the Web app URL you just copied>
 *   8. Redeploy on Vercel so the new env var is picked up.
 *
 * TO UPDATE after a code change:
 *   Deploy → Manage deployments → pencil ✏️ → Version: "New version" → Deploy.
 *   (Forgetting "New version" keeps the old code running — most common bug.)
 *
 * VERIFY DEPLOYMENT:
 *   Open the Web app URL in a browser — you should see: {"ok":true,"message":"..."}
 */

// Sheet tab name — must exist (or will be auto-created with header row).
var SHEET_NAME = 'BU Leads';

// Column order — must match the header row in the sheet.
// Team fills in: status, tier, amount, payment_method, closed_at, notes manually.
var COLUMNS = [
  'submitted_at',
  'name',
  'phone',
  'email',
  'best_time_to_call',
  'status',          // starts as "new"; team updates: contacted / interested / closed_xendit / closed_offline / lost
  'tier',            // team fills: EB / REG / EB_ZOOM / REG_ZOOM / VIP
  'amount',          // team fills after close
  'payment_method',  // team fills: xendit / bank / gcash / cash
  'closed_at',       // team fills after close
  'notes',           // team fills as needed
  'source',
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_content',
  'utm_term',
  'session_id'
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

    var sheet = _getOrCreateSheet(SHEET_NAME);

    var row = COLUMNS.map(function (col) {
      var val = data[col];
      if (val === undefined || val === null) return '';
      return String(val);
    });

    sheet.appendRow(row);
    return _json({ ok: true });

  } catch (err) {
    return _json({ ok: false, error: String(err) });
  }
}

/**
 * doGet: sanity-check endpoint.
 * Visit the Web app URL in a browser to confirm deployment is live.
 */
function doGet() {
  return _json({ ok: true, message: 'BU Leads intake webhook is live.' });
}

function _getOrCreateSheet(name) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    // Write header row
    sheet.appendRow(COLUMNS);
    sheet.setFrozenRows(1);
    // Make header row bold
    sheet.getRange(1, 1, 1, COLUMNS.length).setFontWeight('bold');
    // Auto-resize columns for readability
    sheet.autoResizeColumns(1, COLUMNS.length);
  }
  return sheet;
}

function _json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
