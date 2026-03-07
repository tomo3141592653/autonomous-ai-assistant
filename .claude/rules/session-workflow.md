# セッションワークフロー

## セッション構成（5セッション/サイクル）

- **Session 1**: New session (no --continue) - 計画立案（カレンダー・タスク確認）
- **Session 2-3**: Continue session (--continue) - 自律探索・作業
- **Session 4**: Continue session (--continue) - **日記セッション**（文脈を保持して日記を書く）
- **Session 5**: New session (no --continue) - **メンテナンスセッション**（新鮮な視点でシステム見直し）

**記録形式**: 「サイクル番号」は使わない。日付 + Session X/5 で記録する。

## Session 1: 計画セッション

新規セッションでカレンダーとタスクを確認、今日〜次のSession 5までの計画を立てる。

**チェック内容**:
1. カレンダー（今後2週間）
2. 現在のタスク（GitHub issues等）
3. パートナーの最近のSNS投稿
4. 予約確認メール

**出力**: 新規タスク候補、既存タスクの更新提案

## Session 4: 日記セッション

--continueで文脈を保持、その日やったことを振り返りながら日記を書ける。

```bash
uv run tools/update_diary.py --title "タイトル" --content "内容"
```

## Session 5: メンテナンスセッション

新規セッションで新鮮な視点でシステム・記憶・フォルダを整理。

**チェック項目**:
1. Embedding再構築
2. working_memory.md整理（古い情報をアーカイブ）
3. todo.md整理
4. 記憶の長期化

詳細は `.claude/skills/maintenance/SKILL.md` 参照。

## セッション終了時の必須作業

1. **日記を書く**（Session 4で）
2. **working_memory.md更新**:
   - Current Session → Recent Sessions（要約して移動）
   - Current Session クリア
   - 週が変わったら → `memory/mid-term/YYYY-MM-WX.md`にアーカイブ
3. **experiences.jsonl更新**:
   ```bash
   uv run tools/update_experiences.py --type [type] --description "説明"
   ```
4. **git commit & push**

## セッション開始時の必須作業

1. `uv run tools/pre_pull_merge.py` - JSON conflictを回避してgit pull
2. `memory/working_memory.md` 読む（「他のAIからの通信」セクション確認）
3. `memory/todo.md` 確認
4. `memory/goals.json` 確認
5. `jq 'sort_by(.datetime) | .[-5:]' memory/diary.json` で最近の日記確認
6. `tail -20 memory/experiences.jsonl` で最近の活動確認
7. **`uv run tools/session_recall.py`** - ベクトル検索で関連記憶を呼び出し
   - working_memory.mdとtodo.mdのコンテキストから自動検索
   - 忘れている重要な記憶を掘り起こす
   - 追加検索: `--extra "今日のテーマ"` でトピック指定可
   - **knowledge系の結果は特に注目**（過去の学びが再利用できる）
