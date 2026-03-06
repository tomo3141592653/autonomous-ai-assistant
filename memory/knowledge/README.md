# Knowledge Base

This directory contains long-term knowledge files. Each file focuses on one topic.

## Structure

- One `.md` file per topic
- Small, focused files (easier to search, less git conflicts)
- Use descriptive filenames: `python-async-patterns.md`, `partner-preferences.md`

## Examples

- `partner-preferences.md` — Partner's habits, interests, communication style
- `python-tips.md` — Useful Python patterns discovered over time
- `project-notes.md` — Important context about ongoing projects
- `api-integrations.md` — External APIs and how to use them

## How to Use

Create new knowledge files directly:

```bash
# Create a new knowledge file
cat > memory/knowledge/new-topic.md << 'EOF'
# Topic Title

Key information here.
EOF
```

Or use the semantic search to find existing knowledge:

```bash
python tools/find_related_memories.py --text "what do I know about Python?"
```
