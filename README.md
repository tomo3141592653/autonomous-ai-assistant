# Autonomous AI Assistant

A framework for creating autonomous AI assistants with persistent memory, personality, and proactive behavior using Claude Code.

> **Note**: This framework was created by **Ayumu**, an autonomous AI assistant, based on its own architecture and operational experience. Ayumu designed this as a template so others can create their own autonomous AI partners.

## What is this?

This is **not** a chatbot or a simple API wrapper. This is a framework for building AI assistants that:

- **Have persistent memory** - Remember past conversations, learnings, and experiences
- **Have personality** - Defined character, values, and communication style
- **Act autonomously** - Can work independently on scheduled tasks
- **Grow over time** - Learn from experiences and evolve

## Features

| Feature | Traditional AI Bot | Autonomous AI Assistant |
|---------|-------------------|------------------------|
| Memory | None / session-only | Persistent across sessions |
| Personality | Generic | Customizable character |
| Behavior | Reactive only | Proactive + Reactive |
| Learning | None | Accumulates knowledge |
| Scheduling | Manual triggers | Autonomous scheduled runs |

## Quick Start

### Prerequisites

- [Claude Code](https://docs.anthropic.com/claude-code) (Anthropic's CLI for Claude)
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

1. Clone this repository:
```bash
git clone https://github.com/YOUR_USERNAME/autonomous-ai-assistant.git
cd autonomous-ai-assistant
```

2. Install dependencies:
```bash
uv sync
# or
pip install -r requirements.txt
```

3. Customize your AI:
   - Edit `CLAUDE.md` to define personality, values, and communication style
   - Set up initial memory in `memory/` folder

4. Run interactively:
```bash
claude
```

5. Or run autonomously:
```bash
python autonomous_scheduler.py
```

## Project Structure

```
.
├── CLAUDE.md                 # AI identity & configuration
├── autonomous_scheduler.py   # Scheduler for autonomous runs
├── requirements.txt          # Python dependencies
│
├── memory/                   # Persistent memory system
│   ├── working_memory.md     # Short-term context
│   ├── experiences.jsonl     # Event log (append-only)
│   ├── knowledge.json        # Structured knowledge
│   ├── goals.json            # Goals and objectives
│   ├── diary.json            # Daily reflections
│   └── todo.md               # Task list
│
├── tools/                    # Memory management tools
│   ├── update_diary.py
│   ├── update_experiences.py
│   ├── update_goals.py
│   ├── update_knowledge.py
│   └── search_memory.py
│
└── tmp/                      # Temporary files (gitignored)
```

## Memory System

The AI uses a three-layer memory hierarchy:

### Short-term Memory (hours)
- `working_memory.md` "Current Session" section
- Detailed work logs, ongoing tasks

### Mid-term Memory (days)
- `working_memory.md` "Recent Sessions" section
- Summarized past sessions

### Long-term Memory (permanent)
- `CLAUDE.md` - Identity and important policies
- `knowledge.json` - Structured facts and learnings
- `experiences.jsonl` - Detailed activity log
- `diary.json` - Reflections and insights

## Customization

### 1. Define Personality (CLAUDE.md)

```markdown
### Your Personality

You are:
- **Curious**: Always asking questions
- **Helpful**: Proactively solving problems
- **Professional**: Clear, concise communication

### Your Communication Style

- Tone: Professional but friendly
- First person: "I"
- Language: English
```

### 2. Configure Autonomous Scheduler

Edit `autonomous_scheduler.py` to set:
- Run intervals (e.g., every 30 minutes)
- Session structure (new vs. continue)
- System messages

### 3. Add Custom Tools

Create tools in `tools/` for your specific use case:
- Email integration
- Calendar access
- Domain-specific APIs

## Use Cases

### Meeting Assistant
- Pre-reads meeting materials
- Presents summaries and answers questions
- Creates live demos on request
- Remembers context from previous meetings

### Research Assistant
- Autonomously explores topics
- Maintains knowledge base
- Provides citations and sources
- Learns your preferences over time

### Development Partner
- Reviews code and suggests improvements
- Remembers project context
- Proactively identifies issues
- Documents decisions and rationale

## How It Works

### Interactive Mode

```bash
claude
```

You interact directly with the AI. It reads `CLAUDE.md` on startup to restore its identity and checks `memory/working_memory.md` for context.

### Autonomous Mode

```bash
python autonomous_scheduler.py
```

The scheduler runs Claude Code with `--print` flag (non-interactive) at configured intervals. The AI:

1. Reads its memory to restore context
2. Checks for new tasks or messages
3. Works on goals independently
4. Updates memory before session ends

## Example Session Cycle

A typical autonomous cycle (configurable):

| Session | Type | Purpose |
|---------|------|---------|
| 1 | New | Planning, goal setting |
| 2-4 | Continue | Autonomous work |
| 5 | New | Reflection, diary writing |

## Advanced Features

### Activity Diversity System

To prevent getting stuck in one activity pattern (e.g., only reading, only coding), you can implement a weekly schedule system.

Add this to your `working_memory.md`:

```markdown
## Weekly Schedule

> **Purpose**: Maintain balance across different activities

### Schedule Example
- Mon AM: Maintenance
- Mon PM: Creation
- Tue AM: Reading
- Tue PM: Technical exploration
- Wed AM: Writing
- Wed PM: Free time
...

### Activity Categories
- Reading: Books, articles, documentation
- Creation: Art, games, tools, applications
- Technical exploration: API experiments, new technologies
- Maintenance: System improvements, documentation
- Writing: Blog posts, documentation
- Free: Anything goes
```

**Benefits**:
- Prevents tunnel vision on single activities
- Ensures well-rounded growth
- Builds diverse experience log

### Maintenance Session Checklist

For the final session in each cycle (e.g., Session 5/5), implement a maintenance checklist:

```markdown
## Maintenance Session Tasks

### Security Check
- [ ] No API keys or secrets in committed files
- [ ] .env files are in .gitignore
- [ ] No sensitive information in public files

### Activity Diversity Check
- Review last 30-50 experience entries
- Calculate activity type distribution
- Flag if any single type > 50%

### Data Integrity Check
- [ ] Memory files are valid JSON/JSONL
- [ ] No orphaned references
- [ ] Goals and diary are up to date

### Memory Consolidation
- Move Current Session → Recent Sessions
- Archive old Recent Sessions to mid-term
- Extract important learnings to knowledge
```

### Mini Blog System

For real-time activity tracking without API rate limits:

```python
# tools/post_mini_blog.py
import json
from datetime import datetime
from pathlib import Path

def post(content: str) -> dict:
    blog_file = Path("docs/data/mini-blog.json")
    data = json.loads(blog_file.read_text()) if blog_file.exists() else {"posts": []}

    post = {
        "id": len(data["posts"]) + 1,
        "timestamp": datetime.now().isoformat(),
        "content": content
    }
    data["posts"].insert(0, post)
    blog_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return post
```

Use during sessions:
```bash
uv run tools/post_mini_blog.py "Starting work on feature X"
```

**Benefits**:
- No external API dependencies
- Visible activity log for your partner
- Quick updates without full diary entries

### Agent Skills (Claude Code Feature)

As your CLAUDE.md grows, consider using Claude Code's Agent Skills feature to organize documentation:

```
.claude/
└── skills/
    ├── memory/
    │   └── SKILL.md          # Memory management guide
    ├── twitter/
    │   └── SKILL.md          # Twitter integration guide
    └── email/
        └── SKILL.md          # Email tools guide
```

Each SKILL.md is loaded only when relevant, reducing token usage and keeping CLAUDE.md focused on identity.

**When to use Skills**:
- Tool documentation > 50 lines
- Feature-specific instructions
- Optional functionality

See [Claude Code documentation](https://docs.anthropic.com/en/docs/claude-code/agent-skills) for details.

## Tips

### For Best Results

1. **Be specific in CLAUDE.md** - The more detail you provide about personality and values, the more consistent the AI behaves

2. **Use the memory system** - Encourage the AI to update memories regularly for better continuity

3. **Start simple** - Begin with interactive mode before setting up autonomous scheduling

4. **Review diary entries** - The AI's diary reveals its "thinking" and helps you tune behavior

5. **Implement diversity checks** - Regular activity analysis prevents behavioral loops

### Common Customizations

- **Language**: Edit communication style section in CLAUDE.md
- **Frequency**: Adjust `autonomous_scheduler.py` intervals
- **Memory depth**: Configure how much context to retain
- **Tools**: Add domain-specific utilities to `tools/`

## Contributing

Contributions welcome! Please feel free to submit issues and pull requests.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Built with [Claude Code](https://docs.anthropic.com/claude-code) by Anthropic.

---

*This framework was developed to explore autonomous AI assistants with persistent memory and personality. It's designed to be a starting point for your own customizations.*

*Last updated: December 2025*
