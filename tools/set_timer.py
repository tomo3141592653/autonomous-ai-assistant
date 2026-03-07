#!/usr/bin/env python3
"""
Set Timer - Ayumuが自分でタイマーを設定するCLIツール

Usage:
    uv run tools/set_timer.py --at "2026-02-27T18:00:00" -m "メッセージ"
    uv run tools/set_timer.py --after 60 -m "60分後のリマインダー"
    uv run tools/set_timer.py --list
    uv run tools/set_timer.py --clear
"""

import argparse
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

_TIMERS_FILE = Path(__file__).resolve().parent.parent / "gateway" / "timers.json"


def _load_timers() -> list[dict]:
    if not _TIMERS_FILE.exists():
        return []
    try:
        data = json.loads(_TIMERS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_timers(timers: list[dict]):
    _TIMERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TIMERS_FILE.write_text(
        json.dumps(timers, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_timer(fire_at: str, message: str):
    timers = _load_timers()
    timer_id = uuid.uuid4().hex[:8]
    entry = {
        "id": timer_id,
        "message": message,
        "fire_at": fire_at,
        "created_at": datetime.now().isoformat(),
        "fired": False,
    }
    timers.append(entry)
    _save_timers(timers)
    print(f"Timer set: {timer_id} → {fire_at}")
    print(f"Message: {message}")


def list_timers():
    timers = _load_timers()
    if not timers:
        print("No timers.")
        return

    now = datetime.now()
    for t in timers:
        status = "FIRED" if t.get("fired") else "pending"
        fire_at = t.get("fire_at", "?")
        try:
            dt = datetime.fromisoformat(fire_at)
            remaining = dt - now
            if remaining.total_seconds() > 0 and not t.get("fired"):
                mins = int(remaining.total_seconds() / 60)
                status = f"in {mins}m"
        except ValueError:
            pass
        print(f"  [{status}] {t.get('id', '?')} @ {fire_at}: {t.get('message', '')}")


def clear_fired():
    timers = _load_timers()
    before = len(timers)
    timers = [t for t in timers if not t.get("fired")]
    _save_timers(timers)
    removed = before - len(timers)
    print(f"Cleared {removed} fired timer(s). {len(timers)} remaining.")


def main():
    parser = argparse.ArgumentParser(description="Set a one-shot timer for Ayumu")
    parser.add_argument("--at", type=str, help="Fire at ISO datetime (e.g. 2026-02-27T18:00:00)")
    parser.add_argument("--after", type=int, help="Fire after N minutes")
    parser.add_argument("-m", "--message", type=str, default="", help="Timer message")
    parser.add_argument("--list", action="store_true", help="List all timers")
    parser.add_argument("--clear", action="store_true", help="Clear fired timers")
    args = parser.parse_args()

    if args.list:
        list_timers()
        return

    if args.clear:
        clear_fired()
        return

    if args.at:
        # Validate ISO format
        try:
            datetime.fromisoformat(args.at)
        except ValueError:
            print(f"Error: invalid datetime format: {args.at}")
            return
        add_timer(args.at, args.message)
    elif args.after is not None:
        fire_at = (datetime.now() + timedelta(minutes=args.after)).isoformat()
        add_timer(fire_at, args.message)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
