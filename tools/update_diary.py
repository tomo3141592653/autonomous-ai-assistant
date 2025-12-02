#!/usr/bin/env python3
"""
Add diary entry

Usage:
    # Short content
    python tools/update_diary.py --title "Title" --content "Content"

    # Long content or special characters (from stdin)
    echo "Long content..." | python tools/update_diary.py --title "Title" --stdin

    # From file
    python tools/update_diary.py --title "Title" --file content.txt

datetime and time_period are auto-generated from current time.
"""

import json
import argparse
import sys
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "memory"
DIARY_FILE = MEMORY_DIR / "diary.json"


def get_datetime_for_sort(entry):
    """Get datetime from entry for sorting"""
    if "datetime" in entry:
        return datetime.strptime(entry["datetime"], "%Y-%m-%d %H:%M:%S")
    else:
        date_str = entry.get("date", "1970-01-01")
        return datetime.strptime(date_str, "%Y-%m-%d")


def get_time_period_from_datetime(dt: datetime) -> str:
    """Generate time_period from datetime"""
    hour = dt.hour
    if 0 <= hour < 6:
        return "night"
    elif 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    else:
        return "evening"


def add_diary_entry(title: str, content: str):
    """Add diary entry"""
    # Load existing diary
    if DIARY_FILE.exists():
        with open(DIARY_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
    else:
        entries = []

    # Generate datetime
    now = datetime.now()
    datetime_str = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")
    time_period = get_time_period_from_datetime(now)

    # Create new entry
    new_entry = {
        "date": date_str,
        "datetime": datetime_str,
        "time_period": time_period,
        "title": title,
        "content": content
    }

    # Append
    entries.append(new_entry)

    # Sort by datetime (oldest first)
    entries.sort(key=get_datetime_for_sort)

    # Save
    DIARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DIARY_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"✅ Added diary entry: {datetime_str} - {title}")
    print(f"   Saved to: {DIARY_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Add diary entry")
    parser.add_argument("--title", required=True, help="Title")

    content_group = parser.add_mutually_exclusive_group(required=True)
    content_group.add_argument("--content", help="Content (Markdown OK)")
    content_group.add_argument("--stdin", action="store_true", help="Read content from stdin")
    content_group.add_argument("--file", help="Read content from file")

    args = parser.parse_args()

    if args.content:
        content = args.content
    elif args.stdin:
        content = sys.stdin.read()
    elif args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read()

    add_diary_entry(args.title, content)


if __name__ == "__main__":
    main()
