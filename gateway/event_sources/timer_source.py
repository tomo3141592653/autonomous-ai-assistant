#!/usr/bin/env python3
"""
Timer Source - Periodic callback event source

Used for heartbeat (session cycle) scheduling. The first callback is fired
by the caller immediately, so this thread waits `interval` seconds before
the first callback.
"""

import threading
import time

from scheduler_utils import log


class TimerSource(threading.Thread):
    """Daemon thread that calls a callback at regular intervals"""

    def __init__(self, interval: int, callback):
        """
        Args:
            interval: Callback interval in seconds
            callback: No-argument callback function
        """
        super().__init__(daemon=True)
        self.interval = interval
        self.callback = callback
        self._stop_event = threading.Event()

    def run(self):
        log(f"TimerSource started (interval={self.interval}s)")
        while not self._stop_event.is_set():
            if self._stop_event.wait(timeout=self.interval):
                break
            try:
                self.callback()
            except Exception as e:
                log(f"TimerSource callback error: {type(e).__name__}: {e}")

    def stop(self):
        """Stop the timer"""
        self._stop_event.set()
