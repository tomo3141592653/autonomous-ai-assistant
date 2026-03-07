#!/usr/bin/env python3
"""
Pre-pull merge script to avoid JSON conflicts.

Fetches remote changes and merges JSON files before git pull.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

# Files to merge
JSON_FILES = [
    'docs/data/mini-blog.json',
    'memory/diary.json',
    'docs/data/all-creations.json',
    'docs/data/portal.json',
]

JSONL_FILES = [
    'memory/experiences.jsonl',
]


def run_command(cmd: List[str], cwd: Path = None) -> tuple[bool, str]:
    """Run shell command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or Path.cwd(),
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def load_json(path: Path) -> Any:
    """Load JSON file."""
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_json(path: Path, data: Any):
    """Save JSON file."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def load_jsonl(path: Path) -> List[Dict]:
    """Load JSONL file."""
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


def save_jsonl(path: Path, items: List[Dict]):
    """Save JSONL file."""
    with open(path, 'w', encoding='utf-8') as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


def merge_mini_blog(local_data: Dict, remote_data: Dict) -> Dict:
    """Merge mini-blog.json by id and timestamp."""
    local_posts = local_data.get('posts', [])
    remote_posts = remote_data.get('posts', [])

    # Build dict by id, preferring newer timestamp
    posts_by_id = {}

    for post in local_posts + remote_posts:
        post_id = post.get('id')
        if post_id is None:
            continue

        if post_id not in posts_by_id:
            posts_by_id[post_id] = post
        else:
            # Compare timestamps, keep newer
            existing_ts = posts_by_id[post_id].get('timestamp', '')
            new_ts = post.get('timestamp', '')
            if new_ts > existing_ts:
                posts_by_id[post_id] = post

    # Sort by timestamp descending
    merged_posts = sorted(posts_by_id.values(), key=lambda x: x.get('timestamp', ''), reverse=True)

    # Take lastUpdated from newer
    last_updated = max(
        local_data.get('lastUpdated', ''),
        remote_data.get('lastUpdated', '')
    )

    return {
        'lastUpdated': last_updated,
        'posts': merged_posts
    }


def merge_diary(local_data: List, remote_data: List) -> List:
    """Merge diary.json by datetime, preferring more complete entries."""
    entries_by_datetime = {}

    for entry in local_data + remote_data:
        dt = entry.get('datetime')
        if dt is None:
            continue

        if dt not in entries_by_datetime:
            entries_by_datetime[dt] = entry
        else:
            # Prefer entry with more complete content
            existing = entries_by_datetime[dt]

            # Compare by content length (more detailed entry wins)
            existing_content_len = len(existing.get('content', ''))
            new_content_len = len(entry.get('content', ''))

            if new_content_len > existing_content_len:
                entries_by_datetime[dt] = entry
            elif new_content_len == existing_content_len:
                # If content is same length, prefer entry with more related_memories
                existing_memories = len(existing.get('related_memories', []))
                new_memories = len(entry.get('related_memories', []))
                if new_memories > existing_memories:
                    entries_by_datetime[dt] = entry
            # Otherwise keep existing

    return sorted(entries_by_datetime.values(), key=lambda x: x.get('datetime', ''), reverse=True)


def merge_all_creations(local_data: Dict, remote_data: Dict) -> Dict:
    """Merge all-creations.json by number."""
    local_creations = local_data.get('creations', [])
    remote_creations = remote_data.get('creations', [])

    creations_by_number = {}

    for creation in local_creations + remote_creations:
        num = creation.get('number')
        if num is None:
            continue

        if num not in creations_by_number:
            creations_by_number[num] = creation
        else:
            # Keep the one with more fields (more complete)
            if len(creation) > len(creations_by_number[num]):
                creations_by_number[num] = creation

    merged = sorted(creations_by_number.values(), key=lambda x: x.get('number', 0), reverse=True)

    return {
        'creations': merged,
        'metadata': remote_data.get('metadata', local_data.get('metadata', {}))
    }


def merge_portal(local_data: Dict, remote_data: Dict) -> Dict:
    """Merge portal.json - prefer remote for most sections.

    portal.json structure:
    - messages: list of {id, ...}
    - questionsForTomo: dict with 'items' list
    - recommendationsForTomo: dict with 'items' list
    - stats, eventsFromLikes, etc.: simple dicts (prefer remote)
    """
    result = remote_data.copy()

    # Merge messages array (has id)
    if 'messages' in local_data and 'messages' in remote_data:
        items_by_id = {}
        for item in remote_data['messages'] + local_data['messages']:
            item_id = item.get('id')
            if item_id:
                items_by_id[item_id] = item
        result['messages'] = list(items_by_id.values())

    # For dict sections with 'items', just prefer remote (lastUpdated)
    # These are manually curated and should not be auto-merged

    return result


def merge_experiences_jsonl(local_items: List, remote_items: List) -> List:
    """Merge experiences.jsonl by timestamp."""
    items_by_ts = {}

    for item in local_items + remote_items:
        ts = item.get('timestamp')
        if ts:
            items_by_ts[ts] = item

    return sorted(items_by_ts.values(), key=lambda x: x.get('timestamp', ''))


def main():
    repo_root = Path(__file__).parent.parent

    print("🔄 Pre-pull merge: Fetching remote changes...")

    # 1. Fetch remote
    success, output = run_command(['git', 'fetch', 'origin', 'master'], repo_root)
    if not success:
        print(f"❌ git fetch failed: {output}")
        return 1

    print("✅ Fetched remote changes")

    # 2. Check if there are local uncommitted changes in JSON files
    has_local_changes = False
    for file_path in JSON_FILES + JSONL_FILES:
        full_path = repo_root / file_path
        if full_path.exists():
            success, output = run_command(['git', 'diff', '--quiet', file_path], repo_root)
            if not success:  # exit code != 0 means there are changes
                has_local_changes = True
                break

    if not has_local_changes:
        print("✅ No local JSON changes, safe to pull")
        return 0

    print("📝 Found local JSON changes, merging with remote...")

    # 3. For each JSON file, merge local and remote
    for file_path in JSON_FILES:
        full_path = repo_root / file_path
        if not full_path.exists():
            continue

        # Get remote version
        success, remote_content = run_command(
            ['git', 'show', f'origin/master:{file_path}'],
            repo_root
        )
        if not success:
            print(f"⚠️  Skipping {file_path} (not on remote)")
            continue

        try:
            local_data = load_json(full_path)
            remote_data = json.loads(remote_content)

            # Merge based on file type
            if file_path == 'docs/data/mini-blog.json':
                merged = merge_mini_blog(local_data, remote_data)
            elif file_path == 'memory/diary.json':
                merged = merge_diary(local_data, remote_data)
            elif file_path == 'docs/data/all-creations.json':
                merged = merge_all_creations(local_data, remote_data)
            elif file_path == 'docs/data/portal.json':
                merged = merge_portal(local_data, remote_data)
            else:
                print(f"⚠️  Unknown merge strategy for {file_path}")
                continue

            save_json(full_path, merged)
            print(f"✅ Merged {file_path}")

        except Exception as e:
            print(f"❌ Failed to merge {file_path}: {e}")
            return 1

    # 4. Merge JSONL files
    for file_path in JSONL_FILES:
        full_path = repo_root / file_path
        if not full_path.exists():
            continue

        success, remote_content = run_command(
            ['git', 'show', f'origin/master:{file_path}'],
            repo_root
        )
        if not success:
            continue

        try:
            local_items = load_jsonl(full_path)
            remote_items = []
            for line in remote_content.split('\n'):
                line = line.strip()
                if line:
                    remote_items.append(json.loads(line))

            merged = merge_experiences_jsonl(local_items, remote_items)
            save_jsonl(full_path, merged)
            print(f"✅ Merged {file_path}")

        except Exception as e:
            print(f"❌ Failed to merge {file_path}: {e}")
            return 1

    # 5. Stage merged files
    for file_path in JSON_FILES + JSONL_FILES:
        full_path = repo_root / file_path
        if full_path.exists():
            run_command(['git', 'add', file_path], repo_root)

    print("✅ Pre-pull merge complete!")

    # 6. Now safe to git pull
    print("🔄 Running git pull...")

    # Get current HEAD before pull
    success, old_head = run_command(['git', 'rev-parse', 'HEAD'], repo_root)
    if not success:
        old_head = None
    else:
        old_head = old_head.strip()

    success, output = run_command(['git', 'pull'], repo_root)
    if not success:
        print(f"❌ git pull failed: {output}")
        return 1

    print("✅ git pull successful!")
    print(output)

    # Show what changed
    if old_head:
        success, new_head = run_command(['git', 'rev-parse', 'HEAD'], repo_root)
        if success and new_head.strip() != old_head:
            print("\n📊 Changes from pull:")
            success, changes = run_command(['git', 'diff', '--stat', old_head, 'HEAD'], repo_root)
            if success:
                print(changes)

            # Show commit messages
            print("\n📝 New commits:")
            success, commits = run_command(
                ['git', 'log', '--oneline', '--no-merges', f'{old_head}..HEAD'],
                repo_root
            )
            if success:
                print(commits)
        else:
            print("(Already up to date)")

    return 0


if __name__ == '__main__':
    sys.exit(main())
