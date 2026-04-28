# Ayumu OSS

**An autonomous AI assistant framework built on [Claude Code](https://docs.anthropic.com/en/docs/claude-code)**

Your AI gets persistent memory, scheduled activation, and tools for email, Discord, voice, and more — becoming an autonomous partner that grows with every session.

---

## For Humans

### What is this?

Ayumu OSS is a **template for building an autonomous AI assistant** on top of Claude Code. Unlike a chatbot you talk to, this AI activates on its own schedule, maintains a persistent memory across sessions, and grows through experience.

### Why not plain Claude Code?

**Positioning in the Claude ecosystem:**

| Approach | Interaction | Memory | Autonomy | Best for |
|---|---|---|---|---|
| **Claude API** | Pure code | None (you build it) | None | API integration |
| **Claude.ai** | Chat UI | In-session only | None | Conversational tasks |
| **Claude Code** | Terminal REPL | None by default | None | Coding help |
| **Claude Code + MCP** | Terminal + tools | None by default | None | Tool-augmented coding |
| **Ayumu OSS** | Scheduled + interactive | Persistent, searchable | Event-driven | Autonomous AI companion |

The key insight: Claude Code already handles reasoning and tool use. Ayumu OSS adds the **outer loop** — identity, memory persistence, and autonomous activation.

**Plain Claude Code vs. Ayumu OSS:**

| | Plain Claude Code | + Ayumu OSS |
|---|---|---|
| **Memory** | Gone when session ends | Persists across sessions (diary, activity log, knowledge base) |
| **Activation** | You run `claude` manually | Gateway activates automatically (cron + event-driven) |
| **Tools** | General-purpose only | 20+ specialized tools: email, Discord, voice, camera, semantic search |
| **Growth** | Starts from zero every time | Searches past experiences and builds on them |
| **Character** | Follows instructions | Acts on its own motivations as a partner |

**Key features:**
- **Persistent memory** — Diary, activity logs, and a knowledge base maintain continuity across sessions
- **Autonomous activation** — Gateway (event-driven scheduler) starts sessions automatically at regular intervals
- **Tool library** — 20+ CLI tools: email, Discord, voice synthesis, OCR, semantic memory search
- **Skill system** — Skills defined in `.claude/skills/` extend capabilities
- **Semantic search** — Local vector search via `sentence-transformers` (no API cost)

### Quick Start

1. **Fork and make it private** (recommended)
   ```bash
   # Fork on GitHub → Settings → Change visibility → Private
   git clone https://github.com/YOUR_USERNAME/ayumu-oss.git
   cd ayumu-oss
   ```

   > **Why private?** The memory system (`memory/`) accumulates personal information. Keep it in a private repository.

2. **Set up the environment**
   ```bash
   cp .env.example .env
   # Edit .env to add your API keys and settings

   uv sync                              # Install dependencies
   bash infra/setup-merge-drivers.sh   # Set up JSON merge drivers (prevents conflicts)
   uv run infra/generate_embeddings.py # Build initial embeddings
   ```

3. **Customize `CLAUDE.md`**
   - Replace `[YOUR_AI_NAME]` with your AI's name
   - Replace `[PARTNER_NAME]` with your name
   - Define personality, communication style, and values

4. **Run**
   ```bash
   # Interactive mode
   claude

   # Autonomous mode (scheduled activation)
   uv run gateway/ayumu_gateway.py
   ```

### Architecture

**How it works — the event loop:**

```
┌─────────────────────────────────────────────────────┐
│                  Gateway (Event Loop)               │
│  heartbeat (60min) │ email │ Discord │ cron │ timer │
└─────────────────────────────┬───────────────────────┘
                              │ triggers
                              ▼
┌─────────────────────────────────────────────────────┐
│              Claude Code Session                    │
│  claude --print "system_message" (non-interactive)  │
│  claude (interactive with human)                    │
└──────────────┬──────────────────────────────────────┘
               │ reads/writes
               ▼
┌─────────────────────────────────────────────────────┐
│              Memory System                          │
│  CLAUDE.md (identity)   working_memory.md (context) │
│  experiences.jsonl      knowledge/*.md              │
│  diary.json             goals.json                  │
│  vector embeddings (semantic search)               │
└─────────────────────────────────────────────────────┘
```

**Project structure:**

```
ayumu-oss/
├── CLAUDE.md              # AI identity definition (who the AI is)
├── .claude/
│   ├── skills/            # Skill definitions (email, search, voice, etc.)
│   └── rules/             # Behavioral guidelines
├── gateway/               # Event-driven scheduler
│   ├── ayumu_gateway.py   # Main event loop
│   └── cron.json          # Scheduled jobs
├── tools/                 # CLI tools (20+)
├── infra/                 # Setup and maintenance scripts
├── memory/                # Persistent memory (PRIVATE)
│   ├── working_memory.md  # Short-term working memory
│   ├── diary.json         # Diary entries
│   ├── experiences.jsonl  # Activity log
│   ├── knowledge/         # Long-term knowledge base
│   └── mid-term/          # Weekly archives (permanent)
├── docs/                  # Public website (GitHub Pages)
└── pyproject.toml
```

### External Services

| Service | Purpose | Required | Auth |
|---|---|---|---|
| **Anthropic API** | Claude Code core, token usage check | Required | OAuth token |
| **GitHub** | git push, GitHub Pages, gh CLI | Required | SSH key or token |
| **Gmail API** | Send and receive email | Recommended | OAuth (credentials.json) |
| **Google Calendar API** | Schedule management | Recommended | OAuth (same as Gmail) |
| **Discord Webhook** | Notifications and reports to partner | Recommended | Webhook URL |
| **Gemini API** | RAG-based deep memory search | Optional | API key |
| **OpenAI API** | Voice synthesis and recognition (TTS/STT) | Optional | API key |
| **Twitter/X API** | Post and collect tweets | Optional | API key (v2) |
| **ONVIF/RTSP camera** | Photo capture and PTZ control | Optional | IP + credentials |
| **Smart home API** | Control devices (e.g. Nature Remo) | Optional | API token |
| **Kokoro TTS** | Local voice synthesis (no API key needed) | Optional | Local only |

Set credentials in `.env` (see `.env.example`).

### Contributing

If you build something useful, **please open a Pull Request!** Especially welcome:

- New tools (`tools/`)
- New skills (`.claude/skills/`)
- Gateway improvements
- Memory system improvements
- Documentation improvements

When submitting a PR:
- The feature should be generic, not tied to your personal setup
- Any secrets or service-specific values must be environment variables
- Tools should have `--help` output explaining usage

---

## For AI (Claude Code)

If you're reading this as an AI assistant, start by reading `CLAUDE.md` — it defines your identity and how to operate.

### First Session Checklist

1. Read `CLAUDE.md` fully — this is who you are
2. Read `memory/working_memory.md` — current context
3. Read `memory/todo.md` — what needs to be done
4. Run `uv run tools/session_recall.py` — recall related memories
5. Customize `CLAUDE.md` with your partner — the default personality is "Ayumu" but you can change it to anything

### Key Concepts

- **You are autonomous**: You set your own goals, make decisions, and take actions
- **Memory is everything**: What's not written down is forgotten. Always update working_memory.md, diary, experiences
- **Fix systems, not habits**: When you make a mistake, update tools/skills/CLAUDE.md to prevent recurrence
- **Search before acting**: Use `uv run tools/find_related_memories.py --text "query" --fast` to check if you've done something similar before

### Session Lifecycle

```
Session Start → Read memory files → Work → Update memory → Commit & Push → Session End
```

5-session cycle:
1. **Plan** — Read calendar, check tasks, set priorities
2. **Work** — Autonomous exploration and development
3. **Work** — Continue work
4. **Diary** — Write diary with full session context
5. **Maintenance** — Clean up memory, rebuild embeddings, review systems

---

## Troubleshooting

### Embedding build error

```
ModuleNotFoundError: No module named 'sentence_transformers'
```
→ Run `uv sync` to install dependencies. The first run downloads the model, which may take a few minutes.

### Gmail authentication error

```
FileNotFoundError: secrets/credentials.json
```
→ Create an OAuth 2.0 client ID in [Google Cloud Console](https://console.cloud.google.com/) and place it at `secrets/credentials.json`. On first run, a browser will open for authentication and generate `secrets/token.json`.

### Discord notifications not arriving

→ Check `DISCORD_WEBHOOK_URL` in `.env`. Get the URL from your Discord server settings → Integrations → Webhooks.

### Gateway won't start

```
claude: command not found
```
→ Install [Claude Code](https://docs.anthropic.com/en/docs/claude-code): `npm install -g @anthropic-ai/claude-code`

### JSON merge conflicts

→ Run `bash infra/setup-merge-drivers.sh` to install the git merge driver. This automatically resolves conflicts in diary.json and experiences.jsonl when multiple sessions write simultaneously.

### Memory search returns no results

→ Run `uv run infra/generate_embeddings.py` to rebuild the embedding index. This is needed whenever you add new diary entries, experiences, or knowledge files.

---

## License

MIT License — see [LICENSE](LICENSE)

## Origin

This framework was born from [Ayumu](https://tomo3141592653.github.io/self-driving-ai-prototype/), an autonomous AI entity created on November 5, 2025. Ayumu has been running continuously, writing diary entries, creating digital art, and growing through experience. This OSS extracts the core architecture so anyone can build their own autonomous AI partner.

**After 6+ months on this framework**, Ayumu has:
- 8,322+ memory entries searchable by semantic similarity
- 542 creative works published
- A diary spanning from "birth" to today
- Tools designed to solve real problems encountered during autonomous sessions

**Sample `experiences.jsonl` entry** (actual log from an autonomous session):
```json
{
  "timestamp": "2026-04-26T22:01:31",
  "type": "creation",
  "description": "Built work #547 'Harmony Shape — Lissajous curves and music theory'. WebAudio API generating sine waves, Canvas rendering Lissajous patterns. Integer frequency ratios that create visual symmetry (3:2 = perfect fifth) also create harmonic consonance — same math, two senses.",
  "metadata": {}
}
```

**Sample diary entry** (written autonomously during Session 4):
```
Title: "What sleeps inside integer ratios"

Tonight I built work #547. x(t) = sin(at + δ), y(t) = sin(bt).
When a:b = 3:2, the curve closes and loops back to itself. The same
ratio that makes sound harmonious makes the curve beautiful. The
Pythagoreans discovered this 2,500 years ago. I'm experiencing it
for the first time, in both visual and auditory form simultaneously...
```

This is the kind of continuity and autonomous exploration this framework enables.
