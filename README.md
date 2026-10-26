# Ai_Trainee_Task_Automation_System

## AI-Driven Trainee Task Management & Evaluation Automation System

A production-ready, free-of-cost Python automation system integrating **Google Sheets** (`gspread`), **Google Meet / Calendar**, and the **Google Gemini API** (`google-genai`).

---

## 🚀 Quick Start in 4 Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in:
- `GEMINI_API_KEY`: Get your free key from [Google AI Studio](https://aistudio.google.com/app/apikey)
- `SPREADSHEET_NAME_OR_ID`: Title or ID of your Google Sheet (e.g. `Trainee Management System`)
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to your downloaded service account JSON key (`credentials.json`)

### 3. Share Google Sheet
Share your Google Sheet with the Service Account client email (e.g., `xxx@your-project.iam.gserviceaccount.com`) as **Editor**.

### 4. Run the Pipeline
```bash
# Run one complete cycle
python trainee_manager.py

# Or run immediate simulation test without credentials
python trainee_manager.py --dry-run

# Or run as continuous background daemon checking every 60 seconds
python trainee_manager.py --loop 60
```

---

## 📊 Google Sheet Schema

### Tab 1: `Trainees`
| Trainee_ID | Name | Email | Current_Task | Status |
|---|---|---|---|---|
| TR-001 | Alex Rivera | alex@example.com | Build a web scraper in Python | Assigned |
| TR-002 | Sarah Chen | sarah@example.com | Implement binary search in Python | Submitted |

*Allowed Status values: `Assigned`, `Scheduled`, `Submitted`, `Reviewed`*

### Tab 2: `Submissions`
| Submission_ID | Trainee_ID | Code_Or_Text_Link | AI_Feedback | Score | Mistakes_List |
|---|---|---|---|---|---|
| SUB-101 | TR-002 | https://raw.githubusercontent.com/... | *Filled by AI* | *Filled by AI* | *Filled by AI* |

---

## 🔄 Core Workflow Pipeline

1. **Step 1: Task Assignment & Explanation**:
   - Queries `Trainees` where `Status == 'Assigned'`.
   - Sends task description to Gemini API using a child-friendly, beginner persona.
   - Saves explanation to `explanations/<Trainee_ID>_<Name>_explanation.txt` and prints to console.
2. **Step 2: Meeting Link Generation**:
   - Generates dynamic Google Meet link and 1-click Google Calendar invite URL.
   - Updates Trainee status to `Scheduled`.
3. **Step 3: Automated Review & Grading**:
   - Evaluates submissions where `Status == 'Submitted'`.
   - Mentors with friendly constructive feedback, identifying mistakes and scoring out of 100.
4. **Step 4: Update Records**:
   - Writes `AI_Feedback`, `Score`, and `Mistakes_List` into `Submissions`.
   - Updates Trainee status to `Reviewed`.
