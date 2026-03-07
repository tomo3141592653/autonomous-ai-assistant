#!/usr/bin/env python3
"""
Ayumu Gateway - Event-driven scheduler

An event-driven architecture scheduler inspired by OpenClaw's design.
Manages both periodic execution (heartbeat) and events (email, Discord, etc.)
through a unified Gateway.

Event sources:
- TimerSource: Heartbeat at configurable intervals (drives session cycles)
- EmailSource: Polling for unread emails
- DiscordSource: Discord bot message monitoring (optional)
- VoiceSource: Wake word detection via hearing log file (optional)
- CronSource: Cron-scheduled tasks from cron.json
- OneTimerSource: One-shot timers from timers.json

Heartbeat runs serially (Session 1 -> 2 -> ... -> 5).
All other events run in parallel via `claude --print`.
"""

import argparse
import json
import os
import subprocess
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from scheduler_utils import (
    log,
    ensure_git_hooks,
    ensure_embeddings,
    check_diary_written,
    fetch_twilog_update,
    sync_twilog_to_unified_diary,
    check_github_pages_status,
    CLAUDE_OUTPUT_LOG,
)
from message_builder import build_system_message, build_event_message, MAX_SESSIONS
from session_manager import (
    save_session_id,
    get_current_session_id,
    clear_session_id,
    get_session_id_by_tag,
)
from event_sources import TimerSource, EmailSource, DiscordSource, VoiceSource, CronSource, OneTimerSource

# =============================================================================
# Constants
# =============================================================================

SESSION_INTERVAL_SECONDS = 60 * 60   # 60 min
SESSION_TIMEOUT_MINUTES = 120        # 120 min
EMAIL_POLL_SECONDS = 30              # 30 sec
VOICE_POLL_SECONDS = 2               # 2 sec (low latency for voice)
EVENT_SESSION_TIMEOUT_MINUTES = 30   # event-driven sessions are shorter

SESSION_COMPLETE_MARKER = "__SESSION_COMPLETE__"
MARKER_GRACE_SECONDS = 10


# =============================================================================
# AyumuGateway
# =============================================================================

class AyumuGateway:
    """Event-driven gateway for Ayumu activation"""

    def __init__(self, args):
        self.args = args
        self.session_count = 0
        self.cycle_start_time = None
        self.launch_time = datetime.now()
        self.custom_message = args.message
        self.use_gemini = args.gemini
        self.claude_model = "sonnet"  # Default. Updated at session 1/5 based on API usage
        self.sources: list[threading.Thread] = []

        # --session: start from a specific session number
        if args.session:
            self.session_count = args.session - 1  # on_heartbeat does +1
            self.cycle_start_time = datetime.now()
            log(f"Starting from session {args.session}/{MAX_SESSIONS}")

        # heartbeat lock: only one heartbeat runs at a time
        self._heartbeat_lock = threading.Lock()
        self._paused = False

        # Discord session ID persistence directory
        self._discord_session_dir = Path(__file__).parent / "discord_sessions"
        self._discord_session_dir.mkdir(exist_ok=True)
        self._discord_sessions_lock = threading.Lock()

        # Voice session ID persistence
        self._voice_session_file = Path(__file__).parent / "discord_sessions" / "_voice.txt"
        self._voice_session_lock = threading.Lock()

        # Discord security: owner user ID (numeric) from env var
        # Set DISCORD_OWNER_USER_ID in .env.local to enable per-user restrictions
        owner_id_str = os.environ.get("DISCORD_OWNER_USER_ID", "")
        self._discord_owner_user_id: int | None = int(owner_id_str) if owner_id_str.strip().isdigit() else None
        if self._discord_owner_user_id:
            log(f"Discord owner ID: {self._discord_owner_user_id} (restricted mode active)")
        else:
            log("Discord owner ID: not set (no per-user restrictions)")

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    def start(self):
        """Start event sources and enter main loop"""
        log("=" * 60)
        log("Ayumu Gateway started")
        log("=" * 60)

        # Load .env.local into os.environ (so DiscordSource etc. can read tokens)
        try:
            from session_manager import load_env_local
            env_vars = load_env_local()
            for key, value in env_vars.items():
                if key not in os.environ:  # don't override existing env vars
                    os.environ[key] = value
            log(f"Loaded .env.local ({len(env_vars)} vars)")
        except Exception as e:
            log(f"Warning: Could not load .env.local: {e}")

        # Setup
        ensure_git_hooks()
        ensure_embeddings()

        log(f"Timer: {'disabled' if self.args.no_timer else f'{SESSION_INTERVAL_SECONDS}s interval'}")
        log(f"Email: {'disabled' if self.args.no_email else f'{EMAIL_POLL_SECONDS}s poll'}")
        log(f"Discord: {'enabled' if not self.args.no_discord else 'disabled'}")
        log(f"Voice: {'disabled' if self.args.no_voice else 'enabled'}")
        log(f"Cron: {'disabled' if self.args.no_cron else 'enabled'}")
        log(f"OneTimer: enabled (always on)")

        # Start event sources
        if not self.args.no_timer:
            timer = TimerSource(
                interval=SESSION_INTERVAL_SECONDS,
                callback=self.on_heartbeat,
            )
            timer.start()
            self.sources.append(timer)

        if not self.args.no_email:
            email = EmailSource(
                poll_interval=EMAIL_POLL_SECONDS,
                callback=self.on_email,
            )
            email.start()
            self.sources.append(email)

        if not self.args.no_discord:
            discord = DiscordSource(
                callback=self.on_discord,
                on_control=self._on_discord_control,
                owner_user_id=self._discord_owner_user_id,
                jb_check_func=self._check_jailbreak,
            )
            discord.start()
            self.sources.append(discord)

        if not self.args.no_voice:
            voice = VoiceSource(
                poll_interval=VOICE_POLL_SECONDS,
                callback=self.on_voice,
            )
            voice.start()
            self.sources.append(voice)

        if not self.args.no_cron:
            cron = CronSource(callback=self.on_cron)
            cron.start()
            self.sources.append(cron)

        # OneTimer is always on (no-op if timers.json is empty)
        one_timer = OneTimerSource(callback=self.on_timer)
        one_timer.start()
        self.sources.append(one_timer)

        # Initial heartbeat (immediate)
        if not self.args.no_timer:
            log("Running initial heartbeat...")
            self.on_heartbeat()

        # Keep main thread alive
        log("Gateway running. Press Ctrl+C to stop.")
        heartbeat_counter = 0
        try:
            while True:
                time.sleep(60)
                heartbeat_counter += 1
                if heartbeat_counter % 10 == 0:
                    log(f"Gateway heartbeat: alive ({heartbeat_counter} min)")
        except KeyboardInterrupt:
            log("Gateway stopped by user (KeyboardInterrupt)")

    # -----------------------------------------------------------------
    # Heartbeat (timer event) - session cycle management
    # -----------------------------------------------------------------

    def on_heartbeat(self):
        """Timer event handler - runs session cycle (serial, locked)"""
        if self._paused:
            log("Heartbeat skipped: gateway is paused (use !resume on Discord)")
            return
        if not self._heartbeat_lock.acquire(blocking=False):
            log("Heartbeat skipped: previous heartbeat still running")
            return

        try:
            self._run_heartbeat()
        finally:
            self._heartbeat_lock.release()

    def _pick_claude_model(self) -> str:
        """Pick opus/sonnet based on weekly token usage.
        Use opus if: token remaining > 30% AND token% >= time%
        (If consumption rate exceeds time rate, use sonnet to conserve)
        """
        try:
            from datetime import timezone
            credentials_file = Path.home() / ".claude" / ".credentials.json"
            token = json.loads(credentials_file.read_text())["claudeAiOauth"]["accessToken"]
            req = urllib.request.Request(
                "https://api.anthropic.com/api/oauth/usage",
                headers={"Authorization": f"Bearer {token}", "anthropic-beta": "oauth-2025-04-20"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            seven_day_rem = 100 - round(data["seven_day"]["utilization"])
            seven_reset = datetime.fromisoformat(data["seven_day"]["resets_at"])
            now = datetime.now(timezone.utc)
            remaining_sec = max(0, (seven_reset - now).total_seconds())
            time_rem = round(remaining_sec / (7 * 24 * 3600) * 100)
            model = "opus" if seven_day_rem > 30 and seven_day_rem >= time_rem else "sonnet"
            log(f"Token remaining: {seven_day_rem}%, time remaining: {time_rem}% -> model: {model}")
            return model
        except Exception as e:
            log(f"Warning: Could not fetch usage, defaulting to sonnet: {e}")
            return "sonnet"

    def _run_heartbeat(self):
        """Core heartbeat logic"""
        self.session_count += 1

        # Load machine name
        machine_name = None
        env_local_missing = False
        try:
            from session_manager import load_env_local
            env_vars = load_env_local()
            machine_name = env_vars.get("MACHINE_NAME")
            if machine_name:
                log(f"Machine: {machine_name}")
        except FileNotFoundError:
            log("Warning: .env.local not found")
            env_local_missing = True
        except Exception as e:
            log(f"Warning: Could not load machine name: {e}")

        # Cycle start
        if self.cycle_start_time is None:
            self.cycle_start_time = datetime.now()
            if self.session_count == 1:
                log(f"=== New cycle started at {self.cycle_start_time.strftime('%Y-%m-%d %H:%M:%S')} ===")
            else:
                log(f"=== Cycle started from session {self.session_count}/{MAX_SESSIONS} ===")

        log(f"=== Heartbeat: Session {self.session_count}/{MAX_SESSIONS} ===")

        # Pre-session data gathering
        twilog_result = fetch_twilog_update()
        github_pages_result = check_github_pages_status()

        is_diary_session = (self.session_count == MAX_SESSIONS - 1)
        is_maintenance_session = (self.session_count == MAX_SESSIONS)

        if is_maintenance_session:
            sync_twilog_to_unified_diary()

        # Build system message
        msg_kwargs = dict(
            twilog_result=twilog_result,
            email_result=None,
            github_pages_result=github_pages_result,
            custom_msg=self.custom_message,
            launch_time=self.launch_time,
            machine_name=machine_name,
            env_local_missing=env_local_missing,
        )

        if is_diary_session:
            message = build_system_message(self.session_count, is_diary=True, **msg_kwargs)
        elif is_maintenance_session:
            message = build_system_message(self.session_count, is_maintenance=True, **msg_kwargs)
        else:
            message = build_system_message(self.session_count, **msg_kwargs)

        log(f"System message: {message}")

        # Build command
        model_command = "gemini" if self.use_gemini else "claude"
        if not self.use_gemini and self.session_count in (1, MAX_SESSIONS):
            self.claude_model = self._pick_claude_model()
        cmd = self._build_heartbeat_command(
            model_command, message, is_maintenance_session,
        )

        # Record time before launch so we can identify the new session file afterward
        session_start_time = time.time()
        success, _ = self._run_claude_session(
            cmd, f"Session {self.session_count}/{MAX_SESSIONS}",
            capture_session_id=(self.session_count == 1 and not self.args.use_continue),
            model_command=model_command,
            session_start_time=session_start_time,
        )

        if not success:
            log("!!! Session failed. Scheduling 10-minute retry...")
            self.session_count -= 1
            self._schedule_retry(self.on_heartbeat, delay=600)
            return

        # Post-session processing
        if is_diary_session:
            self._handle_diary_check()

        if is_maintenance_session:
            self._handle_maintenance_complete()

    def _build_heartbeat_command(self, model_command, message, is_maintenance):
        """Build the command list for heartbeat session"""
        cmd_prefix = ["timeout", f"{SESSION_TIMEOUT_MINUTES}m", model_command]
        if self.use_gemini:
            cmd_prefix.append("-y")

        if model_command == "gemini":
            return cmd_prefix + ["-p", message]

        # Claude
        model_flags = ["--model", self.claude_model] if not self.use_gemini else []

        if is_maintenance:
            clear_session_id()
            cmd = cmd_prefix + ["--print", "--verbose"] + model_flags + [message]
            log(f"Session {self.session_count}/{MAX_SESSIONS} - Maintenance, fresh start (model={self.claude_model})")
            return cmd

        if self.session_count == 1 and not self.args.use_continue:
            cmd = cmd_prefix + ["--print", "--verbose"] + model_flags + [message]
            log(f"Session {self.session_count}/{MAX_SESSIONS} - New cycle (model={self.claude_model})")
            return cmd

        # Session 2-4: resume
        session_id = get_current_session_id()
        if session_id:
            cmd = cmd_prefix + ["--print", "--verbose"] + model_flags + ["--resume", session_id, message]
            log(f"Session {self.session_count}/{MAX_SESSIONS} - Resume {session_id} (model={self.claude_model})")
        else:
            log(f"WARNING: Session ID not found, creating new session")
            cmd = cmd_prefix + ["--print", "--verbose"] + model_flags + [message]

        return cmd

    # -----------------------------------------------------------------
    # Event handlers (parallel)
    # -----------------------------------------------------------------

    def on_email(self, email_data: dict):
        """Email event handler - write body to tmp file, run claude --print in a new thread"""
        log(f"Email event: {email_data.get('from', '?')} - {email_data.get('subject', '')}")

        # Write long bodies to a tmp file
        body = email_data.get("body", "").strip()
        if body and len(body) > 500:
            import tempfile
            fd, body_file = tempfile.mkstemp(prefix="ayumu_email_", suffix=".txt", dir="/tmp")
            with os.fdopen(fd, "w") as f:
                f.write(body)
            log(f"Email body written to {body_file} ({len(body)} chars)")
            email_data = {**email_data, "body": "", "body_file": body_file}

        threading.Thread(
            target=self._run_claude_for_event,
            args=("email", email_data),
            daemon=True,
        ).start()

    def _check_jailbreak(self, text: str) -> tuple[bool, str]:
        """Jailbreak check wrapper (uses gateway/jb_checker.py if available)"""
        try:
            import sys
            gateway_dir = str(Path(__file__).parent)
            if gateway_dir not in sys.path:
                sys.path.insert(0, gateway_dir)
            from jb_checker import check_jailbreak
            return check_jailbreak(text)
        except ImportError:
            return False, "jb_checker not available"
        except Exception as e:
            return False, f"JB check error: {e}"

    def _on_discord_control(self, command: str) -> str:
        """Handle Discord control commands (!pause, !resume, !stop)"""
        if command == "!pause":
            self._paused = True
            log("Gateway PAUSED via Discord")
            return "Heartbeat paused. Use `!resume` to resume."

        if command == "!resume":
            self._paused = False
            log("Gateway RESUMED via Discord")
            return "Heartbeat resumed."

        if command == "!stop":
            log("EMERGENCY STOP via Discord")
            # Kill all claude processes
            try:
                result = subprocess.run(
                    ["pkill", "-f", "claude"],
                    capture_output=True, text=True,
                )
                killed = result.returncode == 0
                log(f"pkill claude: {'killed' if killed else 'no processes found'}")
            except Exception as e:
                log(f"pkill error: {e}")
            # Return message, then exit gateway
            threading.Timer(1.0, lambda: os._exit(0)).start()
            return "All claude processes killed. Gateway shutting down."

        return f"Unknown command: {command}"

    def on_discord(self, message_data: dict):
        """Discord event handler - runs claude --print in a new thread"""
        author = message_data.get("author", "?")
        author_id = message_data.get("author_id")
        channel = message_data.get("channel", "?")
        content = message_data.get("content", "")
        log(f"Discord event: {author} ({author_id}) in #{channel}")

        threading.Thread(
            target=self._run_claude_for_event,
            args=("discord", message_data),
            daemon=True,
        ).start()

    _voice_lock_file = Path("/tmp/ayumu_voice_session.lock")

    def on_voice(self, voice_data: dict):
        """Voice event handler - runs claude --print in a new thread.

        Prevents multiple sessions: ignores new voice events while a
        voice session is active (lock file exists).
        """
        if self._voice_lock_file.exists():
            log(f"Voice event IGNORED (session already active): {voice_data.get('command', '?')}")
            return
        log(f"Voice event: {voice_data.get('command', '?')}")
        threading.Thread(
            target=self._run_voice_session,
            args=(voice_data,),
            daemon=True,
        ).start()

    def _run_voice_session(self, voice_data: dict):
        """Voice session wrapper with lock file management."""
        try:
            self._voice_lock_file.write_text(str(os.getpid()))
            self._run_claude_for_event("voice", voice_data)
        finally:
            self._voice_lock_file.unlink(missing_ok=True)

    def on_cron(self, cron_data: dict):
        """Cron event handler - runs claude --print in a new thread"""
        log(f"Cron event: {cron_data.get('name', '?')}")
        threading.Thread(
            target=self._run_claude_for_event,
            args=("cron", cron_data),
            daemon=True,
        ).start()

    def on_timer(self, timer_data: dict):
        """OneTimer event handler - runs claude --print in a new thread"""
        log(f"Timer event: {timer_data.get('id', '?')}")
        threading.Thread(
            target=self._run_claude_for_event,
            args=("timer", timer_data),
            daemon=True,
        ).start()

    @staticmethod
    def _pick_discord_model(content: str) -> str | None:
        """Pick model from --haiku / --sonnet / --opus flags in Discord message. Default: haiku."""
        lower = content.lower()
        if "--opus" in lower:
            return "opus"
        if "--sonnet" in lower:
            return "sonnet"
        if "--haiku" in lower:
            return "haiku"
        return "haiku"

    def _get_discord_session_id(self, channel: str) -> str | None:
        """Read saved session ID for a Discord channel"""
        f = self._discord_session_dir / f"{channel}.txt"
        if f.exists():
            sid = f.read_text().strip()
            return sid if sid else None
        return None

    def _save_discord_session_id(self, channel: str, session_id: str):
        """Save session ID for a Discord channel"""
        f = self._discord_session_dir / f"{channel}.txt"
        f.write_text(session_id)

    def _get_voice_session_id(self) -> str | None:
        """Read saved session ID for voice conversations"""
        if self._voice_session_file.exists():
            sid = self._voice_session_file.read_text().strip()
            return sid if sid else None
        return None

    def _save_voice_session_id(self, session_id: str):
        """Save session ID for voice conversations"""
        self._voice_session_file.write_text(session_id)

    def _run_claude_for_event(self, event_type: str, data: dict):
        """Run claude --print for a non-heartbeat event (parallel OK)"""
        message = build_event_message(event_type, data)
        cmd = [
            "timeout", f"{EVENT_SESSION_TIMEOUT_MINUTES}m",
            "claude", "--print", "--verbose",
        ]

        # Discord: model selection + session resume + access control
        if event_type == "discord":
            model = self._pick_discord_model(data.get("content", ""))
            cmd.extend(["--model", model])
            log(f"Discord model: {model}")

            # Resume previous session for this channel if available
            channel = data.get("channel", "")
            with self._discord_sessions_lock:
                session_id = self._get_discord_session_id(channel)
            if session_id:
                cmd.extend(["--resume", session_id])
                log(f"Discord resuming session: {session_id[:12]}...")

            # Non-owner users get read-only tool access (no Bash or write)
            author_id = data.get("author_id")
            if self._discord_owner_user_id and author_id and author_id != self._discord_owner_user_id:
                read_only_tools = "Read,Glob,Grep,WebSearch,WebFetch"
                cmd.extend(["--allowedTools", read_only_tools])
                log(f"Discord: read-only mode for external user {author_id}")

        # Voice: sonnet for MCP tool use + session resume
        if event_type == "voice":
            cmd.extend(["--model", "sonnet"])
            with self._voice_session_lock:
                session_id = self._get_voice_session_id()
            if session_id:
                cmd.extend(["--resume", session_id])
                log(f"Voice resuming session: {session_id[:12]}...")

        # Record start time for session ID capture (tag-based detection)
        start_time = time.time()

        cmd.append(message)
        label = f"Event:{event_type}"
        log(f"Starting {label} session...")
        self._run_claude_session(cmd, label)

        # Store new session ID for Discord channel
        if event_type == "discord":
            channel = data.get("channel", "")
            try:
                time.sleep(3)
                session_id = get_session_id_by_tag(f"discord:{channel}", start_time)
                if session_id:
                    with self._discord_sessions_lock:
                        self._save_discord_session_id(channel, session_id)
                    log(f"Discord session saved for #{channel}: {session_id[:12]}...")
                else:
                    log(f"ERROR: Discord session ID not found (tag not found)")
            except Exception as e:
                log(f"Failed to capture Discord session ID: {e}")

        # Store new session ID for voice conversations
        if event_type == "voice":
            try:
                time.sleep(3)
                session_id = get_session_id_by_tag("voice", start_time)
                if session_id:
                    with self._voice_session_lock:
                        self._save_voice_session_id(session_id)
                    log(f"Voice session saved: {session_id[:12]}...")
                else:
                    log(f"ERROR: Voice session ID not found (tag not found)")
            except Exception as e:
                log(f"Failed to capture Voice session ID: {e}")

        log(f"{label} session finished")

    def _send_discord_reply(self, channel: str, stdout: str):
        """
        Extract response from stdout and send to Discord.
        Removes header/footer markers and extracts actual response.
        """
        try:
            lines = stdout.split("\n")

            start_idx = -1
            end_idx = len(lines)

            for i, line in enumerate(lines):
                if ">>> Ayumu's output" in line:
                    start_idx = i
                if "__SESSION_COMPLETE__" in line:
                    end_idx = i
                    break

            if start_idx >= 0:
                response_lines = lines[start_idx + 1:end_idx]
                response_lines = [l for l in response_lines if not l.startswith("===")]
                response = "\n".join(response_lines).strip()

                if response:
                    cmd = [
                        "uv", "run", "tools/send_discord.py",
                        response,
                        "--channel", channel,
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        log(f"Discord reply sent to #{channel}")
                    else:
                        log(f"Failed to send Discord reply: {result.stderr}")
                else:
                    log(f"No response content to send to Discord")
        except Exception as e:
            log(f"Error sending Discord reply: {type(e).__name__}: {e}")

    # -----------------------------------------------------------------
    # Shared execution logic
    # -----------------------------------------------------------------

    def _run_claude_session(
        self, cmd: list[str], label: str,
        capture_session_id: bool = False,
        model_command: str = "claude",
        session_start_time: float | None = None,
    ) -> bool:
        """
        Execute a claude/gemini session with marker detection.

        Returns True on success, False on failure.
        """
        log(f"Executing: {' '.join(cmd[:6])}... ({label})")
        print(f"\n{'=' * 60}")
        print(f">>> Ayumu's output ({label}):")
        print(f"{'=' * 60}\n")

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout_lines = []
        marker_detected = False
        returncode = None

        try:
            for line in process.stdout:
                line_stripped = line.rstrip("\n")
                stdout_lines.append(line_stripped)
                print(line_stripped)

                if SESSION_COMPLETE_MARKER in line_stripped:
                    marker_detected = True
                    log(f"Session complete marker detected! Waiting {MARKER_GRACE_SECONDS}s...")
                    time.sleep(MARKER_GRACE_SECONDS)
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        log("Process did not terminate gracefully, killing...")
                        process.kill()
                        process.wait()
                    break

            if not marker_detected:
                process.wait()

            returncode = process.returncode
        except Exception as e:
            log(f"Error reading process output: {e}")
            process.kill()
            process.wait()
            returncode = process.returncode

        # Read stderr
        stderr_output = ""
        try:
            stderr_output = process.stderr.read() if process.stderr else ""
        except Exception:
            pass

        stdout_output = "\n".join(stdout_lines)

        # Capture session ID after Session 1
        if capture_session_id and model_command == "claude" and session_start_time is not None:
            try:
                log("Waiting 3s for session file creation...")
                time.sleep(3)
                new_id = get_session_id_by_tag("heartbeat", session_start_time)
                if new_id:
                    save_session_id(new_id)
                    log(f"Captured session ID: {new_id}")
                else:
                    log("ERROR: Failed to capture session ID (tag not found)")
            except Exception as e:
                log(f"ERROR capturing session ID: {e}")

        if stderr_output:
            print(stderr_output)

        # Write log
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(CLAUDE_OUTPUT_LOG, "a") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"[{timestamp}] {label}\n")
            f.write(f"Command: {' '.join(cmd[:5])}...\n")
            if marker_detected:
                f.write("Terminated by SESSION_COMPLETE marker\n")
            f.write(f"{'=' * 60}\n")
            if stdout_output:
                f.write(f"STDOUT:\n{stdout_output}\n")
            if stderr_output:
                f.write(f"STDERR:\n{stderr_output}\n")
            f.write(f"Return code: {returncode}\n")

        print(f"\n{'=' * 60}")

        # Determine success/failure
        if marker_detected:
            log(f"{label} completed (marker detected)")
            return True, stdout_output
        elif returncode == 0:
            log(f"{label} completed successfully")
            return True, stdout_output
        elif returncode == 124:
            log(f"!!! {label}: {SESSION_TIMEOUT_MINUTES}m timeout")
            return True, stdout_output  # timeout is not a failure for retry purposes
        elif returncode is not None and returncode < 0 and marker_detected:
            log(f"{label} completed (marker + signal {-returncode})")
            return True, stdout_output
        else:
            log(f"{label} failed with return code {returncode}")
            return False, stdout_output

    # -----------------------------------------------------------------
    # Post-session helpers
    # -----------------------------------------------------------------

    def _handle_diary_check(self):
        """Check if diary was written after diary session (Session 4)"""
        log("=== Checking diary... ===")
        time.sleep(5)

        if check_diary_written(self.cycle_start_time):
            log("Diary was written.")
        else:
            log("!!! Diary NOT written. Starting extra session...")
            self._run_extra_session()
            time.sleep(5)
            if check_diary_written(self.cycle_start_time):
                log("Diary written in extra session.")
            else:
                log("Diary still not written. Proceeding anyway.")

    def _run_extra_session(self):
        """Run diary reminder extra session"""
        log("=== Extra session (diary reminder) ===")

        github_pages_result = check_github_pages_status()

        message = build_system_message(
            None,
            is_reminder=True,
            email_result=None,
            github_pages_result=github_pages_result,
            custom_msg=self.custom_message,
            launch_time=self.launch_time,
        )

        model_command = "gemini" if self.use_gemini else "claude"
        cmd_prefix = ["timeout", f"{SESSION_TIMEOUT_MINUTES}m", model_command]
        if self.use_gemini:
            cmd_prefix.append("-y")

        if model_command == "gemini":
            cmd = cmd_prefix + ["-p", message]
        else:
            cmd = cmd_prefix + ["--print", "--continue", "--verbose", message]

        _, _ = self._run_claude_session(cmd, "Extra (Diary Reminder)")
        log("=== Extra session ended ===")

    def _handle_maintenance_complete(self):
        """Post-maintenance processing"""
        log("=== Maintenance complete ===")

        # Reset cycle
        self.session_count = 0
        self.cycle_start_time = None
        log("=== Cycle ended ===")

    def _schedule_retry(self, callback, delay: int):
        """Schedule a one-shot retry after delay seconds"""
        def _retry():
            time.sleep(delay)
            log(f"Retry timer fired ({delay}s)")
            callback()

        threading.Thread(target=_retry, daemon=True).start()


# =============================================================================
# CLI
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Ayumu Gateway - Event-driven scheduler",
    )
    parser.add_argument(
        "-m", "--message", type=str,
        help="Custom message to send to Ayumu",
    )
    parser.add_argument(
        "--continue", action="store_true", dest="use_continue",
        help="Use --continue from the first session",
    )
    parser.add_argument(
        "--session", type=int, choices=range(1, MAX_SESSIONS + 1), metavar="N",
        help=f"Start from session N (1-{MAX_SESSIONS})",
    )
    parser.add_argument(
        "--gemini", action="store_true",
        help="Use gemini model instead of claude",
    )
    parser.add_argument(
        "--no-timer", action="store_true",
        help="Disable timer-based heartbeat (event-only mode)",
    )
    parser.add_argument(
        "--no-email", action="store_true",
        help="Disable email polling",
    )
    parser.add_argument(
        "--no-discord", action="store_true",
        help="Disable Discord bot integration",
    )
    parser.add_argument(
        "--no-voice", action="store_true",
        help="Disable voice wake word detection",
    )
    parser.add_argument(
        "--no-cron", action="store_true",
        help="Disable cron-based scheduling",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.message:
        log(f"Custom message: {args.message}")
    if args.use_continue:
        log("--continue enabled")
    if args.gemini:
        log("--gemini enabled")

    gateway = AyumuGateway(args)
    gateway.start()
