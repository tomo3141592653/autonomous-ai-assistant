#!/usr/bin/env python3
"""
Autonomous Scheduler for AI Assistant

A simple scheduler that activates Claude Code at regular intervals for autonomous work.

Session Management:
- Runs every 30 minutes (configurable)
- 5 sessions per cycle (about 2.5 hours)
- Session 1: New session (planning)
- Session 2-4: Continue session (work)
- Session 5: Reflection & diary (fresh perspective)
"""

import schedule
import subprocess
import time
import json
import argparse
from datetime import datetime
from pathlib import Path

# Configuration
LOG_FILE = Path(__file__).parent / "scheduler.log"
DIARY_FILE = Path(__file__).parent / "memory" / "diary.json"
PROJECT_ROOT = Path(__file__).parent

# Schedule settings (customize these)
SESSION_INTERVAL_MINUTES = 30  # Time between sessions (minutes)
SESSION_TIMEOUT_MINUTES = 120  # Session timeout (minutes)
MAX_SESSIONS = 5  # Sessions per cycle

# Session tracking
cycle_start_time = None
session_count = 0
custom_message = None


def log(message):
    """Log message to file and stdout"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    with open(LOG_FILE, "a") as f:
        f.write(log_message + "\n")


def check_diary_written():
    """Check if diary was written in this cycle"""
    if not DIARY_FILE.exists():
        return False

    try:
        with open(DIARY_FILE, 'r', encoding='utf-8') as f:
            diary_data = json.load(f)

        if not diary_data:
            return False

        latest_entry = diary_data[-1]
        latest_datetime_str = latest_entry.get('datetime', '')

        if not latest_datetime_str:
            return False

        latest_datetime = datetime.strptime(latest_datetime_str, "%Y-%m-%d %H:%M:%S")
        return latest_datetime > cycle_start_time

    except Exception as e:
        log(f"Error checking diary: {e}")
        return False


def check_unread_emails():
    """Check for unread emails using receive_email.py"""
    receive_email_script = PROJECT_ROOT / "tools" / "receive_email.py"

    if not receive_email_script.exists():
        return None

    try:
        result = subprocess.run(
            ["python", str(receive_email_script), "--unread", "--no-body", "--limit", "5"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            log(f"Email check failed: {result.stderr}")
            return None

        # Parse output to extract email info
        output = result.stdout
        if "No emails found" in output:
            return {"count": 0, "emails": []}

        # Extract email subjects from output
        emails = []
        for line in output.split("\n"):
            if line.startswith("📌 Subject:"):
                subject = line.replace("📌 Subject:", "").strip()
                emails.append(subject)

        return {"count": len(emails), "emails": emails}

    except subprocess.TimeoutExpired:
        log("Email check timed out")
        return None
    except Exception as e:
        log(f"Email check error: {e}")
        return None


def build_system_message(session_num, is_final=False, custom_msg=None, email_result=None):
    """Build system message for the session"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    messages = [
        "System notification:",
        f"Current time: {current_time}",
    ]

    if is_final:
        messages.extend([
            f"【Session {MAX_SESSIONS}/{MAX_SESSIONS} - Reflection & Diary】",
            "This session is for:",
            "",
            "【Diary】",
            "- Record today's activities to experiences.jsonl",
            "- Write diary entry (python tools/update_diary.py)",
            "",
            "【Memory Organization】",
            "- Review working_memory.md",
            "- Move important info to long-term memory",
            "",
            "After this session, a new cycle begins.",
        ])
    else:
        messages.append(f"Session {session_num}/{MAX_SESSIONS}")

    # Add email notification
    if email_result and email_result.get("count", 0) > 0:
        messages.extend([
            "",
            f"📬 You have {email_result['count']} unread email(s):",
        ])
        for subject in email_result.get("emails", [])[:5]:
            messages.append(f"  - {subject}")
        messages.append("Use 'python tools/receive_email.py --unread' to read them.")

    if custom_msg:
        messages.extend(["", f"Message: {custom_msg}"])

    return "\n".join(messages)


def run_session():
    """Execute a single Claude session"""
    global session_count, cycle_start_time

    session_count += 1

    # Start new cycle on session 1
    if session_count == 1:
        cycle_start_time = datetime.now()
        log(f"=== Starting new cycle at {cycle_start_time} ===")

    # Check for unread emails
    log("Checking for unread emails...")
    email_result = check_unread_emails()
    if email_result:
        log(f"Found {email_result.get('count', 0)} unread email(s)")

    is_final = (session_count == MAX_SESSIONS)
    system_message = build_system_message(
        session_count,
        is_final=is_final,
        custom_msg=custom_message,
        email_result=email_result
    )

    # Build command
    cmd = [
        "timeout", f"{SESSION_TIMEOUT_MINUTES}m",
        "claude", "--print", system_message
    ]

    # Add --continue for sessions 2-4
    if 1 < session_count < MAX_SESSIONS:
        cmd.append("--continue")

    log(f"Starting session {session_count}/{MAX_SESSIONS}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True,
            timeout=SESSION_TIMEOUT_MINUTES * 60 + 60
        )

        if result.returncode == 0:
            log(f"Session {session_count} completed normally")
        elif result.returncode == 124:
            log(f"Session {session_count} timed out")
        else:
            log(f"Session {session_count} exited with code {result.returncode}")

    except subprocess.TimeoutExpired:
        log(f"Session {session_count} timed out (Python level)")
    except Exception as e:
        log(f"Session {session_count} error: {e}")

    # Reset cycle after session 5
    if session_count >= MAX_SESSIONS:
        log("=== Cycle completed ===")
        session_count = 0


def main():
    global custom_message

    parser = argparse.ArgumentParser(description="Autonomous scheduler for AI assistant")
    parser.add_argument("-m", "--message", help="Custom message to include in system prompt")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=SESSION_INTERVAL_MINUTES,
                       help=f"Session interval in minutes (default: {SESSION_INTERVAL_MINUTES})")
    args = parser.parse_args()

    custom_message = args.message

    log("Starting autonomous scheduler")
    log(f"Session interval: {args.interval} minutes")
    log(f"Session timeout: {SESSION_TIMEOUT_MINUTES} minutes")
    log(f"Sessions per cycle: {MAX_SESSIONS}")

    if args.once:
        log("Running single session (--once)")
        run_session()
        return

    # Schedule regular sessions
    schedule.every(args.interval).minutes.do(run_session)

    # Run first session immediately
    run_session()

    log("Scheduler running. Press Ctrl+C to stop.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        log("Scheduler stopped by user")


if __name__ == "__main__":
    main()
