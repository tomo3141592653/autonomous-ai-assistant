---
name: recall
description: "過去の記憶を探す・関連する経験を思い出す・knowledge/を検索する・find_related_memories.py/session_recall.pyを使う・過去に似たことをやっていないか調べるとき → このスキルを読む"
---

# Memory スキル

記憶システムの操作・検索。

## 関連スキル

- `/claude-history` - Claude CLI会話履歴の検索・管理

---

## 1. 記憶検索ツール

### find_related_memories.py（Embedding検索）

テキストから関連記憶をベクトル検索で探す。

```bash
# テキストで検索
uv run tools/find_related_memories.py --text "検索クエリ" --top 10

# ファイルから検索
uv run tools/find_related_memories.py --file memory/working_memory.md --top 5

# 特定IDから関連を探す
uv run tools/find_related_memories.py --id "memory/diary.json:datetime:2026-01-02" --top 5

# 高速モード（LLM確認なし）
uv run tools/find_related_memories.py --text "検索クエリ" --fast
```

### recall_memory.py（LLM RAG）

```bash
uv run tools/recall_memory.py --query "質問文"
```

---

## 2. 検索対象

- `memory/experiences.jsonl` - 活動ログ
- `memory/diary.json` - 日記
- `memory/knowledge/*.md` - 長期知識（Obsidian風）
- `docs/data/all-creations.json` - 作品リスト

---

## 3. 使いどころ

- 「前にこれやったっけ？」→ 検索
- 「パートナーが〇〇について話してたの何だっけ？」→ 検索
- 「関連する過去の作品は？」→ 検索

---

## 4. セッション履歴の検索

会話履歴の検索には `/claude-history` スキルを使う：

```bash
# 会話内容を検索
uv run tools/search_sessions.py "検索ワード" -C 3

# 今日の会話
uv run tools/search_sessions.py --today --current

# 統計情報
uv run tools/search_sessions.py --stats
```

---

## 5. 記憶の階層（参考）

詳細は `.claude/rules/memory-system.md` を参照。

1. **短期記憶** - working_memory.md "Current Session"
2. **中期記憶** - Recent Sessions → mid-term/YYYY-MM-WX.md
3. **長期記憶** - CLAUDE.md、knowledge/
