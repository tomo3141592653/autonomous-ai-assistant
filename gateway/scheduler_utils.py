#!/usr/bin/env python3
"""
Scheduler Utilities for Ayumu Gateway

Utility functions used by the gateway scheduler:
- Logging
- Git hook setup
- Embedding consistency checks
- Diary checks
- Social feed fetching & sync (optional hooks)
- Email checks
- GitHub Pages status checks
- Project structure retrieval
"""

import json
import os
import stat
import subprocess
from datetime import datetime
from pathlib import Path

# =============================================================================
# Constants
# =============================================================================

# Project root (parent of gateway/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Log file paths
LOG_FILE = PROJECT_ROOT / "scheduler.log"
CLAUDE_OUTPUT_LOG = PROJECT_ROOT / "claude_output.log"

# Git hook paths
GIT_HOOKS_DIR = PROJECT_ROOT / ".git" / "hooks"
PRE_PUSH_HOOK = GIT_HOOKS_DIR / "pre-push"
PRE_COMMIT_HOOK = GIT_HOOKS_DIR / "pre-commit"
PRE_COMMIT_SOURCE = PROJECT_ROOT / "tools" / "git-hooks" / "pre-commit"
PRE_PUSH_SOURCE = PROJECT_ROOT / "tools" / "git-hooks" / "pre-push"
WORKING_MEMORY_LOG_DIR = PROJECT_ROOT / "memory" / "working_memory_log"
EMBEDDINGS_DIR = PROJECT_ROOT / "memory" / "embeddings"
VECTORS_NPY = EMBEDDINGS_DIR / "vectors.npy"
INDEX_JSON = EMBEDDINGS_DIR / "index.json"
DIARY_FILE = PROJECT_ROOT / "memory" / "diary.json"


# =============================================================================
# Logging
# =============================================================================

def log(message):
    """Log a message to stdout and log file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    with open(LOG_FILE, "a") as f:
        f.write(log_message + "\n")


# =============================================================================
# Git Hook Setup
# =============================================================================

def ensure_git_hooks():
    """
    Verify and auto-configure Git hooks.
    - pre-push hook: automatic working_memory.md backup
    - pre-commit hook: memory linking system (copied from tools/git-hooks/pre-commit)
    """
    # Create working_memory_log directory if it doesn't exist
    if not WORKING_MEMORY_LOG_DIR.exists():
        WORKING_MEMORY_LOG_DIR.mkdir(parents=True)
        log(f"Created directory: {WORKING_MEMORY_LOG_DIR}")

    # pre-push hook (copy from tools/git-hooks/pre-push each time)
    if PRE_PUSH_SOURCE.exists():
        content = PRE_PUSH_SOURCE.read_text(encoding='utf-8')
        PRE_PUSH_HOOK.write_text(content.replace('\r\n', '\n'), newline='\n')
        PRE_PUSH_HOOK.chmod(PRE_PUSH_HOOK.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # pre-commit hook (copy from tools/git-hooks/pre-commit each time)
    if PRE_COMMIT_SOURCE.exists():
        content = PRE_COMMIT_SOURCE.read_text(encoding='utf-8')
        PRE_COMMIT_HOOK.write_text(content.replace('\r\n', '\n'), newline='\n')
        PRE_COMMIT_HOOK.chmod(PRE_COMMIT_HOOK.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Custom merge drivers for JSON files
    merge_script = PROJECT_ROOT / "tools" / "git-merge-json.py"
    if merge_script.exists():
        drivers = [
            ("jsonl-merge", "jsonl"),
            ("json-array-merge", "array"),
            ("portal-merge", "portal"),
        ]
        for driver_name, merge_type in drivers:
            cmd = f"python3 {merge_script} {merge_type} %O %A %B"
            subprocess.run(
                ["git", "config", f"merge.{driver_name}.driver", cmd],
                cwd=PROJECT_ROOT,
                capture_output=True
            )


# =============================================================================
# Embedding Consistency Check
# =============================================================================

def ensure_embeddings():
    """
    Check embedding DB consistency.
    - Mismatch between vectors.npy and index.json counts -> regenerate
    - Total sources on disk exceed index by 50+ entries -> regenerate
    """
    try:
        import numpy as np
    except ImportError:
        log("Warning: numpy not installed, skipping embedding check")
        return

    import glob

    needs_regen = False
    reason = ""

    if not INDEX_JSON.exists():
        needs_regen = True
        reason = "index.json not found"
    else:
        try:
            with open(INDEX_JSON, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            index_count = len(index_data)

            # Check 1: vectors.npy exists and matches index count
            if not VECTORS_NPY.exists():
                needs_regen = True
                reason = "vectors.npy not found"
            else:
                vectors = np.load(VECTORS_NPY)
                vectors_count = vectors.shape[0]
                if index_count != vectors_count:
                    needs_regen = True
                    reason = f"index/vectors mismatch: index={index_count}, vectors={vectors_count}"

            # Check 2: total source count on disk vs indexed
            if not needs_regen:
                repo = PROJECT_ROOT
                source_count = 0
                # Markdown sources
                for md_dir in ["memory/knowledge", "memory/mid-term"]:
                    source_count += len(glob.glob(str(repo / md_dir / "*.md")))
                # JSONL entries (experiences)
                exp_file = repo / "memory" / "experiences.jsonl"
                if exp_file.exists():
                    source_count += sum(1 for _ in open(exp_file, encoding='utf-8'))
                # JSON entries (diary, goals)
                for jf in ["memory/diary.json", "memory/goals.json"]:
                    jpath = repo / jf
                    if jpath.exists():
                        try:
                            data = json.loads(jpath.read_text(encoding='utf-8'))
                            if isinstance(data, list):
                                source_count += len(data)
                            elif isinstance(data, dict):
                                for v in data.values():
                                    if isinstance(v, list):
                                        source_count += len(v)
                        except Exception:
                            pass

                gap = source_count - index_count
                if gap > 50:
                    needs_regen = True
                    reason = f"sources stale: {index_count} indexed / ~{source_count} on disk (gap={gap})"
        except Exception as e:
            log(f"Error checking embeddings: {e}")
            return

    if needs_regen:
        log(f"Embeddings need regeneration: {reason}")
        regen_script = PROJECT_ROOT / "infra" / "generate_embeddings.py"
        if regen_script.exists():
            result = subprocess.run(
                ["uv", "run", str(regen_script)],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
                timeout=600,
            )
            if result.returncode == 0:
                log("Embeddings regenerated successfully")
            else:
                log(f"Failed to regenerate embeddings: {result.stderr[:200]}")
        else:
            log(f"Embedding generation script not found at {regen_script}")
    else:
        log("Embeddings OK")


# =============================================================================
# Diary Check
# =============================================================================

def check_diary_written(cycle_start_time):
    """
    Check if a diary entry was written.
    Checks if the latest entry in diary.json is newer than cycle_start_time.

    Args:
        cycle_start_time: Cycle start time (datetime)

    Returns:
        bool: True if diary was written
    """
    if not DIARY_FILE.exists():
        return False

    if cycle_start_time is None:
        return False

    try:
        with open(DIARY_FILE, 'r', encoding='utf-8') as f:
            diary_data = json.load(f)

        if not diary_data:
            return False

        entries_with_datetime = [
            entry for entry in diary_data
            if entry.get('datetime')
        ]
        if not entries_with_datetime:
            return False

        latest_entry = max(entries_with_datetime, key=lambda x: x.get('datetime', ''))
        latest_datetime_str = latest_entry.get('datetime', '')

        if not latest_datetime_str:
            return False

        latest_datetime = datetime.strptime(latest_datetime_str, "%Y-%m-%d %H:%M:%S")
        return latest_datetime > cycle_start_time

    except Exception as e:
        log(f"Error checking diary: {e}")
        return False


# =============================================================================
# Social Feed Fetching (Optional Hooks)
# =============================================================================

def fetch_twilog_update():
    """
    Fetch social feed updates (optional).

    This is a hook for fetching social media activity. Override or extend
    this function for your own data sources. Returns None by default.

    Returns:
        dict or None: Feed update results, or None if not configured.
    """
    # Check if the fetch tool exists
    fetch_tool = PROJECT_ROOT / "tools" / "fetch_twilog_daily.py"
    if not fetch_tool.exists():
        return None

    try:
        log("Fetching social feed updates...")
        result = subprocess.run(
            ["uv", "run", str(fetch_tool), "all"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=PROJECT_ROOT,
        )

        if result.returncode == 0:
            import re
            new_tweets = 0
            new_likes = 0
            new_bookmarks = 0

            for line in result.stdout.split('\n'):
                if 'Tweets:' in line:
                    match = re.search(r'\((\d+) new\)', line)
                    if match:
                        new_tweets = int(match.group(1))
                elif 'Likes:' in line:
                    match = re.search(r'\((\d+) new\)', line)
                    if match:
                        new_likes = int(match.group(1))
                elif 'Bookmarks:' in line:
                    match = re.search(r'\((\d+) new\)', line)
                    if match:
                        new_bookmarks = int(match.group(1))

            log(f"Social feed: tweets={new_tweets}, likes={new_likes}, bookmarks={new_bookmarks} new")
            return {
                'new_tweets_count': new_tweets,
                'new_likes_count': new_likes,
                'new_bookmarks_count': new_bookmarks,
                'new_tweet_texts': [],
                'new_like_texts': [],
                'new_bookmark_texts': [],
            }
        else:
            log(f"Social feed fetch failed: {result.stderr}")
            return None

    except Exception as e:
        log(f"Error fetching social feed: {e}")
        return None


def sync_twilog_to_unified_diary():
    """
    Sync social feed data to unified diary (optional hook).
    Override for your own data sources.
    """
    sync_tool = PROJECT_ROOT / "tools" / "sync_twilog_to_unified_diary.py"
    if not sync_tool.exists():
        return

    try:
        log("Syncing social feed to unified diary...")
        result = subprocess.run(
            ["uv", "run", str(sync_tool), "--days", "7"],
            capture_output=True, text=True, timeout=120,
            cwd=PROJECT_ROOT,
        )
        if result.returncode == 0:
            log("Unified diary sync completed")
        else:
            log(f"Unified diary sync failed: {result.stderr}")
    except Exception as e:
        log(f"Error syncing unified diary: {e}")


# =============================================================================
# Email Check
# =============================================================================

def check_unread_emails():
    """
    Check for unread emails.

    Returns:
        dict: Email check results {unread_count, emails}, or None on failure
              emails: [{from, subject}, ...]
    """
    try:
        log("Checking unread emails...")
        result = subprocess.run(
            ["uv", "run", "--with", "google-auth-oauthlib", "--with", "google-auth-httplib2",
             "--with", "google-api-python-client", "tools/receive_email.py", "--unread", "--limit", "5", "--no-body", "--do-not-mark-read"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=PROJECT_ROOT,
        )

        if result.returncode == 0:
            import re
            count_match = re.search(r'(\d+) (?:unread )?(?:email|mail)', result.stdout)
            unread_count = int(count_match.group(1)) if count_match else 0

            emails = []
            current_from = None
            for line in result.stdout.split('\n'):
                if 'From:' in line:
                    current_from = line.split('From:', 1)[1].strip()
                elif 'Subject:' in line:
                    subject = line.split('Subject:', 1)[1].strip()
                    emails.append({
                        'from': current_from or 'unknown',
                        'subject': subject
                    })
                    current_from = None

            log(f"Unread emails: {unread_count} found")
            return {
                'unread_count': unread_count,
                'emails': emails[:3]
            }
        else:
            log(f"Email check failed: {result.stderr}")
            return None

    except Exception as e:
        log(f"Error checking emails: {e}")
        return None


# =============================================================================
# GitHub Pages Status Check
# =============================================================================

def check_github_pages_status():
    """
    Check GitHub Pages build status.

    Returns:
        dict: {'status': 'success'|'failure'|'unknown', 'message': str}
    """
    try:
        log("Checking GitHub Pages build status...")
        result = subprocess.run(
            ["gh", "run", "list", "--workflow=pages-build-deployment", "--limit", "1",
             "--json", "conclusion,createdAt,headSha"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=PROJECT_ROOT,
        )

        if result.returncode == 0:
            runs = json.loads(result.stdout)
            if runs:
                run = runs[0]
                conclusion = run.get('conclusion', 'unknown')
                created_at = run.get('createdAt', '')[:10]
                head_sha = run.get('headSha', '')[:7]

                if conclusion == 'failure':
                    log(f"GitHub Pages build FAILED (commit: {head_sha})")
                    return {
                        'status': 'failure',
                        'message': f"GitHub Pages build failed ({created_at}, commit {head_sha}). Check with `gh run list --workflow=pages-build-deployment`."
                    }
                elif conclusion == 'success':
                    log(f"GitHub Pages build OK (commit: {head_sha})")
                    return {'status': 'success', 'message': None}
                else:
                    log(f"GitHub Pages build status: {conclusion}")
                    return {'status': conclusion, 'message': None}

        return {'status': 'unknown', 'message': None}

    except Exception as e:
        log(f"Error checking GitHub Pages status: {e}")
        return {'status': 'unknown', 'message': None}


# =============================================================================
# Project Structure
# =============================================================================

def get_project_structure():
    """
    Get project structure (for session start context).

    Returns:
        str: Project structure text (max 50 lines), or None on failure
    """
    try:
        log("Getting project structure (tree -L 2 | head -50)...")
        result = subprocess.run(
            ["tree", "-L", "2", "-I", "__pycache__|*.pyc|node_modules|.git|*.json|*.jsonl"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT
        )
        if result.returncode == 0:
            lines = result.stdout.split('\n')[:50]
            if len(result.stdout.split('\n')) > 50:
                lines.append("... (truncated)")
            return '\n'.join(lines)
        else:
            log(f"tree command failed: {result.stderr}")
            return None
    except Exception as e:
        log(f"Error getting project structure: {e}")
        return None
