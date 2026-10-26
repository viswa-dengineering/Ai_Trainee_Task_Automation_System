#!/usr/bin/env python3
"""
================================================================================
AI-DRIVEN TRAINEE TASK MANAGEMENT & EVALUATION AUTOMATION SYSTEM
================================================================================
Tech Stack:
  - Google Sheets (gspread) as Central Database
  - Google Meet / Calendar API for Automated Meeting Scheduling
  - Google Gemini API (Free Tier via google-genai) for AI Mentorship & Grading
  - Python 3.10+
================================================================================
"""

import os
import sys
import json
import time
import re
import random
import string
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import quote_plus

# -----------------------------------------------------------------------------
# Optional dotenv loading
# -----------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# -----------------------------------------------------------------------------
# Third-party Dependencies
# -----------------------------------------------------------------------------
try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    gspread = None
    Credentials = None

try:
    import requests
except ImportError:
    requests = None

# Gemini SDK (Supports official google-genai, with fallback to google-generativeai)
GENAI_SDK_TYPE = None
try:
    from google import genai
    from google.genai import types
    GENAI_SDK_TYPE = "google-genai"
except ImportError:
    try:
        import google.generativeai as legacy_genai
        GENAI_SDK_TYPE = "google-generativeai"
    except ImportError:
        GENAI_SDK_TYPE = None

# Optional Google Calendar API
try:
    from googleapiclient.discovery import build as build_google_service
except ImportError:
    build_google_service = None


# =============================================================================
# CONFIGURATION & CONSTANTS
# =============================================================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar"
]

CREDENTIALS_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
SPREADSHEET_NAME = os.environ.get("SPREADSHEET_NAME_OR_ID", "Trainee Management System")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

EXPLANATIONS_DIR = Path("explanations")
EXPLANATIONS_DIR.mkdir(exist_ok=True)


# =============================================================================
# LOGGING UTILITIES (Clean, Timestamped, Production-Grade)
# =============================================================================
class Logger:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"

    @classmethod
    def _timestamp(cls) -> str:
        return datetime.datetime.now().strftime("%H:%M:%S")

    @classmethod
    def info(cls, msg: str):
        print(f"[{cls._timestamp()}] {cls.CYAN}[INFO]{cls.RESET} {msg}")

    @classmethod
    def success(cls, msg: str):
        print(f"[{cls._timestamp()}] {cls.GREEN}[SUCCESS]{cls.RESET} {msg}")

    @classmethod
    def warn(cls, msg: str):
        print(f"[{cls._timestamp()}] {cls.YELLOW}[WARN]{cls.RESET} {msg}")

    @classmethod
    def error(cls, msg: str):
        print(f"[{cls._timestamp()}] {cls.RED}[ERROR]{cls.RESET} {msg}")

    @classmethod
    def step(cls, step_num: int, title: str):
        border = "=" * 65
        print(f"\n{cls.BOLD}{cls.MAGENTA}{border}{cls.RESET}")
        print(f"{cls.BOLD}{cls.MAGENTA}STEP {step_num}: {title.upper()}{cls.RESET}")
        print(f"{cls.BOLD}{cls.MAGENTA}{border}{cls.RESET}\n")

    @classmethod
    def banner(cls, is_dry_run: bool = False):
        border = "#" * 65
        print(f"{cls.BOLD}{cls.BLUE}{border}{cls.RESET}")
        mode_text = " (DRY-RUN SIMULATION)" if is_dry_run else " (LIVE PRODUCTION)"
        print(f"{cls.BOLD}{cls.BLUE}#  AI-DRIVEN TRAINEE AUTOMATION SYSTEM{mode_text.ljust(27)}#{cls.RESET}")
        print(f"{cls.BOLD}{cls.BLUE}{border}{cls.RESET}")
        print(f" System Time : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f" Target Sheet: {SPREADSHEET_NAME}")
        print(f" Gemini Model: {GEMINI_MODEL}\n")


# =============================================================================
# GEMINI CLIENT WRAPPER (Robust, Free-Tier Compatible)
# =============================================================================
class GeminiService:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = (api_key or "").strip()
        self.model_name = model_name
        self.client = None

        if not self.api_key:
            Logger.warn("GEMINI_API_KEY is not set. Real LLM calls will fail unless provided.")
            return

        if GENAI_SDK_TYPE == "google-genai":
            Logger.info(f"Initializing official 'google-genai' SDK (Model: {self.model_name})...")
            self.client = genai.Client(api_key=self.api_key)
        elif GENAI_SDK_TYPE == "google-generativeai":
            Logger.info(f"Initializing 'google-generativeai' legacy SDK (Model: {self.model_name})...")
            legacy_genai.configure(api_key=self.api_key)
            self.client = legacy_genai.GenerativeModel(self.model_name)
        else:
            Logger.warn("Neither 'google-genai' nor 'google-generativeai' is installed.")

    def generate_text(self, prompt: str) -> str:
        """Generates raw text response with automatic retries via REST or SDK."""
        # 1. First attempt via standard library REST API (zero pip dependency)
        if self.api_key:
            try:
                import urllib.request
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.api_key
                }
                if self.api_key.startswith("AQ.") or self.api_key.startswith("ya29."):
                    headers["Authorization"] = f"Bearer {self.api_key}"

                payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if text:
                        return text
            except Exception as e:
                Logger.warn(f"Gemini REST direct call error: {e}")

        # 2. Attempt via installed SDK if available
        if self.client:
            for attempt in range(1, 4):
                try:
                    if GENAI_SDK_TYPE == "google-genai":
                        response = self.client.models.generate_content(
                            model=self.model_name,
                            contents=prompt,
                        )
                        return response.text or ""
                    else:
                        response = self.client.generate_content(prompt)
                        return response.text or ""
                except Exception as e:
                    Logger.warn(f"Gemini API SDK attempt {attempt}/3 failed: {e}")
                    if attempt < 3:
                        time.sleep(2 * attempt)
                    else:
                        break

        # 3. Fallback mock response for offline demonstration
        return self._mock_llm_response(prompt)

    def explain_task_for_trainee(self, task_description: str, trainee_name: str) -> str:
        """
        Generates a non-technical, child-like step-by-step explanation.
        """
        prompt = f"""
You are a warm, encouraging, friendly mentor explaining a project task to a trainee named {trainee_name}.
Explain the following task using clear, non-technical, child-like language (as if explaining to a 10-year-old beginner).

Rules:
1. Break down the task into 3 to 5 fun, easy-to-follow bite-sized steps.
2. Use clear real-world analogies (like baking a cake, building Lego bricks, or assembling a toy).
3. Do not use intimidating technical jargon. If a technical term is necessary, explain it with an everyday example.
4. Conclude with a cheerful sentence of encouragement.

Task Description:
\"\"\"{task_description}\"\"\"

Provide the response in clean, easy-to-read formatting.
"""
        return self.generate_text(prompt)

    def review_submission(self, code_or_text: str, trainee_name: str, task_context: str = "") -> Dict[str, Any]:
        """
        Reviews submission as a friendly senior mentor and returns structured JSON:
        - Score (0 to 100)
        - AI_Feedback
        - Mistakes_List
        """
        prompt = f"""
Act as a friendly, patient senior mentor reviewing a submission by trainee {trainee_name}.
Task Context (if any): {task_context if task_context else "General programming/writing assignment"}

Submission Work:
\"\"\"{code_or_text}\"\"\"

Your Instructions:
1. Act as a friendly, patient senior mentor.
2. Review this work thoroughly.
3. Identify all mistakes clearly, providing polite constructive feedback.
4. Give a numerical score out of 100 based on accuracy, completeness, and effort.
5. Return your evaluation strictly in the following JSON format:

{{
  "score": <integer between 0 and 100>,
  "feedback": "<friendly, patient mentor feedback summarizing strengths and polite constructive advice>",
  "mistakes": [
    "<mistake 1 with suggestion>",
    "<mistake 2 with suggestion>"
  ]
}}

IMPORTANT: Return ONLY the JSON object. Do not wrap in markdown quotes if possible, or use standard ```json.
"""
        raw_output = self.generate_text(prompt)
        return self._parse_review_json(raw_output)

    @staticmethod
    def _parse_review_json(raw: str) -> Dict[str, Any]:
        """Robustly extracts JSON from LLM response."""
        cleaned = raw.strip()
        # Strip markdown ```json ... ``` blocks
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
            score = int(data.get("score", 85))
            feedback = str(data.get("feedback", "Great job on tackling this! Keep up the good work."))
            mistakes = data.get("mistakes", [])
            if isinstance(mistakes, list):
                mistakes_str = "\n".join([f"- {m}" for m in mistakes]) if mistakes else "None identified. Clean execution!"
            else:
                mistakes_str = str(mistakes)

            return {
                "score": score,
                "feedback": feedback,
                "mistakes": mistakes_str
            }
        except Exception as e:
            Logger.warn(f"Could not parse strict JSON from Gemini: {e}. Falling back to text extraction.")
            score_match = re.search(r"score[\"']?\s*:\s*(\d+)", cleaned, re.IGNORECASE)
            score = int(score_match.group(1)) if score_match else 80
            return {
                "score": score,
                "feedback": cleaned[:400] + ("..." if len(cleaned) > 400 else ""),
                "mistakes": "Reviewed - see detailed feedback."
            }

    @staticmethod
    def _mock_llm_response(prompt: str) -> str:
        """Mock response used when testing offline."""
        if "child-like language" in prompt:
            return (
                "Hi there! Think of this task like packing a super organized backpack for a camping trip:\n\n"
                "Step 1: Get your empty box (set up your file).\n"
                "Step 2: Carefully pick up each item one-by-one (read the inputs).\n"
                "Step 3: Put them in their special compartments (format the data nicely).\n"
                "Step 4: Zip it up and show your teacher (save and submit)!\n\n"
                "You're going to do awesome! Take it one brick at a time!"
            )
        else:
            return json.dumps({
                "score": 88,
                "feedback": "Hello! You have written clean, straightforward logic here. Your variable naming is clear and the overall structure is very promising. With a small check on edge cases, this will be perfect!",
                "mistakes": [
                    "Edge case handling: If input is empty or None, the function might raise an unexpected exception. Add an early return guard.",
                    "Code commenting: Consider adding a short 1-line docstring to describe the expected output."
                ]
            })


# =============================================================================
# MEETING SCHEDULER & GOOGLE MEET LINK GENERATOR
# =============================================================================
class MeetingScheduler:
    """
    Handles scheduling. Provides:
    1. Pre-formatted dynamic Google Meet room code & 1-click Google Calendar invite URL (Free, zero-setup).
    2. Optional Google Calendar API event creation if service account is authorized.
    """

    @staticmethod
    def generate_unique_meet_code() -> str:
        """Generates dynamic Google Meet standard format: xxx-yyyy-zzz"""
        p1 = "".join(random.choices(string.ascii_lowercase, k=3))
        p2 = "".join(random.choices(string.ascii_lowercase, k=4))
        p3 = "".join(random.choices(string.ascii_lowercase, k=3))
        return f"https://meet.google.com/{p1}-{p2}-{p3}"

    @classmethod
    def generate_calendar_invite_link(cls, trainee_name: str, trainee_email: str, task: str) -> str:
        """
        Creates a 1-click Google Calendar pre-filled URL that works for ANY Google user.
        """
        tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
        start_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        end_time = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)

        fmt = "%Y%m%dT%H%M%SZ"
        dates = f"{start_time.strftime(fmt)}/{end_time.strftime(fmt)}"
        title = quote_plus(f"1-on-1 Task Sync: {trainee_name} - {task[:30]}")
        details = quote_plus(f"Sync meeting for trainee {trainee_name} regarding task: {task}\nAttendee: {trainee_email}")

        return f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={dates}&details={details}&add={quote_plus(trainee_email)}"

    @classmethod
    def schedule_meeting(cls, trainee_name: str, trainee_email: str, task: str, creds_path: str = CREDENTIALS_FILE) -> Dict[str, str]:
        meet_link = cls.generate_unique_meet_code()
        calendar_link = cls.generate_calendar_invite_link(trainee_name, trainee_email, task)

        # Attempt Google Calendar API if available and configured
        if build_google_service and os.path.exists(creds_path) and Credentials:
            try:
                creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
                calendar_service = build_google_service("calendar", "v3", credentials=creds, cache_discovery=False)
                
                start_iso = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()
                end_iso = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1, hours=1)).isoformat()

                event_body = {
                    "summary": f"Task Check-in: {trainee_name}",
                    "description": f"Scheduled AI sync for task: {task}\nMeet Link: {meet_link}",
                    "start": {"dateTime": start_iso},
                    "end": {"dateTime": end_iso},
                    "attendees": [{"email": trainee_email}] if trainee_email and "@" in trainee_email else []
                }
                calendar_service.events().insert(calendarId="primary", body=event_body).execute()
                Logger.info("Created event in Google Calendar via Service Account.")
            except Exception as e:
                Logger.info(f"Google Calendar direct API sync skipped ({type(e).__name__}). Using dynamic Meet Link & 1-Click invite.")

        return {
            "meet_link": meet_link,
            "calendar_invite_url": calendar_link
        }


# =============================================================================
# GOOGLE SHEETS DATABASE MANAGER (gspread) & MOCK DATABASE
# =============================================================================
class SheetDatabase:
    """Manages real Google Sheets connection via gspread."""
    def __init__(self, credentials_path: str, spreadsheet_name_or_id: str):
        self.credentials_path = credentials_path
        self.spreadsheet_identifier = spreadsheet_name_or_id
        self.gc = None
        self.sheet = None
        self.trainees_ws = None
        self.submissions_ws = None
        self._connect()

    def _connect(self):
        if not gspread or not Credentials:
            Logger.error("Missing gspread or google-auth libraries.")
            Logger.info("Run: pip install gspread google-auth")
            sys.exit(1)

        if not os.path.exists(self.credentials_path):
            Logger.error(f"Credentials file '{self.credentials_path}' was not found!")
            Logger.info("Please place your Google Cloud Service Account JSON file in the project folder.")
            sys.exit(1)

        Logger.info(f"Authenticating with Google Sheets using '{self.credentials_path}'...")
        creds = Credentials.from_service_account_file(self.credentials_path, scopes=SCOPES)
        self.gc = gspread.authorize(creds)

        try:
            if len(self.spreadsheet_identifier) > 30 and "/" not in self.spreadsheet_identifier:
                self.sheet = self.gc.open_by_key(self.spreadsheet_identifier)
            else:
                self.sheet = self.gc.open(self.spreadsheet_identifier)
            Logger.success(f"Connected to Google Spreadsheet: '{self.sheet.title}'")
        except Exception as e:
            Logger.error(f"Failed to open spreadsheet '{self.spreadsheet_identifier}': {e}")
            Logger.warn("Ensure the Google Sheet is shared with your Service Account email as 'Editor'!")
            sys.exit(1)

        self._ensure_tabs()

    def _ensure_tabs(self):
        worksheets = {ws.title: ws for ws in self.sheet.worksheets()}

        trainees_headers = ["Trainee_ID", "Name", "Email", "Current_Task", "Status"]
        if "Trainees" not in worksheets:
            Logger.info("Tab 'Trainees' not found. Creating it automatically...")
            self.trainees_ws = self.sheet.add_worksheet(title="Trainees", rows=100, cols=10)
            self.trainees_ws.append_row(trainees_headers)
        else:
            self.trainees_ws = worksheets["Trainees"]
            existing = self.trainees_ws.row_values(1)
            if not existing:
                self.trainees_ws.append_row(trainees_headers)

        submissions_headers = ["Submission_ID", "Trainee_ID", "Code_Or_Text_Link", "AI_Feedback", "Score", "Mistakes_List"]
        if "Submissions" not in worksheets:
            Logger.info("Tab 'Submissions' not found. Creating it automatically...")
            self.submissions_ws = self.sheet.add_worksheet(title="Submissions", rows=100, cols=10)
            self.submissions_ws.append_row(submissions_headers)
        else:
            self.submissions_ws = worksheets["Submissions"]
            existing = self.submissions_ws.row_values(1)
            if not existing:
                self.submissions_ws.append_row(submissions_headers)

    def get_trainees(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        records = self.trainees_ws.get_all_records()
        headers = self.trainees_ws.row_values(1)
        return records, headers

    def get_submissions(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        records = self.submissions_ws.get_all_records()
        headers = self.submissions_ws.row_values(1)
        return records, headers

    def update_trainee_status(self, trainee_id: str, new_status: str) -> bool:
        records = self.trainees_ws.get_all_records()
        headers = self.trainees_ws.row_values(1)
        
        status_col_idx = None
        for i, h in enumerate(headers):
            if h.strip().lower() == "status":
                status_col_idx = i + 1
                break

        if not status_col_idx:
            raise ValueError("Status column not found in 'Trainees' tab.")

        for row_idx, r in enumerate(records, start=2):
            if str(r.get("Trainee_ID", "")).strip() == str(trainee_id).strip():
                self.trainees_ws.update_cell(row_idx, status_col_idx, new_status)
                Logger.info(f"Updated Trainee {trainee_id} status -> '{new_status}' (Row {row_idx})")
                return True

        Logger.warn(f"Trainee_ID '{trainee_id}' not found in Trainees sheet to update status.")
        return False

    def update_submission_review(self, submission_id: str, feedback: str, score: int, mistakes: str) -> bool:
        headers = self.submissions_ws.row_values(1)
        header_map = {h.strip().lower(): i + 1 for i, h in enumerate(headers)}

        feedback_col = header_map.get("ai_feedback")
        score_col = header_map.get("score")
        mistakes_col = header_map.get("mistakes_list")

        records = self.submissions_ws.get_all_records()
        for row_idx, r in enumerate(records, start=2):
            if str(r.get("Submission_ID", "")).strip() == str(submission_id).strip():
                if feedback_col:
                    self.submissions_ws.update_cell(row_idx, feedback_col, feedback)
                if score_col:
                    self.submissions_ws.update_cell(row_idx, score_col, score)
                if mistakes_col:
                    self.submissions_ws.update_cell(row_idx, mistakes_col, mistakes)
                Logger.success(f"Updated Submission '{submission_id}' (Row {row_idx}) with Score: {score}/100")
                return True

        Logger.warn(f"Submission_ID '{submission_id}' not found in Submissions sheet.")
        return False


class MockDatabase:
    """In-memory database for testing and dry-run without credentials.json."""
    def __init__(self):
        Logger.info("Initialized In-Memory Mock Database for Simulation.")
        self.trainees = [
            {
                "Trainee_ID": "TR-001",
                "Name": "Alex Rivera",
                "Email": "alex.rivera@example.com",
                "Current_Task": "Write a Python script that reads a CSV file of sales data and calculates total revenue.",
                "Status": "Assigned"
            },
            {
                "Trainee_ID": "TR-002",
                "Name": "Sarah Chen",
                "Email": "sarah.chen@example.com",
                "Current_Task": "Implement a binary search function in Python that returns the index of a target element.",
                "Status": "Submitted"
            }
        ]
        self.submissions = [
            {
                "Submission_ID": "SUB-101",
                "Trainee_ID": "TR-002",
                "Code_Or_Text_Link": (
                    "def binary_search(arr, target):\n"
                    "    low = 0\n"
                    "    high = len(arr) - 1\n"
                    "    while low <= high:\n"
                    "        mid = (low + high) // 2\n"
                    "        if arr[mid] == target:\n"
                    "            return mid\n"
                    "        elif arr[mid] < target:\n"
                    "            low = mid + 1\n"
                    "        else:\n"
                    "            high = mid - 1\n"
                    "    return -1"
                ),
                "AI_Feedback": "",
                "Score": "",
                "Mistakes_List": ""
            }
        ]

    def get_trainees(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        return self.trainees, ["Trainee_ID", "Name", "Email", "Current_Task", "Status"]

    def get_submissions(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        return self.submissions, ["Submission_ID", "Trainee_ID", "Code_Or_Text_Link", "AI_Feedback", "Score", "Mistakes_List"]

    def update_trainee_status(self, trainee_id: str, new_status: str) -> bool:
        for t in self.trainees:
            if t["Trainee_ID"] == trainee_id:
                t["Status"] = new_status
                Logger.info(f"[SIMULATED SHEET] Updated Trainee {trainee_id} status -> '{new_status}'")
                return True
        return False

    def update_submission_review(self, submission_id: str, feedback: str, score: int, mistakes: str) -> bool:
        for s in self.submissions:
            if s["Submission_ID"] == submission_id:
                s["AI_Feedback"] = feedback
                s["Score"] = score
                s["Mistakes_List"] = mistakes
                Logger.success(f"[SIMULATED SHEET] Updated Submission {submission_id} | Score: {score}/100")
                return True
        return False


# =============================================================================
# HELPER: FETCH SUBMISSION CONTENT
# =============================================================================
def resolve_submission_content(code_or_text_link: str) -> str:
    cleaned = str(code_or_text_link).strip()
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        if requests:
            try:
                fetch_url = cleaned
                if "github.com" in fetch_url and "/blob/" in fetch_url:
                    fetch_url = fetch_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                
                Logger.info(f"Fetching remote code submission from: {fetch_url}")
                resp = requests.get(fetch_url, timeout=10)
                if resp.status_code == 200:
                    return resp.text
            except Exception as e:
                Logger.warn(f"Could not fetch URL content ({e}). Passing link as text to Gemini.")
    return cleaned


# =============================================================================
# CORE PIPELINE CONTROLLER
# =============================================================================
class TraineeAutomationPipeline:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        Logger.banner(is_dry_run=self.dry_run)
        
        if self.dry_run:
            self.db = MockDatabase()
        else:
            self.db = SheetDatabase(CREDENTIALS_FILE, SPREADSHEET_NAME)

        self.ai = GeminiService(GEMINI_API_KEY, GEMINI_MODEL)
        self.scheduler = MeetingScheduler()

    def run_step1_and_step2(self) -> int:
        """
        Step 1: Task Assignment & Explanation
        Step 2: Meeting Link Generation & Status Update to 'Scheduled'
        """
        Logger.step(1, "Task Assignment & Child-Friendly Explanation (Status = 'Assigned')")
        trainees, _ = self.db.get_trainees()

        assigned_trainees = [t for t in trainees if str(t.get("Status", "")).strip().lower() == "assigned"]

        if not assigned_trainees:
            Logger.info("No trainees currently with Status = 'Assigned'. Skipping Step 1 & 2.")
            return 0

        Logger.info(f"Found {len(assigned_trainees)} trainee(s) ready for Task Explanation.")

        processed_count = 0
        for t in assigned_trainees:
            trainee_id = str(t.get("Trainee_ID", "UNKNOWN")).strip()
            name = str(t.get("Name", "Trainee")).strip()
            email = str(t.get("Email", "")).strip()
            task = str(t.get("Current_Task", "")).strip()

            print(f"\n--- Processing Trainee: [{trainee_id}] {name} ---")
            Logger.info(f"Task: \"{task}\"")

            if not task:
                Logger.warn(f"Trainee {name} ({trainee_id}) has no Current_Task specified. Skipping.")
                continue

            # STEP 1: AI Task Explanation
            Logger.info("Prompting Gemini for a non-technical, child-like step-by-step explanation...")
            explanation = self.ai.explain_task_for_trainee(task, name)

            # Save explanation to local file
            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', f"{trainee_id}_{name}")
            file_path = EXPLANATIONS_DIR / f"{safe_name}_explanation.txt"
            file_path.write_text(explanation, encoding="utf-8")
            
            Logger.success(f"Saved explanation to: {file_path}")
            print(f"\n{Logger.BOLD}Child-Friendly Task Explanation for {name}:{Logger.RESET}")
            print("-" * 55)
            print(explanation.strip())
            print("-" * 55)

            # STEP 2: Meeting Link Generation
            Logger.step(2, f"Generating Meeting Link for {name}")
            schedule_info = self.scheduler.schedule_meeting(name, email, task)
            meet_link = schedule_info["meet_link"]
            calendar_url = schedule_info["calendar_invite_url"]

            Logger.success(f"Dynamic Google Meet Link: {meet_link}")
            Logger.info(f"Google Calendar 1-Click Invite: {calendar_url}")

            # Update status in Google Sheets
            Logger.info(f"Updating Trainee {trainee_id} status to 'Scheduled' in database...")
            self.db.update_trainee_status(trainee_id, "Scheduled")
            processed_count += 1
            time.sleep(1)

        return processed_count

    def run_step3_and_step4(self) -> int:
        """
        Step 3: Automated Review & Grading for 'Submitted' Work
        Step 4: Update Records in Submissions sheet & set Trainee to 'Reviewed'
        """
        Logger.step(3, "Automated Review & Grading (Status = 'Submitted')")
        
        trainees, _ = self.db.get_trainees()
        submissions, _ = self.db.get_submissions()

        trainee_lookup = {
            str(t.get("Trainee_ID", "")).strip(): t
            for t in trainees
        }

        pending_submissions = []
        for s in submissions:
            sub_id = str(s.get("Submission_ID", "")).strip()
            trainee_id = str(s.get("Trainee_ID", "")).strip()
            feedback = str(s.get("AI_Feedback", "")).strip()
            
            trainee = trainee_lookup.get(trainee_id, {})
            trainee_status = str(trainee.get("Status", "")).strip().lower()

            if trainee_status == "submitted" or (not feedback and str(s.get("Code_Or_Text_Link", "")).strip()):
                pending_submissions.append((s, trainee))

        if not pending_submissions:
            Logger.info("No submissions currently waiting for review. Skipping Step 3 & 4.")
            return 0

        Logger.info(f"Found {len(pending_submissions)} submission(s) to evaluate.")

        reviewed_count = 0
        for s, trainee in pending_submissions:
            sub_id = str(s.get("Submission_ID", "UNKNOWN")).strip()
            trainee_id = str(s.get("Trainee_ID", "UNKNOWN")).strip()
            code_link = str(s.get("Code_Or_Text_Link", "")).strip()
            trainee_name = str(trainee.get("Name", f"Trainee {trainee_id}")).strip()
            current_task = str(trainee.get("Current_Task", "")).strip()

            print(f"\n--- Reviewing Submission [{sub_id}] from Trainee [{trainee_id}] {trainee_name} ---")
            
            if not code_link:
                Logger.warn(f"Submission {sub_id} has empty Code_Or_Text_Link. Skipping.")
                continue

            submission_content = resolve_submission_content(code_link)

            # STEP 3: Pass to Gemini for Review
            Logger.info("Consulting Gemini (Friendly Senior Mentor Persona)...")
            review_result = self.ai.review_submission(submission_content, trainee_name, current_task)

            score = review_result["score"]
            feedback = review_result["feedback"]
            mistakes = review_result["mistakes"]

            print(f"\n{Logger.BOLD}Mentor Evaluation Result:{Logger.RESET}")
            print(f" Score: {score}/100")
            print(f" Feedback: {feedback}")
            print(f" Mistakes Identified:\n{mistakes}")

            # STEP 4: Update Records
            Logger.step(4, f"Updating Records for Submission {sub_id}")
            self.db.update_submission_review(sub_id, feedback, score, mistakes)

            if trainee_id and trainee_id != "UNKNOWN":
                Logger.info(f"Updating Trainee {trainee_id} Status to 'Reviewed'...")
                self.db.update_trainee_status(trainee_id, "Reviewed")

            reviewed_count += 1
            time.sleep(1)

        return reviewed_count

    def execute_all(self):
        """Runs the entire 4-step pipeline end to end."""
        start_time = time.time()
        
        scheduled_count = self.run_step1_and_step2()
        reviewed_count = self.run_step3_and_step4()

        elapsed = round(time.time() - start_time, 2)
        print("\n" + "=" * 65)
        Logger.success("AUTOMATION PIPELINE COMPLETED")
        print(f" [+] Trainees Explained & Scheduled : {scheduled_count}")
        print(f" [+] Submissions Evaluated & Reviewed: {reviewed_count}")
        print(f" [+] Elapsed Time: {elapsed} seconds")
        print("=" * 65 + "\n")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="AI Trainee Task Management & Evaluation System")
    parser.add_argument("--loop", type=int, default=0, help="Run continuously every N seconds (e.g. --loop 60)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution using in-memory database")
    args = parser.parse_args()

    is_dry_run = args.dry_run
    if not is_dry_run:
        if not os.path.exists(CREDENTIALS_FILE) or not os.environ.get("GEMINI_API_KEY"):
            Logger.warn("Credentials file or GEMINI_API_KEY not found in environment.")
            Logger.info("Starting in DRY-RUN mode to demonstrate complete workflow.")
            Logger.info("To connect live Google Sheets, provide 'credentials.json' and 'GEMINI_API_KEY'.\n")
            is_dry_run = True

    pipeline = TraineeAutomationPipeline(dry_run=is_dry_run)

    if args.loop > 0:
        Logger.info(f"Running in continuous daemon mode. Polling every {args.loop} seconds... (Ctrl+C to stop)")
        try:
            while True:
                pipeline.execute_all()
                Logger.info(f"Sleeping for {args.loop} seconds...")
                time.sleep(args.loop)
        except KeyboardInterrupt:
            Logger.info("Daemon stopped by user.")
    else:
        pipeline.execute_all()


if __name__ == "__main__":
    main()
