# Memory System

Persistent memory that maintains continuity across sessions.

## Structure

```
memory/
├── working_memory.md      # Current session context (read every session)
├── todo.md                # Task list
├── goals.json             # Short-term and long-term goals
├── diary.json             # Daily diary entries
├── experiences.jsonl      # Activity log (append-only)
├── knowledge/             # Long-term knowledge base (Markdown files)
├── mid-term/              # Weekly archives (permanent, never delete)
├── working_memory_log/    # Past working_memory snapshots
└── embeddings/            # Vector search index (auto-generated)
```

## Memory Flow

```
Current Session → summarize → Recent Sessions → summarize → mid-term/ → important learnings → knowledge/
```

## Key Principles

1. **If it's not in files read at session start, it's forgotten** — put important things in working_memory.md, todo.md, or knowledge/
2. **Fix systems, not habits** — "be more careful" doesn't work. Update tools, add automation, write to CLAUDE.md
3. **Search before acting** — check if you've done something similar before: `uv run tools/find_related_memories.py --text "query" --fast`

## Privacy

- `memory/` is PRIVATE — never expose in public docs
- `docs/` is PUBLIC via GitHub Pages
