#!/usr/bin/env python3
"""
Cron Source - Event source that fires callbacks based on cron schedules

Reads schedules from gateway/cron.json and checks every 30 seconds.
Fires the callback when a schedule's time arrives.
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path

from croniter import croniter

from scheduler_utils import log

_CRON_FILE = Path(__file__).resolve().parent.parent / "cron.json"
_CHECK_INTERVAL = 30  # seconds


class CronSource(threading.Thread):
    """Daemon thread that fires callbacks based on cron schedules"""

    def __init__(self, callback):
        """
        Args:
            callback: callback(data) -- data is {name, cron, message, scheduled_time}
        """
        super().__init__(daemon=True)
        self.callback = callback
        self._stop_event = threading.Event()

    def _load_schedules(self) -> list[dict]:
        """Load schedules from cron.json"""
        if not _CRON_FILE.exists():
            return []
        try:
            data = json.loads(_CRON_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception as e:
            log(f"CronSource: failed to load {_CRON_FILE}: {e}")
            return []

    def run(self):
        log("CronSource started")
        schedules = self._load_schedules()
        if not schedules:
            log("CronSource: no schedules found, idling")

        # Track last fire time per schedule to avoid double-firing
        last_fired: dict[str, datetime] = {}

        while not self._stop_event.is_set():
            if self._stop_event.wait(timeout=_CHECK_INTERVAL):
                break

            # Reload schedules each check (allows hot-reload)
            schedules = self._load_schedules()
            now = datetime.now()

            for entry in schedules:
                name = entry.get("name", "unnamed")
                cron_expr = entry.get("cron", "")
                message = entry.get("message", "")

                if not cron_expr:
                    continue

                try:
                    cron = croniter(cron_expr, now)
                    prev_fire = cron.get_prev(datetime)

                    # Fire if prev_fire is within the last CHECK_INTERVAL and we haven't fired it yet
                    elapsed = (now - prev_fire).total_seconds()
                    if elapsed <= _CHECK_INTERVAL:
                        last_key = f"{name}:{prev_fire.isoformat()}"
                        if last_key not in last_fired:
                            last_fired[last_key] = now
                            log(f"CronSource: firing '{name}' (scheduled {prev_fire})")
                            try:
                                self.callback({
                                    "name": name,
                                    "cron": cron_expr,
                                    "message": message,
                                    "scheduled_time": prev_fire.isoformat(),
                                })
                            except Exception as e:
                                log(f"CronSource callback error: {type(e).__name__}: {e}")
                except Exception as e:
                    log(f"CronSource: invalid cron '{cron_expr}' for '{name}': {e}")

            # Clean up old entries (older than 1 hour)
            cutoff = datetime.now()
            last_fired = {
                k: v for k, v in last_fired.items()
                if (cutoff - v).total_seconds() < 3600
            }

    def stop(self):
        self._stop_event.set()
