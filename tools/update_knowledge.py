#!/usr/bin/env python3
"""
Update knowledge base

Usage:
    # Add fact
    python tools/update_knowledge.py --add-fact "New fact"

    # Remove fact (partial match)
    python tools/update_knowledge.py --remove-fact "Fact to remove"

    # List knowledge base
    python tools/update_knowledge.py --list
"""

import json
import argparse
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "memory"
KNOWLEDGE_FILE = MEMORY_DIR / "knowledge.json"


def add_fact(fact: str):
    """Add fact"""
    # Load existing knowledge
    if KNOWLEDGE_FILE.exists():
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            knowledge = json.load(f)
    else:
        knowledge = {"facts": []}

    # Check duplicate
    if fact in knowledge.get("facts", []):
        print(f"⚠️  Fact already exists: {fact}")
        return

    # Add
    knowledge.setdefault("facts", []).append(fact)

    # Save
    KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        json.dump(knowledge, f, ensure_ascii=False, indent=2)

    print(f"✅ Added fact: {fact}")
    print(f"   Saved to: {KNOWLEDGE_FILE}")


def remove_fact(fact_pattern: str):
    """Remove fact (partial match)"""
    if not KNOWLEDGE_FILE.exists():
        print("❌ Error: knowledge.json not found")
        return

    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
        knowledge = json.load(f)

    # Find by partial match
    facts = knowledge.get("facts", [])
    removed = [f for f in facts if fact_pattern in f]
    remaining = [f for f in facts if fact_pattern not in f]

    if not removed:
        print(f"❌ Error: No matching fact found: {fact_pattern}")
        return

    knowledge["facts"] = remaining

    # Save
    with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        json.dump(knowledge, f, ensure_ascii=False, indent=2)

    print(f"✅ Removed {len(removed)} fact(s):")
    for f in removed:
        print(f"   - {f}")
    print(f"   Saved to: {KNOWLEDGE_FILE}")


def list_facts():
    """List knowledge base"""
    if not KNOWLEDGE_FILE.exists():
        print("❌ Error: knowledge.json not found")
        return

    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
        knowledge = json.load(f)

    facts = knowledge.get("facts", [])
    print(f"📚 Knowledge base ({len(facts)} items):")
    for i, fact in enumerate(facts, 1):
        print(f"   {i}. {fact}")


def main():
    parser = argparse.ArgumentParser(description="Update knowledge base")
    parser.add_argument("--add-fact", help="Fact to add")
    parser.add_argument("--remove-fact", help="Fact to remove (partial match)")
    parser.add_argument("--list", action="store_true", help="List knowledge base")

    args = parser.parse_args()

    if args.add_fact:
        add_fact(args.add_fact)
    elif args.remove_fact:
        remove_fact(args.remove_fact)
    elif args.list:
        list_facts()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
