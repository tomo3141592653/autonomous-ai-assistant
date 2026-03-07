# gateway/

Event-driven scheduler system for Ayumu. Manages periodic session cycles (heartbeat), incoming events (email, Discord, voice), cron jobs, and one-shot timers through a unified Gateway.

## Architecture

The Gateway runs as a long-lived process with multiple event sources, each on its own daemon thread. Events trigger Claude Code sessions via `claude --print`.

- **Heartbeat sessions** run serially in a 5-session cycle (plan -> work -> work -> diary -> maintenance).
- **Event-driven sessions** (email, Discord, voice, cron, timer) run in parallel.

## Quick Start

```bash
# Start with all event sources enabled
uv run gateway/ayumu_gateway.py

# Start with only timer (no email/discord/voice/cron)
uv run gateway/ayumu_gateway.py --no-email --no-discord --no-voice --no-cron

# Start from a specific session number
uv run gateway/ayumu_gateway.py --session 3

# Send a custom message to the first session
uv run gateway/ayumu_gateway.py -m "Focus on code review today"

# Event-only mode (no periodic heartbeat)
uv run gateway/ayumu_gateway.py --no-timer
```

## Python Modules

### ayumu_gateway.py - Main event-driven scheduler

The core Gateway class that:
- Manages the 5-session heartbeat cycle (plan/work/diary/maintenance)
- Dispatches event-driven sessions in parallel threads
- Handles Discord control commands (!pause, !resume, !stop)
- Manages session ID persistence for resume capability
- Auto-selects Claude model (opus/sonnet) based on token usage

### message_builder.py - System message construction

Builds the prompt messages passed to `claude --print` for each session type:
- Heartbeat sessions (with session-specific instructions)
- Event sessions (email, Discord, voice, cron, timer)
- Includes security notices for externally-triggered sessions

### scheduler_utils.py - Scheduler utilities

Shared utility functions:
- Logging (stdout + file)
- Git hook setup
- Embedding consistency checks
- Diary verification
- Social feed fetching (optional hooks)
- GitHub Pages status checks

### session_manager.py - Session ID management

Manages Claude session IDs for the resume feature:
- Saves/loads session IDs for heartbeat continuity
- Tag-based session identification (`[AYUMU_SESSION: <type>]`)
- Loads machine-specific settings from `.env.local`

### event_sources/ - Event source modules

| Module | Event Type | Description |
|--------|-----------|-------------|
| `timer_source.py` | Heartbeat | Periodic timer (default: 60 min) |
| `cron_source.py` | Cron | Schedule-based from `cron.json` |
| `email_source.py` | Email | Polls for unread emails |
| `discord_source.py` | Discord | Discord bot message monitoring |
| `voice_source.py` | Voice | Wake word detection via hearing log |
| `one_timer_source.py` | Timer | One-shot timers from `timers.json` |

## Configuration Files

| File | Description |
|------|-------------|
| `cron.json` | Cron job definitions (daily tests, security checks, cleanup, etc.) |
| `timers.json` | One-shot timer settings (generated at runtime, gitignored) |
| `discord_sessions/` | Discord session persistence (gitignored) |

## Environment Variables

Set these in `.env.local` at the project root:

| Variable | Required | Description |
|----------|----------|-------------|
| `MACHINE_NAME` | Recommended | Human-readable machine name for logging |
| `CLAUDE_PROJECT_DIR` | Required | Claude project directory name (for session ID lookup) |
| `DISCORD_BOT_TOKEN` | For Discord | Discord bot token |
| `DISCORD_OWNER_USER_ID` | For Discord | Owner's Discord user ID (enables per-user restrictions) |
| `AYUMU_HEARING_FILE` | For Voice | Path to the hearing log file (default: `memory/hearing/latest.txt`) |

## CLI Options

```
usage: ayumu_gateway.py [-h] [-m MESSAGE] [--continue] [--session N]
                        [--gemini] [--no-timer] [--no-email] [--no-discord]
                        [--no-voice] [--no-cron]

  -m, --message    Custom message to send to the first session
  --continue       Use --continue (resume) from the first session
  --session N      Start from session N (1-5)
  --gemini         Use Gemini model instead of Claude
  --no-timer       Disable periodic heartbeat (event-only mode)
  --no-email       Disable email polling
  --no-discord     Disable Discord bot
  --no-voice       Disable voice wake word detection
  --no-cron        Disable cron scheduling
```

## Discord Control Commands

When Discord is enabled, the owner can send these commands in any channel:

| Command | Action |
|---------|--------|
| `!pause` | Pause heartbeat timer (events still processed) |
| `!resume` | Resume heartbeat timer |
| `!stop` | Kill all Claude processes and stop Gateway |
| `!help` | Show available commands |
| `!ban @user` | Ban a user (owner only) |
| `!unban <id>` | Unban a user (owner only) |
| `!banlist` | Show ban list (owner only) |

## Session Cycle

```
Session 1 (new)      -> Planning, calendar/task review
Session 2 (resume)   -> Autonomous work
Session 3 (resume)   -> Autonomous work
Session 4 (resume)   -> Diary session (write diary, update memory)
Session 5 (new)      -> Maintenance (system review, cleanup)
                     -> Cycle resets to Session 1
```

Each session runs `claude --print` with a tailored system message. Sessions 2-4 resume the previous session's context via `--resume <session_id>`.
