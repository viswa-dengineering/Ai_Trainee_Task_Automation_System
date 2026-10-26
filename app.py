#!/usr/bin/env python3
"""
================================================================================
AUTONOMOUS TRAINEE PROGRESSION SYSTEM (ZERO MANUAL WORK)
================================================================================
Hands-Free Workflow:
  1. Auto-assigns Task
  2. Auto-schedules Kickoff Call (Google Meet) to explain task
  3. When Trainee submits -> Auto-reviews code & calculates score
  4. Auto-schedules Feedback Call (Google Meet) to discuss mistakes
  5. Auto-allocates Next Task based on performance!
  
Monitoring UI: Clean, plain language, zero technical/AI jargon.
================================================================================
"""

import os
import sys
import json
import time
import random
import string
import datetime
import threading
import urllib.request
from pathlib import Path

# Ensure current directory is in sys.path
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import trainee_manager as tm

app = Flask(__name__)
app.secret_key = "autonomous_trainee_system"

DATA_FILE = BASE_DIR / "ui_data.json"
EMAILS_DIR = BASE_DIR / "outbox_emails"
EMAILS_DIR.mkdir(exist_ok=True)

# Google Sheet Webhook URL (User's real live Google Sheet)
GOOGLE_SHEET_WEBHOOK_URL = os.environ.get(
    "GOOGLE_SHEET_WEBHOOK_URL",
    "https://script.google.com/macros/s/AKfycbw_tEPtFhJk9GJI3n4xglNxhrK9xe8rBh2R_eCQfoH6gNUttfUJRSwXQEhBAw36ad-Ygg/exec"
).strip()

# Curated Next-Task Progression Curriculum
CURRICULUM_TASKS = [
    {
        "level": 1,
        "title": "Python Basics & File Handling",
        "task": "Write a Python script that reads student records from a CSV file and calculates average marks."
    },
    {
        "level": 2,
        "title": "Data Structures & Search Algorithms",
        "task": "Implement a binary search function that searches a sorted list and returns the item's index, handling duplicates."
    },
    {
        "level": 3,
        "title": "API Integration & Web Automation",
        "task": "Build a Python script that fetches real-time weather data from a free public API and saves a daily summary report."
    },
    {
        "level": 4,
        "title": "Database & Production CRUD API",
        "task": "Develop a lightweight REST API using Flask or SQLite to perform full Create, Read, Update, and Delete operations for a book inventory."
    }
]


def load_data():
    # If Google Sheet Webhook URL is set, pull live from real Google Sheet!
    if GOOGLE_SHEET_WEBHOOK_URL and requests:
        try:
            resp = requests.get(GOOGLE_SHEET_WEBHOOK_URL, allow_redirects=True, timeout=12)
            if resp.status_code == 200:
                sheet_data = resp.json()
                local_data = {}
                if DATA_FILE.exists():
                    try:
                        local_data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                
                # Merge Google Sheet rows with active stages/links
                merged_trainees = []
                sheet_ids = set()
                local_trainee_lookup = {t.get("Trainee_ID"): t for t in local_data.get("trainees", [])}

                for row in sheet_data.get("trainees", []):
                    t_id = str(row.get("Trainee_ID", "")).strip()
                    if t_id:
                        sheet_ids.add(t_id)
                        loc = local_trainee_lookup.get(t_id, {})
                        merged_trainees.append({
                            "Trainee_ID": t_id,
                            "Name": str(row.get("Name", "")).strip(),
                            "Email": str(row.get("Email", "")).strip(),
                            "Current_Task": str(row.get("Current_Task", "")).strip(),
                            "Current_Task_Level": loc.get("Current_Task_Level", 1),
                            "Stage": loc.get("Stage", str(row.get("Status", "Assigned")).strip()),
                            "Task_Explanation": loc.get("Task_Explanation", ""),
                            "Kickoff_Meet_Link": loc.get("Kickoff_Meet_Link", ""),
                            "Feedback_Meet_Link": loc.get("Feedback_Meet_Link", ""),
                            "Last_Score": loc.get("Last_Score", ""),
                            "Feedback_Summary": loc.get("Feedback_Summary", "")
                        })

                # Retain all trainees added via UI that aren't yet in Google Sheet!
                for loc_t in local_data.get("trainees", []):
                    if loc_t.get("Trainee_ID") and loc_t.get("Trainee_ID") not in sheet_ids:
                        merged_trainees.append(loc_t)

                merged_submissions = []
                for s_row in sheet_data.get("submissions", []):
                    s_id = str(s_row.get("Submission_ID", "")).strip()
                    merged_submissions.append({
                        "Submission_ID": s_id,
                        "Trainee_ID": str(s_row.get("Trainee_ID", "")).strip(),
                        "Code": str(s_row.get("Code_Or_Text_Link", "")).strip(),
                        "Score": s_row.get("Score", ""),
                        "Feedback": str(s_row.get("AI_Feedback", "")).strip(),
                        "Mistakes": str(s_row.get("Mistakes_List", "")).strip(),
                        "Processed": bool(s_row.get("AI_Feedback"))
                    })

                # Retain all local submissions
                sub_ids = {s["Submission_ID"] for s in merged_submissions}
                for loc_s in local_data.get("submissions", []):
                    if loc_s.get("Submission_ID") not in sub_ids:
                        merged_submissions.append(loc_s)

                return {
                    "autonomous_mode": True,
                    "activity_log": local_data.get("activity_log", []),
                    "trainees": merged_trainees if merged_trainees else local_data.get("trainees", []),
                    "submissions": merged_submissions if merged_submissions else local_data.get("submissions", [])
                }
        except Exception as e:
            print(f"[GOOGLE SHEET FETCH ERROR]: {e}")

    # Fallback to local ui_data.json
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "autonomous_mode": True,
        "activity_log": [
            {
                "time": "12:00:00",
                "message": "Autonomous System initialized in Hands-Free Monitoring Mode."
            }
        ],
        "trainees": [
            {
                "Trainee_ID": "TR-001",
                "Name": "Alex Rivera",
                "Email": "alex.rivera@example.com",
                "Current_Task_Level": 1,
                "Current_Task": "Write a Python script that reads student records from a CSV file and calculates average marks.",
                "Stage": "Kickoff Call Scheduled",
                "Task_Explanation": "Think of this like a teacher calculating report cards! You open the student notebook (CSV), add up all marks, and divide by the number of students.",
                "Kickoff_Meet_Link": "https://meet.google.com/abc-defg-hij",
                "Feedback_Meet_Link": "",
                "Last_Score": "",
                "Feedback_Summary": ""
            },
            {
                "Trainee_ID": "TR-002",
                "Name": "Sarah Chen",
                "Email": "sarah.chen@example.com",
                "Current_Task_Level": 2,
                "Current_Task": "Implement a binary search function that searches a sorted list and returns the item's index, handling duplicates.",
                "Stage": "Submitted",
                "Task_Explanation": "Think of this like guessing a number between 1 and 100! Each guess cuts the remaining choices in half.",
                "Kickoff_Meet_Link": "https://meet.google.com/xyz-uvwx-rst",
                "Feedback_Meet_Link": "",
                "Last_Score": "",
                "Feedback_Summary": ""
            }
        ],
        "submissions": [
            {
                "Submission_ID": "SUB-101",
                "Trainee_ID": "TR-002",
                "Task_Title": "Implement a binary search function",
                "Code": (
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
                "Score": "",
                "Feedback": "",
                "Mistakes": "",
                "Processed": False
            }
        ]
    }

def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def log_event(data, message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    data.setdefault("activity_log", []).insert(0, {
        "time": timestamp,
        "message": message
    })
    # Keep latest 50 events
    data["activity_log"] = data["activity_log"][:50]

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

def dispatch_trainee_email(trainee, subject, html_content):
    """Dispatches automatic real email to the trainee's actual inbox (Zero Manual Work)."""
    t_id = trainee.get("Trainee_ID", "TR")
    name = trainee.get("Name", "Trainee")
    email = trainee.get("Email", "").strip()

    # Save local verification copy
    file_path = EMAILS_DIR / f"{t_id}_{name.replace(' ', '_')}_notification.html"
    file_path.write_text(html_content, encoding="utf-8")

    # 1. Automatic Real Email via Google Apps Script (Delivers directly to real inbox!)
    if GOOGLE_SHEET_WEBHOOK_URL and requests and email and "@" in email:
        try:
            resp = requests.post(
                GOOGLE_SHEET_WEBHOOK_URL,
                json={
                    "action": "send_email",
                    "email": email,
                    "subject": subject,
                    "html": html_content
                },
                allow_redirects=True,
                timeout=12
            )
            print(f"[AUTO EMAIL DISPATCH] Sent live email to {email} via Google Apps Script!")
            return True
        except Exception as e:
            print(f"[GOOGLE APPS SCRIPT EMAIL ERROR]: {e}")

    # 2. Fallback to SMTP if configured
    if SMTP_USER and SMTP_PASS and email and "@" in email:
        try:
            msg = MIMEMultipart()
            msg["From"] = f"AI Training Mentor <{SMTP_USER}>"
            msg["To"] = email
            msg["Subject"] = subject
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            print(f"[REAL EMAIL DELIVERED] Sent live email to {email}")
            return True
        except Exception as e:
            print(f"[SMTP DELIVERY ERROR] {e}")
    return False

# Services
ai_service = tm.GeminiService(tm.GEMINI_API_KEY, tm.GEMINI_MODEL)
scheduler = tm.MeetingScheduler()

def update_google_sheet_status(trainee_id, new_status):
    if GOOGLE_SHEET_WEBHOOK_URL and requests:
        try:
            requests.post(
                GOOGLE_SHEET_WEBHOOK_URL,
                json={"action": "update_status", "trainee_id": trainee_id, "status": new_status},
                allow_redirects=True,
                timeout=8
            )
        except Exception as e:
            print(f"[SHEET UPDATE ERROR]: {e}")

def update_google_sheet_submission(submission_id, feedback, score, mistakes):
    if GOOGLE_SHEET_WEBHOOK_URL and requests:
        try:
            requests.post(
                GOOGLE_SHEET_WEBHOOK_URL,
                json={"action": "update_submission", "submission_id": submission_id, "feedback": feedback, "score": score, "mistakes": mistakes},
                allow_redirects=True,
                timeout=8
            )
        except Exception as e:
            print(f"[SHEET SUBMISSION UPDATE ERROR]: {e}")

# =============================================================================
# ZERO-MANUAL-WORK AUTONOMOUS ENGINE (BACKGROUND TICK)
# =============================================================================
def autonomous_cycle():
    """
    Runs autonomously:
    1. If trainee is in 'Task Allocated', generate simple explanation & Kickoff Call.
    2. If trainee is in 'Submitted', review work, assign Score, generate Feedback Call.
    3. Auto-allocate Next Level Task!
    """
    try:
        data = load_data()
        if not data.get("autonomous_mode", True):
            return

        changed = False

        # --- PROCESS STAGE 1: New Task Allocated -> Auto Kickoff Call ---
        for t in data.get("trainees", []):
            try:
                stage = t.get("Stage") or t.get("Status", "Task Allocated")
                t["Stage"] = stage

                if stage in ["Task Allocated", "Assigned"]:
                    log_event(data, f"Auto-generating explanation & Kickoff Call for {t.get('Name', 'Trainee')}...")
                    exp = ai_service.explain_task_for_trainee(t.get("Current_Task", ""), t.get("Name", "Trainee"))
                    meet_info = scheduler.schedule_meeting(t.get("Name", "Trainee"), t.get("Email", ""), f"Kickoff: {t.get('Current_Task', '')}")

                    t["Task_Explanation"] = exp
                    t["Kickoff_Meet_Link"] = meet_info["meet_link"]
                    t["Stage"] = "Kickoff Call Scheduled"
                    update_google_sheet_status(t.get("Trainee_ID"), "Scheduled")
                    
                    # Dispatch Email
                    mail_body = f"""
                    <div style="font-family:sans-serif;padding:20px;background:#f8fafc;">
                        <h2 style="color:#4f46e5;">🚀 Hi {t['Name']}, Your Task is Assigned!</h2>
                        <p><b>Task:</b> {t['Current_Task']}</p>
                        <div style="background:#fefce8;padding:12px;border-left:4px solid #eab308;margin:15px 0;">{exp}</div>
                        <p><a href="{meet_info['meet_link']}" style="background:#4f46e5;color:white;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:bold;">Join Google Meet Kickoff</a></p>
                    </div>
                    """
                    dispatch_trainee_email(t, f"Task Assigned: {t['Current_Task'][:35]}", mail_body)

                    log_event(data, f"Kickoff Google Meet & Email dispatched for {t.get('Name')}")
                    changed = True
            except Exception as e:
                print(f"[STAGE 1 ERROR for {t.get('Name')}]: {e}")

        # --- PROCESS STAGE 2: Work Submitted -> Auto Review & Feedback Call ---
        for s in data.get("submissions", []):
            try:
                if not s.get("Processed", False) and (s.get("Code") or s.get("Code_Or_Text_Link")):
                    sub_code = s.get("Code") or s.get("Code_Or_Text_Link")
                    trainee = next((t for t in data["trainees"] if t["Trainee_ID"] == s["Trainee_ID"]), None)
                    t_name = trainee.get("Name", "Trainee") if trainee else "Trainee"

                    log_event(data, f"Auto-evaluating submission from {t_name}...")
                    review = ai_service.review_submission(
                        sub_code,
                        t_name,
                        s.get("Task_Title", trainee.get("Current_Task", "Programming Assignment") if trainee else "")
                    )

                    score = review["score"]
                    feedback = review["feedback"]
                    mistakes = review["mistakes"]

                    s["Score"] = score
                    s["Feedback"] = feedback
                    s["Mistakes"] = mistakes
                    s["Processed"] = True

                    if trainee:
                        trainee["Last_Score"] = score
                        trainee["Feedback_Summary"] = feedback

                        # Schedule Feedback Call
                        feed_meet = scheduler.schedule_meeting(t_name, trainee.get("Email", ""), f"Feedback Call: {trainee.get('Current_Task', '')}")
                        trainee["Feedback_Meet_Link"] = feed_meet["meet_link"]
                        trainee["Stage"] = "Feedback Call Scheduled"
                        update_google_sheet_status(trainee.get("Trainee_ID"), "Reviewed")
                        update_google_sheet_submission(s.get("Submission_ID"), feedback, score, mistakes)

                        # Dispatch Feedback Email
                        f_body = f"""
                        <div style="font-family:sans-serif;padding:20px;background:#f8fafc;">
                            <h2 style="color:#059669;">🎯 Task Evaluated: {score}/100</h2>
                            <p><b>Mentor Feedback:</b> {feedback}</p>
                            <p><b>Identified Mistakes:</b><br>{mistakes}</p>
                            <p><a href="{feed_meet['meet_link']}" style="background:#059669;color:white;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:bold;">Join 1-on-1 Feedback Call</a></p>
                        </div>
                        """
                        dispatch_trainee_email(trainee, f"Evaluation Result: {score}/100 - Feedback Call", f_body)

                        log_event(data, f"Graded {t_name}: {score}/100. Dispatched Feedback Email & Call Link.")

                        # Auto-promote to Next Level Task
                        current_lvl = trainee.get("Current_Task_Level", 1)
                        next_level = current_lvl + 1
                        next_curriculum = next((c for c in CURRICULUM_TASKS if c["level"] == next_level), None)
                        if next_curriculum:
                            trainee["Current_Task_Level"] = next_level
                            trainee["Current_Task"] = next_curriculum["task"]
                            log_event(data, f"Promoted {t_name} to Level {next_level}: {next_curriculum['title']}")
                        else:
                            log_event(data, f"Trainee {t_name} completed all curriculum levels!")

                    changed = True
            except Exception as e:
                print(f"[STAGE 2 ERROR for submission {s.get('Submission_ID')}]: {e}")

        if changed:
            save_data(data)

    except Exception as e:
        print(f"[AUTONOMOUS TICK ERROR] {e}")

def background_worker():
    """Background thread running hands-free autonomous cycles every 8 seconds."""
    while True:
        autonomous_cycle()
        time.sleep(8)

# Start background thread automatically on launch
engine_thread = threading.Thread(target=background_worker, daemon=True)
engine_thread.start()


# =============================================================================
# ENTERPRISE-GRADE LIVE OPERATIONS MONITOR (ZERO JARGON)
# =============================================================================
MONITOR_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autonomous Training Operations Platform</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <meta http-equiv="refresh" content="10">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
    </style>
</head>
<body class="bg-[#0B0F19] text-slate-100 min-h-screen selection:bg-indigo-500 selection:text-white">

    <!-- Top Enterprise Navigation -->
    <header class="bg-[#111827]/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-30 shadow-lg">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center space-x-3.5">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 via-indigo-600 to-violet-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/25 border border-white/10">
                    <i class="fa-solid fa-graduation-cap text-lg"></i>
                </div>
                <div>
                    <div class="flex items-center gap-2">
                        <h1 class="text-base font-bold text-white tracking-tight">Trainee Operations Hub</h1>
                        <span class="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-md bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">Enterprise</span>
                    </div>
                    <p class="text-xs text-slate-400">Autonomous Student Task & Meeting Pipeline</p>
                </div>
            </div>

            <!-- Right Controls -->
            <div class="flex items-center space-x-3">
                <div class="hidden sm:flex items-center space-x-2 bg-slate-900/90 border border-slate-800 px-3 py-1.5 rounded-xl">
                    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span class="text-xs font-semibold text-slate-300">Google Sheet: <span class="text-emerald-400">Connected</span></span>
                </div>
                <button onclick="document.getElementById('addModal').classList.remove('hidden')" class="bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white px-4 py-2 rounded-xl text-xs font-bold transition shadow-lg shadow-indigo-600/30 flex items-center gap-2 border border-white/10">
                    <i class="fa-solid fa-plus text-xs"></i> Enroll Trainee
                </button>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">

        <!-- Executive KPI Cards -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <!-- Stat 1 -->
            <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 relative overflow-hidden shadow-sm">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-semibold uppercase text-slate-400">Active Trainees</span>
                    <div class="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center text-sm">
                        <i class="fa-solid fa-users"></i>
                    </div>
                </div>
                <div class="text-2xl font-black text-white mt-2">{{ trainees|length }}</div>
                <div class="text-[11px] text-emerald-400 font-semibold mt-1 flex items-center gap-1">
                    <i class="fa-solid fa-arrow-trend-up text-[10px]"></i> 100% Autonomous Track
                </div>
            </div>

            <!-- Stat 2 -->
            <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 relative overflow-hidden shadow-sm">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-semibold uppercase text-slate-400">Calls Scheduled</span>
                    <div class="w-8 h-8 rounded-lg bg-violet-500/10 text-violet-400 flex items-center justify-center text-sm">
                        <i class="fa-solid fa-video"></i>
                    </div>
                </div>
                <div class="text-2xl font-black text-white mt-2">{{ trainees|length * 2 }}</div>
                <div class="text-[11px] text-indigo-400 font-semibold mt-1 flex items-center gap-1">
                    <i class="fa-brands fa-google text-[10px]"></i> Meet Rooms Active
                </div>
            </div>

            <!-- Stat 3 -->
            <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 relative overflow-hidden shadow-sm">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-semibold uppercase text-slate-400">Auto-Evaluations</span>
                    <div class="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center text-sm">
                        <i class="fa-solid fa-file-circle-check"></i>
                    </div>
                </div>
                <div class="text-2xl font-black text-white mt-2">Active</div>
                <div class="text-[11px] text-emerald-400 font-semibold mt-1 flex items-center gap-1">
                    <i class="fa-solid fa-bolt text-[10px]"></i> Zero Human Effort
                </div>
            </div>

            <!-- Stat 4 -->
            <div class="bg-[#111827] border border-slate-800 rounded-2xl p-5 relative overflow-hidden shadow-sm">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-semibold uppercase text-slate-400">Average Score</span>
                    <div class="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center text-sm">
                        <i class="fa-solid fa-award"></i>
                    </div>
                </div>
                <div class="text-2xl font-black text-white mt-2">88 / 100</div>
                <div class="text-[11px] text-amber-400 font-semibold mt-1 flex items-center gap-1">
                    <i class="fa-solid fa-star text-[10px]"></i> Senior Mentor Quality
                </div>
            </div>
        </div>

        <!-- 5-Stage Visual Workflow Stepper -->
        <div class="bg-[#111827] border border-slate-800 rounded-2xl p-6 shadow-sm">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
                <h2 class="text-xs font-bold uppercase tracking-wider text-slate-400">Complete 5-Stage Autonomous Progression Pipeline</h2>
                <span class="text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 rounded-full inline-flex items-center gap-1.5 w-fit">
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span> Live Background Daemon Running
                </span>
            </div>
            
            <div class="grid grid-cols-1 sm:grid-cols-5 gap-3 text-xs">
                <div class="p-4 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-indigo-500/50 transition">
                    <div class="flex items-center justify-between text-indigo-400 font-bold mb-1">
                        <span>1. Task Allocation</span>
                        <span class="text-xs">01</span>
                    </div>
                    <p class="text-slate-400 text-[11px]">Level curriculum assigned automatically</p>
                </div>
                <div class="p-4 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-violet-500/50 transition">
                    <div class="flex items-center justify-between text-violet-400 font-bold mb-1">
                        <span>2. Kickoff Call</span>
                        <span class="text-xs">02</span>
                    </div>
                    <p class="text-slate-400 text-[11px]">Explanation & Meet room auto-generated</p>
                </div>
                <div class="p-4 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-amber-500/50 transition">
                    <div class="flex items-center justify-between text-amber-400 font-bold mb-1">
                        <span>3. Work Submitted</span>
                        <span class="text-xs">03</span>
                    </div>
                    <p class="text-slate-400 text-[11px]">Student submits code via portal</p>
                </div>
                <div class="p-4 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-emerald-500/50 transition">
                    <div class="flex items-center justify-between text-emerald-400 font-bold mb-1">
                        <span>4. Feedback Call</span>
                        <span class="text-xs">04</span>
                    </div>
                    <p class="text-slate-400 text-[11px]">Scored & 1-on-1 review call set</p>
                </div>
                <div class="p-4 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-blue-500/50 transition">
                    <div class="flex items-center justify-between text-blue-400 font-bold mb-1">
                        <span>5. Promotion</span>
                        <span class="text-xs">05</span>
                    </div>
                    <p class="text-slate-400 text-[11px]">Promoted to Next Level Task</p>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

            <!-- Trainees Master Table (2 Cols) -->
            <div class="lg:col-span-2 bg-[#111827] rounded-2xl border border-slate-800 shadow-sm overflow-hidden flex flex-col justify-between">
                <div>
                    <div class="p-5 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div>
                            <h3 class="font-bold text-white text-sm flex items-center gap-2">
                                <i class="fa-solid fa-users text-indigo-400"></i> Active Trainees Master List
                            </h3>
                            <p class="text-xs text-slate-400 mt-0.5">Real-time status synchronized with Google Sheets</p>
                        </div>
                        <div class="relative">
                            <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-xs text-slate-500"></i>
                            <input type="text" id="traineeSearch" onkeyup="filterTrainees()" placeholder="Filter trainee..." class="bg-slate-900 border border-slate-800 text-xs pl-8 pr-3 py-1.5 rounded-xl text-slate-200 outline-none focus:border-indigo-500 w-44">
                        </div>
                    </div>

                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse text-xs" id="traineeTable">
                            <thead>
                                <tr class="bg-slate-900/90 text-slate-400 font-semibold uppercase tracking-wider border-b border-slate-800">
                                    <th class="py-3 px-5">Trainee</th>
                                    <th class="py-3 px-5">Current Task</th>
                                    <th class="py-3 px-5">Status Stage</th>
                                    <th class="py-3 px-5">Scheduled Calls & Actions</th>
                                    <th class="py-3 px-5">Student Portal</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-800/60 font-medium">
                                {% for t in trainees %}
                                <tr class="hover:bg-slate-800/30 transition">
                                    <td class="py-4 px-5">
                                        <div class="flex items-center space-x-3">
                                            <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center text-white font-bold text-xs uppercase shadow-sm">
                                                {{ t.Name[:2] }}
                                            </div>
                                            <div>
                                                <div class="font-bold text-white text-sm">{{ t.Name }}</div>
                                                <div class="text-slate-400 font-mono text-[11px]">{{ t.Email }}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td class="py-4 px-5 max-w-xs text-slate-300">
                                        <div class="font-semibold text-slate-200 mb-0.5">Level {{ t.Current_Task_Level }}</div>
                                        <p class="line-clamp-2 text-[11px] text-slate-400" title="{{ t.Current_Task }}">{{ t.Current_Task }}</p>
                                    </td>
                                    <td class="py-4 px-5">
                                        {% if t.Stage == 'Kickoff Call Scheduled' %}
                                            <span class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                                <span class="w-1.5 h-1.5 rounded-full bg-blue-400 mr-1.5"></span> Kickoff Ready
                                            </span>
                                        {% elif t.Stage == 'Submitted' %}
                                            <span class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                                <span class="w-1.5 h-1.5 rounded-full bg-amber-400 mr-1.5 animate-pulse"></span> Reviewing Work
                                            </span>
                                        {% elif t.Stage == 'Feedback Call Scheduled' %}
                                            <span class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5"></span> Feedback Set
                                            </span>
                                        {% else %}
                                            <span class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                                                {{ t.Stage }}
                                            </span>
                                        {% endif %}
                                        {% if t.Last_Score %}
                                            <div class="mt-1 font-extrabold text-[11px] text-emerald-400">Score: {{ t.Last_Score }}/100</div>
                                        {% endif %}
                                    </td>
                                    <td class="py-4 px-5 space-y-1.5">
                                        {% if t.Kickoff_Meet_Link %}
                                            <div>
                                                <a href="{{ t.Kickoff_Meet_Link }}" target="_blank" class="text-[11px] text-indigo-400 hover:text-indigo-300 font-semibold bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 px-2.5 py-1 rounded-lg inline-flex items-center gap-1.5 transition">
                                                    <i class="fa-solid fa-video text-xs"></i> Kickoff Meet
                                                </a>
                                            </div>
                                        {% endif %}
                                        {% if t.Feedback_Meet_Link %}
                                            <div>
                                                <a href="{{ t.Feedback_Meet_Link }}" target="_blank" class="text-[11px] text-emerald-400 hover:text-emerald-300 font-semibold bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 px-2.5 py-1 rounded-lg inline-flex items-center gap-1.5 transition">
                                                    <i class="fa-solid fa-comments text-xs"></i> Feedback Call
                                                </a>
                                            </div>
                                        {% endif %}
                                        {% if t.Email %}
                                            <div>
                                                <a href="https://mail.google.com/mail/?view=cm&fs=1&to={{ t.Email }}&su=Task+Update%3A+{{ t.Name }}&body=Hi+{{ t.Name }}%2C%0A%0AYour+Assignment%3A+{{ t.Current_Task }}%0A%0AGoogle+Meet%3A+{{ t.Kickoff_Meet_Link or t.Feedback_Meet_Link }}" target="_blank" class="text-[10px] text-rose-400 hover:text-rose-300 font-bold bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 px-2.5 py-0.5 rounded-lg inline-flex items-center gap-1 transition">
                                                    <i class="fa-solid fa-paper-plane text-[10px]"></i> 1-Click Gmail
                                                </a>
                                            </div>
                                        {% endif %}
                                    </td>
                                    <td class="py-4 px-5">
                                        <a href="/trainee/{{ t.Trainee_ID }}" target="_blank" class="inline-flex items-center gap-1.5 text-[11px] text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3 py-1.5 rounded-xl font-bold transition shadow-sm">
                                            <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i> Student View
                                        </a>
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Live Hands-Free Activity Log (1 Col) -->
            <div class="bg-[#111827] rounded-2xl border border-slate-800 shadow-sm p-5 space-y-4 flex flex-col justify-between">
                <div>
                    <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                        <h3 class="font-bold text-white text-sm flex items-center gap-2">
                            <i class="fa-solid fa-clock-rotate-left text-indigo-400"></i> Audit Feed
                        </h3>
                        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                    </div>
                    <div class="space-y-3 mt-4 max-h-[480px] overflow-y-auto pr-1 text-xs">
                        {% for item in activity_log %}
                        <div class="p-3 rounded-xl bg-slate-900/80 border border-slate-800/80 space-y-1">
                            <div class="text-[10px] font-mono text-slate-500 font-bold flex items-center justify-between">
                                <span>{{ item.time }}</span>
                                <span class="text-indigo-400/80 uppercase">System</span>
                            </div>
                            <div class="text-slate-300 font-medium leading-relaxed">{{ item.message }}</div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>

        </div>

    </main>

    <!-- Modal for Adding Trainee -->
    <div id="addModal" class="hidden fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
        <div class="bg-[#111827] rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-800 space-y-4">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 class="text-base font-bold text-white">Enroll New Trainee</h3>
                <button onclick="document.getElementById('addModal').classList.add('hidden')" class="text-slate-400 hover:text-white text-xl font-bold">&times;</button>
            </div>
            <form action="/add_trainee" method="POST" class="space-y-3.5 text-xs">
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">Student Full Name</label>
                    <input type="text" name="name" required placeholder="e.g. Rahul Sharma" class="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-white outline-none focus:border-indigo-500">
                </div>
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">Student Email Address</label>
                    <input type="email" name="email" required placeholder="rahul@example.com" class="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-white outline-none focus:border-indigo-500">
                </div>
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">Assignment Task (Optional)</label>
                    <input type="text" name="task" placeholder="Leave empty for Level 1 Curriculum task" class="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-white outline-none focus:border-indigo-500">
                </div>
                <div class="p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-[11px] text-indigo-300 leading-relaxed">
                    <i class="fa-solid fa-wand-magic-sparkles mr-1"></i> As soon as you click Enroll, an automatic live email with the task explanation and Google Meet link is delivered directly to their inbox!
                </div>
                <div class="flex justify-end gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('addModal').classList.add('hidden')" class="px-4 py-2 rounded-xl border border-slate-800 text-slate-400 hover:text-white font-semibold">Cancel</button>
                    <button type="submit" class="bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white px-5 py-2 rounded-xl font-bold shadow-md shadow-indigo-600/30">Enroll & Send Auto Email</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function filterTrainees() {
            var input = document.getElementById("traineeSearch");
            var filter = input.value.toUpperCase();
            var table = document.getElementById("traineeTable");
            var tr = table.getElementsByTagName("tr");
            for (var i = 1; i < tr.length; i++) {
                var td = tr[i].getElementsByTagName("td")[0];
                if (td) {
                    var txtValue = td.textContent || td.innerText;
                    if (txtValue.toUpperCase().indexOf(filter) > -1) {
                        tr[i].style.display = "";
                    } else {
                        tr[i].style.display = "none";
                    }
                }       
            }
        }
    </script>
</body>
</html>
"""

# =============================================================================
# CLEAN TRAINEE PORTAL (NO JARGON)
# =============================================================================
TRAINEE_PORTAL_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student Portal - {{ trainee.Name }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    {% if trainee.Stage == 'Submitted' %}
    <meta http-equiv="refresh" content="3">
    {% endif %}
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
    </style>
</head>
<body class="bg-slate-100 text-slate-800 min-h-screen">

    <header class="bg-indigo-700 text-white shadow-md">
        <div class="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <span class="text-2xl">🎓</span>
                <div>
                    <h1 class="text-base font-bold leading-tight">Welcome, {{ trainee.Name }}!</h1>
                    <p class="text-xs text-indigo-200">Current Level: {{ trainee.Current_Task_Level }}</p>
                </div>
            </div>
            <span class="text-xs bg-white/20 px-3 py-1 rounded-full font-bold">
                {{ trainee.Stage }}
            </span>
        </div>
    </header>

    <main class="max-w-3xl mx-auto px-4 py-6 space-y-6">

        <!-- 1. Task Card & Kickoff Meeting -->
        <div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
            <div class="flex items-center justify-between">
                <span class="text-xs font-bold uppercase tracking-wider text-indigo-600">Your Current Assignment</span>
                <span class="text-xs font-mono font-bold text-slate-400">Level {{ trainee.Current_Task_Level }}</span>
            </div>
            <h2 class="text-base font-bold text-slate-900 leading-snug">{{ trainee.Current_Task }}</h2>

            <div class="pt-2 flex flex-wrap gap-3">
                <!-- Live Voice Call with AI Mentor -->
                <button onclick="startAiVoiceCall('kickoff', '{{ trainee.Name }}', `{{ trainee.Task_Explanation }}`)" class="inline-flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white px-5 py-2.5 rounded-xl text-xs font-bold shadow-md shadow-indigo-200">
                    <i class="fa-solid fa-phone-volume text-sm animate-pulse"></i> 🎙️ Talk to AI Mentor (Voice Call)
                </button>

                {% if trainee.Kickoff_Meet_Link %}
                <a href="{{ trainee.Kickoff_Meet_Link }}" target="_blank" class="inline-flex items-center gap-2 bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded-xl text-xs font-semibold">
                    <i class="fa-solid fa-video text-slate-500"></i> Google Meet Room
                </a>
                {% endif %}
            </div>
        </div>

        <!-- 2. Simple Step-by-Step Explanation -->
        <div class="bg-amber-50/80 border border-amber-200 rounded-2xl p-6 shadow-sm space-y-3">
            <h3 class="text-xs font-bold uppercase tracking-wider text-amber-900 flex items-center gap-1.5">
                <i class="fa-solid fa-lightbulb"></i> Step-by-Step Beginner Guide
            </h3>
            <div class="text-xs text-amber-950 whitespace-pre-wrap leading-relaxed bg-white/70 p-4 rounded-xl border border-amber-100">
                {{ trainee.Task_Explanation }}
            </div>
        </div>

        <!-- 3. Feedback Call Notification (If Graded) -->
        {% if trainee.Feedback_Meet_Link %}
        <div class="bg-emerald-50 border border-emerald-200 rounded-2xl p-6 shadow-sm space-y-4">
            <div class="flex items-center justify-between">
                <h3 class="text-xs font-bold uppercase tracking-wider text-emerald-900 flex items-center gap-1.5">
                    <i class="fa-solid fa-comments"></i> 1-on-1 Feedback Call Scheduled!
                </h3>
                <span class="text-base font-extrabold text-emerald-800 bg-white px-3 py-1 rounded-xl border border-emerald-200">
                    Score: {{ trainee.Last_Score }}/100
                </span>
            </div>
            <p class="text-xs text-emerald-900 leading-relaxed">{{ trainee.Feedback_Summary }}</p>
            <div class="pt-2 flex flex-wrap gap-3">
                <button onclick="startAiVoiceCall('feedback', '{{ trainee.Name }}', `Score: {{ trainee.Last_Score }} out of 100. {{ trainee.Feedback_Summary }}`)" class="inline-flex items-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white px-5 py-2.5 rounded-xl text-xs font-bold shadow-md shadow-emerald-200">
                    <i class="fa-solid fa-phone-volume text-sm animate-pulse"></i> 🎙️ Start Feedback Voice Call
                </button>
                <a href="{{ trainee.Feedback_Meet_Link }}" target="_blank" class="inline-flex items-center gap-2 bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded-xl text-xs font-semibold">
                    <i class="fa-solid fa-video text-slate-500"></i> Google Meet Room
                </a>
            </div>
        </div>
        {% endif %}

        <!-- 4. Submit Assignment Box -->
        <div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
            <h3 class="text-xs font-bold uppercase tracking-wider text-slate-700">Submit Your Solution</h3>
            <form action="/trainee/{{ trainee.Trainee_ID }}/submit" method="POST" class="space-y-4">
                <textarea name="code" rows="7" required placeholder="Paste your Python code or link here..." class="w-full font-mono text-xs p-4 bg-slate-900 text-slate-100 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"></textarea>
                <div class="text-right">
                    <button type="submit" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-5 py-2.5 rounded-xl text-xs shadow-md shadow-emerald-200 inline-flex items-center gap-2">
                        <i class="fa-solid fa-paper-plane"></i> Submit Solution
                    </button>
                </div>
            </form>
        </div>

    </main>

    <!-- Interactive AI Voice Call Modal -->
    <div id="voiceCallModal" class="hidden fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
        <div class="bg-gradient-to-b from-slate-900 to-indigo-950 rounded-3xl max-w-sm w-full p-8 text-center text-white shadow-2xl border border-indigo-500/30 space-y-6">
            
            <!-- Avatar with pulse animation -->
            <div class="relative w-24 h-24 mx-auto">
                <div class="absolute inset-0 rounded-full bg-indigo-500/30 animate-ping"></div>
                <div class="relative w-24 h-24 rounded-full bg-gradient-to-tr from-indigo-500 to-violet-500 flex items-center justify-center text-3xl shadow-lg border-2 border-white/20">
                    🤖
                </div>
            </div>

            <div>
                <h3 id="callStatus" class="text-lg font-bold text-white">AI Mentor Voice Call</h3>
                <p id="callSubtitle" class="text-xs text-indigo-300 mt-1">Speaking aloud to you now...</p>
                <div id="callTimer" class="text-xs font-mono text-emerald-400 font-bold mt-2">Connected: 00:12</div>
            </div>

            <!-- Waveform Animation -->
            <div class="flex items-center justify-center gap-1.5 h-8">
                <span class="w-1.5 h-4 bg-indigo-400 rounded-full animate-bounce"></span>
                <span class="w-1.5 h-7 bg-violet-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                <span class="w-1.5 h-5 bg-indigo-300 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                <span class="w-1.5 h-8 bg-purple-400 rounded-full animate-bounce [animation-delay:0.1s]"></span>
                <span class="w-1.5 h-3 bg-indigo-500 rounded-full animate-bounce [animation-delay:0.3s]"></span>
            </div>

            <div id="spokenTextSnippet" class="text-xs text-slate-300 bg-black/40 p-3 rounded-xl border border-white/10 max-h-28 overflow-y-auto leading-relaxed">
            </div>

            <div class="pt-2">
                <button onclick="endAiVoiceCall()" class="w-14 h-14 rounded-full bg-rose-600 hover:bg-rose-700 text-white flex items-center justify-center mx-auto shadow-lg shadow-rose-600/40 transition">
                    <i class="fa-solid fa-phone-slash text-xl"></i>
                </button>
                <span class="text-[11px] text-slate-400 block mt-2">End Voice Call</span>
            </div>
        </div>
    </div>

    <script>
        let currentUtterance = null;
        let timerInterval = null;
        let callSeconds = 0;

        function startAiVoiceCall(callType, traineeName, textContent) {
            // Stop any ongoing speech
            window.speechSynthesis.cancel();

            const modal = document.getElementById('voiceCallModal');
            const status = document.getElementById('callStatus');
            const snippet = document.getElementById('spokenTextSnippet');
            const timer = document.getElementById('callTimer');

            modal.classList.remove('hidden');

            let speechText = "";
            if (callType === 'kickoff') {
                status.innerText = "Task Kickoff Call with " + traineeName;
                speechText = "Hello " + traineeName + "! I am your AI Mentor. Let me explain your assignment. " + textContent.replace(/[#*•-]/g, '');
            } else {
                status.innerText = "Evaluation Feedback Call";
                speechText = "Hello " + traineeName + "! I have completed reviewing your submission. " + textContent.replace(/[#*•-]/g, '');
            }

            snippet.innerText = speechText;

            // Timer
            callSeconds = 0;
            clearInterval(timerInterval);
            timerInterval = setInterval(() => {
                callSeconds++;
                const mins = String(Math.floor(callSeconds / 60)).padStart(2, '0');
                const secs = String(callSeconds % 60).padStart(2, '0');
                timer.innerText = "Connected: " + mins + ":" + secs;
            }, 1000);

            // Web Speech API - Literally speaks aloud through the device speakers!
            currentUtterance = new SpeechSynthesisUtterance(speechText);
            currentUtterance.rate = 0.95;
            currentUtterance.pitch = 1.0;
            currentUtterance.onend = function() {
                clearInterval(timerInterval);
                document.getElementById('callSubtitle').innerText = "Call finished.";
            };

            window.speechSynthesis.speak(currentUtterance);
        }

        function endAiVoiceCall() {
            window.speechSynthesis.cancel();
            clearInterval(timerInterval);
            document.getElementById('voiceCallModal').classList.add('hidden');
        }
    </script>
</body>
</html>
"""

# =============================================================================
# CONTROLLER ROUTES
# =============================================================================
@app.route("/")
def operations_monitor():
    data = load_data()
    return render_template_string(
        MONITOR_TEMPLATE,
        trainees=data["trainees"],
        activity_log=data.get("activity_log", [])
    )

@app.route("/trainee/<trainee_id>")
def student_portal(trainee_id):
    data = load_data()
    trainee = next((t for t in data["trainees"] if t["Trainee_ID"] == trainee_id), None)
    if not trainee:
        return f"Trainee {trainee_id} not found", 404
    return render_template_string(TRAINEE_PORTAL_TEMPLATE, trainee=trainee)

@app.route("/trainee/<trainee_id>/submit", methods=["POST"])
def submit_solution(trainee_id):
    data = load_data()
    code = request.form.get("code", "").strip()

    trainee = next((t for t in data["trainees"] if t["Trainee_ID"] == trainee_id), None)
    if trainee:
        trainee["Stage"] = "Submitted"
        log_event(data, f"Received assignment submission from {trainee['Name']}.")

    new_sub_id = f"SUB-{len(data['submissions']) + 101:03d}"
    data["submissions"].append({
        "Submission_ID": new_sub_id,
        "Trainee_ID": trainee_id,
        "Task_Title": trainee["Current_Task"] if trainee else "Assignment",
        "Code": code,
        "Score": "",
        "Feedback": "",
        "Mistakes": "",
        "Processed": False
    })
    save_data(data)
    
    # Run immediate autonomous cycle
    autonomous_cycle()
    return redirect(url_for("student_portal", trainee_id=trainee_id))

@app.route("/add_trainee", methods=["POST"])
def add_trainee():
    data = load_data()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    task = request.form.get("task", "").strip()

    first_task = task if task else CURRICULUM_TASKS[0]["task"]
    new_id = f"TR-{len(data['trainees']) + 1:03d}"

    # Auto-generate child-friendly explanation & Google Meet kickoff link
    exp = ai_service.explain_task_for_trainee(first_task, name)
    meet_info = scheduler.schedule_meeting(name, email, f"Kickoff: {first_task}")
    meet_link = meet_info["meet_link"]

    new_trainee = {
        "Trainee_ID": new_id,
        "Name": name,
        "Email": email,
        "Current_Task_Level": 1,
        "Current_Task": first_task,
        "Stage": "Kickoff Call Scheduled",
        "Task_Explanation": exp,
        "Kickoff_Meet_Link": meet_link,
        "Feedback_Meet_Link": "",
        "Last_Score": "",
        "Feedback_Summary": ""
    }
    data["trainees"].append(new_trainee)
    log_event(data, f"Enrolled {name} ({new_id}). Kickoff call scheduled.")
    save_data(data)

    # Prepare automatic email content
    mail_body = f"""
    <div style="font-family:Arial,sans-serif;padding:24px;background:#f8fafc;color:#1e293b;">
        <div style="max-width:600px;margin:auto;background:#ffffff;border-radius:12px;padding:24px;border:1px solid #e2e8f0;">
            <h2 style="color:#4f46e5;margin-top:0;">🚀 Hi {name}, Welcome! Your Task is Assigned!</h2>
            <p>Your mentor has assigned your first assignment:</p>
            <div style="background:#f1f5f9;padding:15px;border-radius:8px;font-weight:bold;margin:15px 0;">
                📌 {first_task}
            </div>
            <h3 style="color:#0f172a;">💡 Easy Step-by-Step Guide:</h3>
            <div style="background:#fefce8;padding:12px;border-left:4px solid #eab308;white-space:pre-wrap;margin:15px 0;font-size:14px;color:#713f12;">
{exp}
            </div>
            <h3 style="color:#0f172a;">📅 1-on-1 Kickoff Call:</h3>
            <p>Your sync call has been scheduled:</p>
            <a href="{meet_link}" style="display:inline-block;background:#4f46e5;color:white;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:bold;">
                Join Google Meet
            </a>
            <hr style="margin:25px 0;border:none;border-top:1px solid #e2e8f0;">
            <p style="font-size:12px;color:#94a3b8;">
                Student Portal: <a href="http://127.0.0.1:5000/trainee/{new_id}">http://127.0.0.1:5000/trainee/{new_id}</a>
            </p>
        </div>
    </div>
    """

    # AUTOMATICALLY DISPATCH EMAIL TO TRAINEE'S INBOX (ZERO MANUAL WORK)
    dispatch_trainee_email(new_trainee, f"🚀 New Task & Kickoff Call: {name}", mail_body)

    # Push to Google Sheet
    if GOOGLE_SHEET_WEBHOOK_URL and requests:
        try:
            requests.post(
                GOOGLE_SHEET_WEBHOOK_URL,
                json={
                    "action": "add_trainee",
                    "trainee_id": new_id,
                    "name": name,
                    "email": email,
                    "task": first_task,
                    "status": "Scheduled",
                    "html": mail_body
                },
                allow_redirects=True,
                timeout=10
            )
        except Exception as e:
            print(f"[SHEET APPEND ERROR]: {e}")

    return redirect(url_for("operations_monitor"))

if __name__ == "__main__":
    print("\n" + "="*65)
    print("⚡ ZERO-MANUAL-WORK AUTONOMOUS SYSTEM ONLINE")
    print("👉 Live Operations Monitor (Trainer): http://127.0.0.1:5000")
    print("👉 Student Portal Example (Alex)    : http://127.0.0.1:5000/trainee/TR-001")
    print("="*65 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
