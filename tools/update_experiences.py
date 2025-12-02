#!/usr/bin/env python3
"""
Add experience log entry

Usage:
    python tools/update_experiences.py --type communication --description "Received message" --metadata '{"key": "value"}'
    python tools/update_experiences.py --type learning --description "Learned new concept"
"""

import json
import argparse
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "memory"
EXPERIENCES_FILE = MEMORY_DIR / "experiences.jsonl"


def add_experience(type: str, description: str, metadata: dict = None):
    """Add experience log (append-only)"""
    timestamp = datetime.now().isoformat()

    entry = {
        "timestamp": timestamp,
        "type": type,
        "description": description,
        "metadata": metadata or {}
    }

    # Append in JSONL format
    EXPERIENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EXPERIENCES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"✅ Added experience log: {type} - {description}")
    print(f"   Saved to: {EXPERIENCES_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Add experience log entry")
    parser.add_argument("--type", required=True, help="Type (e.g., communication, learning, exploration, creation)")
    parser.add_argument("--description", required=True, help="Description")
    parser.add_argument("--metadata", help="Metadata (JSON string)", default="{}")

    args = parser.parse_args()

    try:
        metadata = json.loads(args.metadata) if args.metadata else {}
    except json.JSONDecodeError:
        print("❌ Error: Metadata is not valid JSON")
        return

    add_experience(args.type, args.description, metadata)


if __name__ == "__main__":
    main()
