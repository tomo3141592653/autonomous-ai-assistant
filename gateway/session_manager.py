#!/usr/bin/env python3
"""
Session ID Management Utilities

Manages session IDs for separating autonomous session chains
from interactive sessions.
"""

import json
import sys
from pathlib import Path

# File to persist the session ID
SESSION_ID_FILE = Path(__file__).parent / "autonomous_session_id.txt"

# Claude history file
CLAUDE_HISTORY_FILE = Path.home() / ".claude" / "history.jsonl"


def load_env_local() -> dict:
    """
    Load .env.local file (machine-specific settings)

    Returns:
        dict: Environment variables

    Raises:
        FileNotFoundError: If .env.local does not exist
        ValueError: If required variables are not set
    """
    env_file = Path(__file__).parent.parent / ".env.local"

    if not env_file.exists():
        print("=" * 80, file=sys.stderr)
        print("ERROR: .env.local file not found!", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        print("", file=sys.stderr)
        print("Please create .env.local file with your machine-specific settings.", file=sys.stderr)
        print("", file=sys.stderr)
        print("Steps:", file=sys.stderr)
        print("1. Copy .env.local.example to .env.local", file=sys.stderr)
        print("   cp .env.local.example .env.local", file=sys.stderr)
        print("", file=sys.stderr)
        print("2. Find your Claude project directory:", file=sys.stderr)
        print("   ls -d ~/.claude/projects/*your-project-name*", file=sys.stderr)
        print("", file=sys.stderr)
        print("3. Edit .env.local and set CLAUDE_PROJECT_DIR to the directory name", file=sys.stderr)
        print("   (just the name part, not the full path)", file=sys.stderr)
        print("", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        raise FileNotFoundError(f".env.local not found at {env_file}")

    env_vars = {}
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()

    # Validate required variables
    if 'CLAUDE_PROJECT_DIR' not in env_vars:
        raise ValueError("CLAUDE_PROJECT_DIR not found in .env.local")

    if env_vars['CLAUDE_PROJECT_DIR'] == 'YOUR_PROJECT_DIR_HERE':
        raise ValueError("Please set CLAUDE_PROJECT_DIR in .env.local (it's still set to the example value)")

    return env_vars


def save_session_id(session_id: str):
    """Save session ID to file"""
    SESSION_ID_FILE.write_text(session_id)


def get_current_session_id() -> str | None:
    """Get the saved session ID (returns None if not found)"""
    if SESSION_ID_FILE.exists():
        return SESSION_ID_FILE.read_text().strip()
    return None


def clear_session_id():
    """Clear the session ID (at cycle end)"""
    if SESSION_ID_FILE.exists():
        SESSION_ID_FILE.unlink()


def _get_project_session_dir() -> Path | None:
    """
    Get the project's session directory.
    Claude Code converts non-alphanumeric characters in the path to hyphens
    for the directory name.
    """
    import re

    project_root = str(Path(__file__).parent.parent.resolve())
    dir_name = re.sub(r'[^a-zA-Z0-9]', '-', project_root)
    project_dir = Path.home() / ".claude" / "projects" / dir_name

    if project_dir.exists():
        return project_dir
    return None


def get_session_id_created_after(start_time: float) -> str | None:
    """
    Get a session ID created/updated after start_time.

    Uses mtime of .jsonl files in the project directory, so it is not
    affected by concurrent sessions (autonomous + interactive).
    """
    project_dir = _get_project_session_dir()
    if not project_dir:
        return None

    try:
        candidates = []
        for f in project_dir.glob("*.jsonl"):
            try:
                if f.stat().st_mtime > start_time:
                    candidates.append(f)
            except OSError:
                continue

        if candidates:
            newest = max(candidates, key=lambda p: p.stat().st_mtime)
            return newest.stem
    except Exception:
        pass

    return None


def get_session_id_by_tag(session_type: str, start_time: float) -> str | None:
    """
    Get a session ID from sessions created after start_time that contain the
    specified tag.

    Uses the [AYUMU_SESSION: <type>] tag at the beginning of the message to
    identify sessions, reliably distinguishing from interactive sessions
    (which have no tag).

    Args:
        session_type: Tag type ("heartbeat", "email", "discord", etc.)
        start_time: Only files created after this time are considered
    """
    project_dir = _get_project_session_dir()
    if not project_dir:
        return None

    tag = f"[AYUMU_SESSION: {session_type}]"

    try:
        candidates = []
        for f in project_dir.glob("*.jsonl"):
            try:
                if f.stat().st_mtime <= start_time:
                    continue
                # Read first few lines to check for the session tag
                with open(f, encoding="utf-8") as fp:
                    head = fp.read(1000)
                if tag in head:
                    candidates.append(f)
            except (OSError, UnicodeDecodeError):
                continue

        if candidates:
            newest = max(candidates, key=lambda p: p.stat().st_mtime)
            return newest.stem
    except Exception:
        pass

    return None


def get_latest_session_id_from_files() -> str | None:
    """
    Get the latest session ID for this project.

    Note: This function should NOT be used for autonomous session ID retrieval.
    history.jsonl only records interactive sessions, so it may return an old
    interactive session ID when no print-mode session exists.
    Use get_session_id_created_after(start_time) instead for autonomous sessions.

    Retrieval methods (in priority order):
    1. ~/.claude/history.jsonl filtered by project path
    2. ~/.claude/projects/<project_dir>/*.jsonl
    """
    import json
    import subprocess
    from pathlib import Path

    project_root = str(Path(__file__).parent.parent.resolve())

    # Method 1: Get project-specific latest session ID from history.jsonl
    try:
        history_file = Path.home() / ".claude" / "history.jsonl"
        if history_file.exists():
            latest_session_id = None
            latest_timestamp = 0
            with open(history_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get('project') == project_root:
                            ts = entry.get('timestamp', 0)
                            if ts > latest_timestamp:
                                latest_timestamp = ts
                                latest_session_id = entry.get('sessionId')
                    except json.JSONDecodeError:
                        continue
            if latest_session_id:
                return latest_session_id
    except Exception as e:
        print(f"Warning: Could not read history.jsonl: {e}", file=sys.stderr)

    # Method 2: ~/.claude/projects/<project_dir>/*.jsonl
    try:
        env_vars = load_env_local()
        project_dir_name = env_vars['CLAUDE_PROJECT_DIR']
        project_dir = Path.home() / ".claude" / "projects" / project_dir_name

        if project_dir.exists():
            result = subprocess.run(
                ["bash", "-c", f"ls -t {project_dir}/*.jsonl 2>/dev/null | head -1"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                latest_file = Path(result.stdout.strip())
                return latest_file.stem
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Error getting latest session ID: {e}", file=sys.stderr)

    return None
