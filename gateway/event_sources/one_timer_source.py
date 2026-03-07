#!/usr/bin/env python3
"""
One Timer Source - One-shot timer event source

Polls gateway/timers.json and fires callbacks for entries whose fire_at
time has passed. After firing, marks the entry as fired: true.
"""

import json
import threading
from datetime import datetime
from pathlib import Path

from scheduler_utils import log

_TIMERS_FILE = Path(__file__).resolve().parent.parent / "timers.json"
_POLL_INTERVAL = 5  # seconds


class OneTimerSource(threading.Thread):
    """Daemon thread that fires one-shot timer callbacks"""

    def __init__(self, callback):
        """
        Args:
            callback: callback(data) -- data is {id, message, fire_at}
        """
        super().__init__(daemon=True)
        self.callback = callback
        self._stop_event = threading.Event()

    def _load_timers(self) -> list[dict]:
        if not _TIMERS_FILE.exists():
            return []
        try:
            data = json.loads(_TIMERS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception as e:
            log(f"OneTimerSource: failed to load {_TIMERS_FILE}: {e}")
            return []

    def _save_timers(self, timers: list[dict]):
        try:
            _TIMERS_FILE.write_text(
                json.dumps(timers, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log(f"OneTimerSource: failed to save {_TIMERS_FILE}: {e}")

    def run(self):
        log("OneTimerSource started")

        while not self._stop_event.is_set():
            if self._stop_event.wait(timeout=_POLL_INTERVAL):
                break

            timers = self._load_timers()
            if not timers:
                continue

            now = datetime.now()
            modified = False

            for entry in timers:
                if entry.get("fired"):
                    continue

                fire_at_str = entry.get("fire_at", "")
                if not fire_at_str:
                    continue

                try:
                    fire_at = datetime.fromisoformat(fire_at_str)
                except ValueError:
                    log(f"OneTimerSource: invalid fire_at '{fire_at_str}'")
                    continue

                if now >= fire_at:
                    timer_id = entry.get("id", "unknown")
                    message = entry.get("message", "")
                    log(f"OneTimerSource: firing timer '{timer_id}' (fire_at={fire_at_str})")

                    entry["fired"] = True
                    modified = True

                    try:
                        self.callback({
                            "id": timer_id,
                            "message": message,
                            "fire_at": fire_at_str,
                        })
                    except Exception as e:
                        log(f"OneTimerSource callback error: {type(e).__name__}: {e}")

            if modified:
                self._save_timers(timers)

    def stop(self):
        self._stop_event.set()
