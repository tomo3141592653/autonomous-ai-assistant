#!/usr/bin/env python3
"""
Git custom merge driver for JSON/JSONL files.

Usage in .gitattributes:
    *.jsonl merge=jsonl-merge
    diary.json merge=json-array-merge

Setup:
    git config merge.jsonl-merge.driver "python tools/git-merge-json.py jsonl %O %A %B"
    git config merge.json-array-merge.driver "python tools/git-merge-json.py array %O %A %B"
"""

import json
import sys
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict]:
    """Load JSONL file as list of dicts."""
    items = []
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return items


def save_jsonl(path: Path, items: list[dict]):
    """Save list of dicts as JSONL."""
    with open(path, 'w', encoding='utf-8') as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


def load_json(path: Path) -> Any:
    """Load JSON file."""
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_json(path: Path, data: Any):
    """Save JSON file with proper formatting."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def merge_jsonl(base: Path, ours: Path, theirs: Path) -> bool:
    """
    Merge JSONL files by combining unique entries.
    Uses 'timestamp' field for deduplication and sorting.
    """
    base_items = load_jsonl(base)
    our_items = load_jsonl(ours)
    their_items = load_jsonl(theirs)

    # Create sets of timestamps for deduplication
    base_timestamps = {item.get('timestamp') for item in base_items if item.get('timestamp')}

    # Find new items in each branch
    our_new = [item for item in our_items if item.get('timestamp') not in base_timestamps]
    their_new = [item for item in their_items if item.get('timestamp') not in base_timestamps]

    # Combine: base + our_new + their_new, then deduplicate
    all_items = base_items + our_new + their_new

    # Deduplicate by timestamp
    seen = set()
    unique_items = []
    for item in all_items:
        ts = item.get('timestamp')
        if ts and ts not in seen:
            seen.add(ts)
            unique_items.append(item)
        elif not ts:
            unique_items.append(item)

    # Sort by timestamp
    unique_items.sort(key=lambda x: x.get('timestamp', ''))

    save_jsonl(ours, unique_items)
    return True


def merge_json_array(base: Path, ours: Path, theirs: Path, key_field: str = None) -> bool:
    """
    Merge JSON files containing arrays.

    For diary.json: uses 'datetime' for dedup/sort
    For mini-blog.json: uses 'id' for dedup, 'timestamp' for sort
    For all-creations.json: uses 'number' or 'id' for dedup
    """
    base_data = load_json(base) or {}
    our_data = load_json(ours) or {}
    their_data = load_json(theirs) or {}

    # Determine the array field and key
    filename = ours.name

    if filename == 'diary.json':
        # diary.json is a simple array
        base_items = base_data if isinstance(base_data, list) else []
        our_items = our_data if isinstance(our_data, list) else []
        their_items = their_data if isinstance(their_data, list) else []
        key_field = 'datetime'
        sort_field = 'datetime'
        reverse_sort = True  # newest first
        result_is_array = True

    elif filename == 'mini-blog.json':
        # mini-blog.json has 'posts' array
        base_items = base_data.get('posts', []) if isinstance(base_data, dict) else []
        our_items = our_data.get('posts', []) if isinstance(our_data, dict) else []
        their_items = their_data.get('posts', []) if isinstance(their_data, dict) else []
        key_field = 'id'
        sort_field = 'timestamp'
        reverse_sort = True
        result_is_array = False
        wrapper_key = 'posts'

    elif filename == 'all-creations.json':
        # all-creations.json has 'creations' array
        base_items = base_data.get('creations', []) if isinstance(base_data, dict) else []
        our_items = our_data.get('creations', []) if isinstance(our_data, dict) else []
        their_items = their_data.get('creations', []) if isinstance(their_data, dict) else []
        key_field = 'number'  # or 'id'
        sort_field = 'number'
        reverse_sort = True  # newest (highest number) first
        result_is_array = False
        wrapper_key = 'creations'

    else:
        # Generic array handling
        if isinstance(base_data, list):
            base_items, our_items, their_items = base_data, our_data, their_data
            result_is_array = True
        else:
            # Can't auto-merge unknown structure
            return False
        key_field = 'id'
        sort_field = 'id'
        reverse_sort = False

    # Get base keys for finding new items
    base_keys = {item.get(key_field) for item in base_items if item.get(key_field)}

    # Find new items
    our_new = [item for item in our_items if item.get(key_field) not in base_keys]
    their_new = [item for item in their_items if item.get(key_field) not in base_keys]

    # Combine all
    all_items = base_items + our_new + their_new

    # Deduplicate by key
    seen = set()
    unique_items = []
    for item in all_items:
        k = item.get(key_field)
        if k is not None and k not in seen:
            seen.add(k)
            unique_items.append(item)
        elif k is None:
            unique_items.append(item)

    # Sort
    def sort_key(x):
        val = x.get(sort_field, '')
        if isinstance(val, int):
            return val
        return str(val)

    unique_items.sort(key=sort_key, reverse=reverse_sort)

    # Save result
    if result_is_array:
        save_json(ours, unique_items)
    else:
        result = our_data.copy() if isinstance(our_data, dict) else {}
        result[wrapper_key] = unique_items
        save_json(ours, result)

    return True


def merge_portal_json(base: Path, ours: Path, theirs: Path) -> bool:
    """
    Merge portal.json by section.
    Takes the most recent values for each section.
    """
    base_data = load_json(base) or {}
    our_data = load_json(ours) or {}
    their_data = load_json(theirs) or {}

    result = our_data.copy()

    # For stats, take the higher/newer values
    if 'stats' in their_data:
        their_stats = their_data['stats']
        our_stats = result.get('stats', {})

        # Take max for numeric fields
        for field in ['totalCreations', 'daysAlive', 'knowledgeFiles', 'experienceEntries', 'creations']:
            if field in their_stats:
                our_val = our_stats.get(field, 0)
                their_val = their_stats.get(field, 0)
                if isinstance(our_val, int) and isinstance(their_val, int):
                    our_stats[field] = max(our_val, their_val)

        # Take newer lastUpdated
        if their_stats.get('lastUpdated', '') > our_stats.get('lastUpdated', ''):
            our_stats['lastUpdated'] = their_stats['lastUpdated']
            our_stats['lastDiary'] = their_stats.get('lastDiary', our_stats.get('lastDiary'))

        result['stats'] = our_stats

    # For array sections, merge items
    array_sections = ['messages', 'questionsForTomo']
    for section in array_sections:
        if section in their_data and section in result:
            base_items = base_data.get(section, [])
            base_ids = {item.get('id') for item in base_items if item.get('id')}

            their_new = [item for item in their_data[section] if item.get('id') not in base_ids]

            # Add their new items
            all_items = result[section] + their_new

            # Deduplicate by id
            seen = set()
            unique = []
            for item in all_items:
                item_id = item.get('id')
                if item_id and item_id not in seen:
                    seen.add(item_id)
                    unique.append(item)

            result[section] = unique

    save_json(ours, result)
    return True


def main():
    if len(sys.argv) < 5:
        print("Usage: git-merge-json.py <type> <base> <ours> <theirs>", file=sys.stderr)
        print("  type: jsonl, array, portal", file=sys.stderr)
        sys.exit(1)

    merge_type = sys.argv[1]
    base = Path(sys.argv[2])
    ours = Path(sys.argv[3])
    theirs = Path(sys.argv[4])

    try:
        if merge_type == 'jsonl':
            success = merge_jsonl(base, ours, theirs)
        elif merge_type == 'array':
            success = merge_json_array(base, ours, theirs)
        elif merge_type == 'portal':
            success = merge_portal_json(base, ours, theirs)
        else:
            print(f"Unknown merge type: {merge_type}", file=sys.stderr)
            sys.exit(1)

        if success:
            print(f"✅ Merged {ours.name} successfully", file=sys.stderr)
            sys.exit(0)
        else:
            print(f"❌ Could not auto-merge {ours.name}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"❌ Merge error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
