// =============================================================================
// GOOGLE APPS SCRIPT WITH AUTOMATIC REAL-TIME EMAIL DISPATCH & SHEET SYNC
// =============================================================================

function doGet(e) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 1. Read Trainees tab
  var traineesSheet = ss.getSheetByName("Trainees");
  var traineesData = [];
  if (traineesSheet) {
    var tValues = traineesSheet.getDataRange().getValues();
    var tHeaders = tValues[0];
    for (var i = 1; i < tValues.length; i++) {
      var row = {};
      for (var j = 0; j < tHeaders.length; j++) {
        row[tHeaders[j]] = tValues[i][j];
      }
      traineesData.push(row);
    }
  }

  // 2. Read Submissions tab
  var subsSheet = ss.getSheetByName("Submissions");
  var subsData = [];
  if (subsSheet) {
    var sValues = subsSheet.getDataRange().getValues();
    var sHeaders = sValues[0];
    for (var k = 1; k < sValues.length; k++) {
      var sRow = {};
      for (var l = 0; l < sHeaders.length; l++) {
        sRow[sHeaders[l]] = sValues[k][l];
      }
      subsData.push(sRow);
    }
  }

  return ContentService.createTextOutput(JSON.stringify({
    trainees: traineesData,
    submissions: subsData
  })).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  var body = JSON.parse(e.postData.contents);
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var action = body.action;

  // 1. Add Trainee to Sheet and Send Automatic Email
  if (action === "add_trainee") {
    var tSheet = ss.getSheetByName("Trainees");
    if (tSheet) {
      tSheet.appendRow([body.trainee_id, body.name, body.email, body.task, body.status]);
    }
    if (body.email && body.email.indexOf("@") !== -1 && body.html) {
      MailApp.sendEmail({
        to: body.email,
        subject: body.subject || "🚀 Your New AI Training Assignment & Kickoff Call",
        htmlBody: body.html
      });
    }
  }

  // 2. Automated Real Email Dispatch (Zero manual work)
  else if (action === "send_email") {
    if (body.email && body.email.indexOf("@") !== -1) {
      MailApp.sendEmail({
        to: body.email,
        subject: body.subject || "Automated Notification: AI Trainee System",
        htmlBody: body.html
      });
    }
  }

  // 3. Update Status in Sheet
  else if (action === "update_status") {
    var tSheet2 = ss.getSheetByName("Trainees");
    var values = tSheet2.getDataRange().getValues();
    for (var i = 1; i < values.length; i++) {
      if (values[i][0] == body.trainee_id) {
        tSheet2.getRange(i + 1, 5).setValue(body.status);
        break;
      }
    }
  }

  // 4. Update Submission Feedback & Score in Sheet
  else if (action === "update_submission") {
    var sSheet = ss.getSheetByName("Submissions");
    var sVals = sSheet.getDataRange().getValues();
    for (var j = 1; j < sVals.length; j++) {
      if (sVals[j][0] == body.submission_id) {
        sSheet.getRange(j + 1, 4).setValue(body.feedback);
        sSheet.getRange(j + 1, 5).setValue(body.score);
        sSheet.getRange(j + 1, 6).setValue(body.mistakes);
        break;
      }
    }
  }

  return ContentService.createTextOutput(JSON.stringify({ status: "success" }))
    .setMimeType(ContentService.MimeType.JSON);
}
