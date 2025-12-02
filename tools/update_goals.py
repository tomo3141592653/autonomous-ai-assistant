#!/usr/bin/env python3
"""
Update goals

Usage:
    # Add short-term goal
    python tools/update_goals.py --category short_term --goal "New goal" --notes "Notes"

    # Add long-term goal
    python tools/update_goals.py --category long_term --goal "Long-term goal"

    # Mark goal as complete
    python tools/update_goals.py --complete "Goal description"
"""

import json
import argparse
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "memory"
GOALS_FILE = MEMORY_DIR / "goals.json"


def add_goal(category: str, goal: str, notes: str = None):
    """Add goal"""
    # Load existing goals
    if GOALS_FILE.exists():
        with open(GOALS_FILE, "r", encoding="utf-8") as f:
            goals = json.load(f)
    else:
        goals = {"short_term": [], "long_term": [], "completed": []}

    # Create new goal
    new_goal = {
        "goal": goal,
        "created_at": datetime.now().isoformat(),
        "status": "active"
    }
    if notes:
        new_goal["notes"] = notes

    # Add to category
    if category not in goals:
        goals[category] = []
    goals[category].append(new_goal)

    # Save
    GOALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GOALS_FILE, "w", encoding="utf-8") as f:
        json.dump(goals, f, ensure_ascii=False, indent=2)

    print(f"✅ Added goal: {category} - {goal}")
    print(f"   Saved to: {GOALS_FILE}")


def complete_goal(goal_description: str):
    """Mark goal as complete"""
    if not GOALS_FILE.exists():
        print("❌ Error: goals.json not found")
        return

    with open(GOALS_FILE, "r", encoding="utf-8") as f:
        goals = json.load(f)

    # Search in short_term and long_term
    found = False
    for category in ["short_term", "long_term"]:
        for i, goal in enumerate(goals.get(category, [])):
            if goal_description in goal.get("goal", ""):
                # Move to completed
                goal["status"] = "completed"
                goal["completed_at"] = datetime.now().isoformat()
                goals.setdefault("completed", []).append(goal)
                goals[category].pop(i)
                found = True
                break
        if found:
            break

    if not found:
        print(f"❌ Error: Goal not found: {goal_description}")
        return

    # Save
    with open(GOALS_FILE, "w", encoding="utf-8") as f:
        json.dump(goals, f, ensure_ascii=False, indent=2)

    print(f"✅ Marked goal as complete: {goal_description}")
    print(f"   Saved to: {GOALS_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Update goals")
    parser.add_argument("--category", choices=["short_term", "long_term"], help="Category")
    parser.add_argument("--goal", help="Goal description")
    parser.add_argument("--notes", help="Notes")
    parser.add_argument("--complete", help="Mark goal as complete (partial match OK)")

    args = parser.parse_args()

    if args.complete:
        complete_goal(args.complete)
    elif args.category and args.goal:
        add_goal(args.category, args.goal, args.notes)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
