#!/usr/bin/env python3
"""
Voice Source - Monitors a hearing log file for wake word detection

Two detection methods run in parallel:
  1. OpenWakeWord -- Detects "Hey Jarvis" at the audio level (fast, accurate)
     The listen tool's OpenWakeWord thread writes a marker line to latest.txt
     when detected.
  2. Whisper STT + text matching -- Detects a configurable wake phrase via
     text matching (legacy, less reliable).

Extracts the text following the wake word as a command.
Example: "[14:30:05] Hey Ayumu, what time is it?" -> command="what time is it?"
"""

import re
import threading
import time
from datetime import datetime
from pathlib import Path

from scheduler_utils import log

# Path to the hearing log file (written by the listen tool)
# Override via AYUMU_HEARING_FILE environment variable
import os
HEARING_LATEST = Path(os.environ.get(
    "AYUMU_HEARING_FILE",
    str(Path(__file__).resolve().parent.parent.parent / "memory" / "hearing" / "latest.txt")
))

DEFAULT_POLL_INTERVAL = 2  # seconds

# Cooldown after wake word detection (seconds).
# Prevents infinite loops when Ayumu's own speech is transcribed.
COOLDOWN_SECONDS = 30

# Lock file to prevent multiple voice sessions from running simultaneously.
# Written by the gateway, deleted when the session ends.
VOICE_SESSION_LOCK = Path("/tmp/ayumu_voice_session.lock")

# OpenWakeWord marker (written by the listen tool's OWW thread)
OWW_MARKER = "\U0001f3af"  # target emoji

# Legacy: Whisper STT + text matching wake word detection
# Customize WAKE_PATTERNS for your own wake phrase.
WAKE_PATTERNS = re.compile(
    r"(?:ok|okay|hey)[,.\s]*(?:ayumu|assistant)",
    re.IGNORECASE,
)


def _extract_command(text: str) -> str | None:
    """Detect wake word in text and return the command portion that follows.

    Returns None if no wake word is found.
    Returns empty string if wake word is found but no command follows.
    """
    m = WAKE_PATTERNS.search(text)
    if m is None:
        return None
    after = text[m.end():]
    after = after.lstrip(",. ")
    return after


def _parse_hearing_line(line: str) -> tuple[str, str]:
    """Parse a hearing log line.

    "[HH:MM:SS] text" -> (timestamp, text)
    Returns ("", line) if parsing fails.
    """
    line = line.strip()
    if line.startswith("[") and "] " in line:
        bracket_end = line.index("] ")
        ts = line[1:bracket_end]
        text = line[bracket_end + 2:]
        return ts, text
    return "", line


class VoiceSource(threading.Thread):
    """Daemon thread that monitors hearing/latest.txt for wake word detection"""

    def __init__(self, poll_interval: int = DEFAULT_POLL_INTERVAL, callback=None):
        """
        Args:
            poll_interval: Polling interval in seconds
            callback: Callback function that receives a voice command data dict
                      dict keys: command, timestamp
        """
        super().__init__(daemon=True)
        self.poll_interval = poll_interval
        self.callback = callback
        self._stop_event = threading.Event()
        self._file_pos = 0  # file read position
        self._last_trigger_time = 0.0  # last wake word trigger time

    def _init_position(self):
        """Seek to end of file on startup to skip existing text"""
        if HEARING_LATEST.exists():
            self._file_pos = HEARING_LATEST.stat().st_size
        else:
            self._file_pos = 0

    def _read_new_lines(self) -> list[str]:
        """Read new lines since last position"""
        if not HEARING_LATEST.exists():
            return []
        try:
            size = HEARING_LATEST.stat().st_size
            if size < self._file_pos:
                # File was reset (e.g., listen tool restarted)
                self._file_pos = 0
            if size <= self._file_pos:
                return []
            with open(HEARING_LATEST, "r", encoding="utf-8") as f:
                f.seek(self._file_pos)
                new_text = f.read()
                self._file_pos = f.tell()
            return [l for l in new_text.splitlines() if l.strip()]
        except Exception:
            return []

    def run(self):
        self._init_position()
        log(f"VoiceSource started (poll={self.poll_interval}s, file={HEARING_LATEST})")

        while not self._stop_event.is_set():
            try:
                new_lines = self._read_new_lines()
                for line in new_lines:
                    # Skip the AI's own speech (prevent infinite loop)
                    if "\U0001f916" in line:  # robot emoji
                        continue
                    ts, text = _parse_hearing_line(line)

                    # --- Multiple session prevention ---
                    if VOICE_SESSION_LOCK.exists():
                        continue

                    # --- OpenWakeWord detection (marker) ---
                    if OWW_MARKER in text:
                        now = time.time()
                        if now - self._last_trigger_time < COOLDOWN_SECONDS:
                            log(f"VoiceSource: OWW wake word ignored (cooldown, {COOLDOWN_SECONDS - (now - self._last_trigger_time):.0f}s left)")
                            continue
                        self._last_trigger_time = now
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        log("VoiceSource: OpenWakeWord detected!")
                        try:
                            self.callback({"command": "(Hey Jarvis)", "timestamp": timestamp})
                        except Exception as e:
                            log(f"VoiceSource callback error: {type(e).__name__}: {e}")
                        continue

                    # --- Legacy: Whisper STT + text matching ---
                    command = _extract_command(text)
                    if command is not None:
                        now = time.time()
                        if now - self._last_trigger_time < COOLDOWN_SECONDS:
                            log(f"VoiceSource: wake word ignored (cooldown, {COOLDOWN_SECONDS - (now - self._last_trigger_time):.0f}s left)")
                            continue
                        self._last_trigger_time = now
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if not command:
                            command = "(wake word only)"
                        log(f"VoiceSource: wake word detected! command='{command}'")
                        try:
                            self.callback({"command": command, "timestamp": timestamp})
                        except Exception as e:
                            log(f"VoiceSource callback error: {type(e).__name__}: {e}")
            except Exception as e:
                log(f"VoiceSource poll error: {type(e).__name__}: {e}")

            if self._stop_event.wait(timeout=self.poll_interval):
                break

    def stop(self):
        """Stop polling"""
        self._stop_event.set()
