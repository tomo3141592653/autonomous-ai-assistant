# 記憶システム規約

## 記憶の階層

1. **短期記憶** (working_memory.md "Current Session") → 現在のセッション、数時間
2. **中期記憶** → 2層構造:
   - working_memory.md "Recent Sessions" → 過去数日のセッション要約
   - `memory/mid-term/YYYY-MM-WX.md` → 週単位のアーカイブ（永続保存、削除しない）
3. **継続的な情報** (working_memory.md) → セッション終了時も消さない
   - パートナーの現在状態（所在、次の予定）
   - 進行中のプロジェクト情報
4. **長期記憶** (CLAUDE.md、knowledge/) → 重要な学びや永続的な情報

## 記憶の流れ

```
Current Session → 要約 → Recent Sessions → 要約 → mid-term/ → 要約 → knowledge/
```

消したら要約して次の階層に移動。重要な学びはCLAUDE.md/knowledge/へ。

## Knowledge Base 運用ルール

- `memory/knowledge/` にObsidian風Markdownファイルで保存
- **基本的に書いたら更新しない**（小さいファイル粒度）
- タグで管理: `#partner` `#person` `#place` `#tech` `#philosophy` `#milestone` `#tool` `#workflow`
- リンクで関連付け: `[[ファイル名]]`
- フォルダ分けは不要

## 重要な設計思想

1. **セッション開始時に読むファイルに書かれていないことは、すべて忘れると思え**
   - CLAUDE.md、working_memory.md、todo.md、goals.json以外は忘れる前提
   - 重要なことはこれらに書く、または参照リンクを書く

2. **ミスをしたら再発防止のシステム改良を行う**
   - 「気をつける」は不可能、システムで防ぐ
   - 専用ファイル作成、ツール改良、標準出力にリマインダー、CLAUDE.mdに追記

3. **何か行動する前に、似たようなことを過去にしていないか検索する**
   - **まず意味検索**: `uv run tools/find_related_memories.py --text "クエリ" --fast`（ローカルembedding、無料、速い）
   - キーワード検索: `uv run tools/search_memory.py --query "キーワード"`（固有名詞や正確な語句向き）
   - 深い検索: `uv run tools/recall_memory.py --query "質問文"`（LLM RAG、API課金）
   - **grepは最終手段**。意味検索で見つからないときだけ使う

## プライバシー警告

- **memory/** folder is PRIVATE
- **docs/** folder is PUBLIC via GitHub Pages
- セキュリティ問題の詳細を公開ファイルに書かない
- 発見した問題はパートナーに直接報告
