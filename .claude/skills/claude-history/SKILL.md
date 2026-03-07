---
name: claude-history
description: "Claude CLIの過去の会話を検索・以前話した内容を調べる・search_sessions.pyを使う・rate_limit後に記憶を復元する・restore_session_memory.pyを使う → このスキルを読む"
---

# Session スキル

Claude CLIの会話履歴とセッション管理。

## 関連スキル

- `/recall` - 記憶システム全般の検索

---

## 1. セッション検索（search_sessions.py）

### 基本検索

```bash
# テキスト検索
uv run tools/search_sessions.py "検索ワード"

# コンテキスト付き（前後3件表示）
uv run tools/search_sessions.py "検索ワード" -C 3

# 今日の会話
uv run tools/search_sessions.py --today --current

# 統計情報
uv run tools/search_sessions.py --stats
```

### 高度な検索

```bash
# 日付範囲
uv run tools/search_sessions.py "キーワード" --after 2026-01-25

# ツール使用箇所を検索
uv run tools/search_sessions.py --tool Edit --current -C 3 --show-tools

# 正規表現
uv run tools/search_sessions.py "パターン" --regex

# 特定セッションを表示
uv run tools/search_sessions.py --session-id <セッションID>
```

---

## 2. セッションデータの保存場所

### メイン会話履歴（完全版）
```
~/.claude/projects/<project-path>/<session-id>.jsonl
```

### サブエージェント履歴
```
~/.claude/projects/<project-path>/<session-id>/subagents/*.jsonl
```

### 簡易履歴（全セッション要約）
```
~/.claude/history.jsonl
```

---

## 3. 記憶復元（restore_session_memory.py）

rate_limitエラー後に記憶が飛んだ場合：

```bash
# compact以降の全会話を表示
uv run .claude/skills/claude-history/restore_session_memory.py --from-compact

# 最後のN件だけ
uv run .claude/skills/claude-history/restore_session_memory.py --last 100

# 全メッセージ
uv run .claude/skills/claude-history/restore_session_memory.py --all
```

出力をClaudeに読ませることで記憶を復元。

---

## 4. トラブルシューティング

### 問題: rate_limitエラー後に記憶がない

**解決**: `restore_session_memory.py` で復元

---

## 5. 便利なコマンド

```bash
# 最近のセッション一覧
jq -r '[.sessionId, .timestamp] | @tsv' ~/.claude/history.jsonl | sort -k2 -r | head -20

# 特定セッションの最初のメッセージ
head -1 ~/.claude/projects/<path>/<id>.jsonl | jq -r '.snapshot.text'

# compact境界の検出
grep -n "This session is being continued" <session-file>.jsonl
```

---

## 関連ファイル

- `tools/search_sessions.py` - 検索ツール
- `.claude/skills/claude-history/restore_session_memory.py` - 記憶復元ツール
