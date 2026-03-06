#!/usr/bin/env python3
"""
Pre-pull merge script to avoid JSON/JSONL conflicts.

When multiple sessions (autonomous + interactive) run concurrently, both may
append to the same JSON/JSONL files. This script merges those changes before
`git pull`, preventing conflicts.

Usage:
    python tools/pre_pull_merge.py

Run this at the start of every session before doing anything else.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# JSON files to merge (customize these for your project)
# Format: (file_path, merge_key_field)
# merge_key_field: the field used to deduplicate entries (e.g., "id", "timestamp")
JSON_ARRAY_FILES: List[Tuple[str, str]] = [
    ('memory/diary.json', 'datetime'),
]

# JSONL files to merge (append-only logs)
JSONL_FILES: List[str] = [
    'memory/experiences.jsonl',
]


def run(cmd: List[str]) -> Tuple[bool, str]:
    """Run a shell command, return (success, output)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode == 0, (result.stdout + result.stderr).strip()
    except Exception as e:
        return False, str(e)


def load_json(path: Path) -> Optional[Any]:
    """Load a JSON file, return None if it doesn't exist."""
    if not path.exists():
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    """Save data as JSON."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def load_jsonl(path: Path) -> List[Dict]:
    """Load a JSONL file into a list of dicts."""
    if not path.exists():
        return []
    items = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return items


def save_jsonl(path: Path, items: List[Dict]) -> None:
    """Save a list of dicts as JSONL."""
    with open(path, 'w', encoding='utf-8') as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


def merge_json_array(local: List, remote: List, key: str) -> List:
    """
    Merge two JSON arrays, deduplicating by key field.
    Both local and remote entries are preserved; local wins on conflict.
    """
    seen = {}
    # Remote first, then local overwrites
    for item in remote:
        k = item.get(key)
        if k is not None:
            seen[k] = item
    for item in local:
        k = item.get(key)
        if k is not None:
            seen[k] = item
    # Sort by key field
    merged = list(seen.values())
    try:
        merged.sort(key=lambda x: x.get(key, ''))
    except TypeError:
        pass
    return merged


def merge_jsonl(local: List[Dict], remote: List[Dict]) -> List[Dict]:
    """
    Merge two JSONL lists, deduplicating by 'timestamp' field.
    Sorts by timestamp ascending.
    """
    seen = {}
    for item in remote + local:
        key = item.get('timestamp') or item.get('id') or json.dumps(item, sort_keys=True)
        seen[key] = item
    merged = list(seen.values())
    try:
        merged.sort(key=lambda x: x.get('timestamp', ''))
    except TypeError:
        pass
    return merged


def has_local_changes(path: Path) -> bool:
    """Check if a file has local uncommitted changes."""
    ok, out = run(['git', 'diff', '--name-only', str(path)])
    return bool(out.strip())


def main() -> None:
    root = Path(__file__).parent.parent

    # 1. Fetch remote changes (don't apply yet)
    print('🔄 Pre-pull merge: Fetching remote changes...')
    ok, out = run(['git', 'fetch', 'origin'])
    if not ok:
        print(f'⚠️  git fetch failed: {out}')
        print('   Proceeding without merge (check network/auth)')
        return
    print('✅ Fetched remote changes')

    # 2. Check if there are any remote changes at all
    ok, ahead_behind = run(['git', 'rev-list', '--left-right', '--count', 'HEAD...origin/HEAD'])
    if ok and ahead_behind:
        parts = ahead_behind.split()
        if len(parts) == 2 and parts[1] == '0':
            print('✅ Already up to date, no merge needed')
            return

    # 3. Merge JSON array files
    any_json_local = False
    for file_path, key_field in JSON_ARRAY_FILES:
        path = root / file_path
        if not has_local_changes(path):
            continue

        any_json_local = True
        # Get remote version
        ok, remote_content = run(['git', 'show', f'origin/HEAD:{file_path}'])
        if not ok or not remote_content:
            continue

        try:
            local_data = load_json(path)
            remote_data = json.loads(remote_content)
        except (json.JSONDecodeError, TypeError):
            continue

        # Handle both bare arrays and wrapped objects
        if isinstance(local_data, list) and isinstance(remote_data, list):
            merged = merge_json_array(local_data, remote_data, key_field)
            save_json(path, merged)
            run(['git', 'add', str(path)])
            print(f'🔀 Merged {file_path} ({len(merged)} entries)')
        else:
            # Try common wrapper keys
            for wrap_key in ['posts', 'entries', 'items', 'data']:
                if wrap_key in local_data and wrap_key in remote_data:
                    merged_items = merge_json_array(
                        local_data[wrap_key], remote_data[wrap_key], key_field
                    )
                    local_data[wrap_key] = merged_items
                    save_json(path, local_data)
                    run(['git', 'add', str(path)])
                    print(f'🔀 Merged {file_path}.{wrap_key} ({len(merged_items)} entries)')
                    break

    # 4. Merge JSONL files
    for file_path in JSONL_FILES:
        path = root / file_path
        if not has_local_changes(path):
            continue

        any_json_local = True
        ok, remote_content = run(['git', 'show', f'origin/HEAD:{file_path}'])
        if not ok or not remote_content:
            continue

        local_items = load_jsonl(path)
        remote_items = []
        for line in remote_content.splitlines():
            line = line.strip()
            if line:
                try:
                    remote_items.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        merged = merge_jsonl(local_items, remote_items)
        save_jsonl(path, merged)
        run(['git', 'add', str(path)])
        print(f'🔀 Merged {file_path} ({len(merged)} entries)')

    if not any_json_local:
        print('✅ No local JSON changes, safe to pull')

    # 5. Git pull
    ok, out = run(['git', 'pull', '--no-rebase'])
    if ok:
        print('✅ git pull succeeded')
    else:
        print(f'⚠️  git pull had issues: {out}')
        print('   You may need to resolve conflicts manually')


if __name__ == '__main__':
    main()
