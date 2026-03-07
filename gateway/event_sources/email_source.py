#!/usr/bin/env python3
"""
Email Source - Polls for new emails and fires callbacks on new messages

Periodically checks for unread emails using a configurable email receiver tool,
and fires a callback for each new email. Uses message IDs to prevent duplicate
notifications.
"""

import json
import subprocess
import threading
from pathlib import Path

from scheduler_utils import log


class EmailSource(threading.Thread):
    """Email polling daemon thread"""

    def __init__(self, poll_interval: int, callback):
        """
        Args:
            poll_interval: Polling interval in seconds
            callback: Callback function that receives an email data dict
                      dict keys: id, from, subject, body, date
        """
        super().__init__(daemon=True)
        self.poll_interval = poll_interval
        self.callback = callback
        self.seen_ids: set[str] = set()
        self._stop_event = threading.Event()
        self._consecutive_failures = 0

    def _fetch_unread(self) -> list[dict] | None:
        """Fetch unread emails using the receive_email tool"""
        try:
            result = subprocess.run(
                [
                    "uv", "run",
                    "--with", "google-auth-oauthlib",
                    "--with", "google-auth-httplib2",
                    "--with", "google-api-python-client",
                    "tools/receive_email.py",
                    "--unread", "--limit", "5", "--json",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=Path(__file__).parent.parent.parent,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
            return None
        except Exception:
            return None

    def run(self):
        log(f"EmailSource started (poll_interval={self.poll_interval}s)")
        while not self._stop_event.is_set():
            try:
                emails = self._fetch_unread()
                if emails is None:
                    self._consecutive_failures += 1
                    if self._consecutive_failures == 1:
                        log("EmailSource: mail check failed (will suppress repeated errors)")
                else:
                    if self._consecutive_failures > 0:
                        log(f"EmailSource: mail check recovered (after {self._consecutive_failures} failures)")
                    self._consecutive_failures = 0
                    for email in emails:
                        msg_id = email.get("id", "")
                        if msg_id and msg_id not in self.seen_ids:
                            self.seen_ids.add(msg_id)
                            log(f"EmailSource: new email [{msg_id}] from {email.get('from', '?')} - {email.get('subject', '(no subject)')}")
                            try:
                                self.callback(email)
                            except Exception as e:
                                log(f"EmailSource callback error: {type(e).__name__}: {e}")
            except Exception as e:
                self._consecutive_failures += 1
                if self._consecutive_failures == 1:
                    log(f"EmailSource poll error: {type(e).__name__}: {e} (will suppress repeated errors)")

            if self._stop_event.wait(timeout=self.poll_interval):
                break

    def stop(self):
        """Stop polling"""
        self._stop_event.set()
