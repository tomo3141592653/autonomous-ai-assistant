---
name: maintenance
description: "Session 5のメンテナンス（記憶整理・統計更新・長期記憶化・embedding再構築・working_memory整理・todo整理）をするとき → このスキルを最初に読む"
---

# メンテナンススキル

Session 5（メンテナンスセッション）で実行するタスク。

**注意**: テスト、セキュリティチェック等はcronで自動化できる。`gateway/cron.json` で設定。

---

## Session 5 チェックリスト

### 1. Embedding再構築
```bash
uv run infra/generate_embeddings.py
```
記憶検索の精度に直結。knowledgeが増えたらインデックス更新が必要。

### 2. working_memory.md整理（最重要）

**目標**: 500行以下

**サイズ確認**:
```bash
wc -l memory/working_memory.md && wc -l memory/todo.md
```

**Recent Sessions削減**
- **3日分だけ残す**（今日、昨日、一昨日）
- それ以前は `memory/mid-term/YYYY-MM-WX.md` に要約して移動

**週間スケジュール更新**
- 古い日付を削除（1週間以上前）

**継続的な情報の整理**
- 1ヶ月以上古い情報は削除
- 完了したタスクは削除

### 3. todo.md整理

**目標**: 150行以下、アクティブなタスクのみ

- 完了済み（`[x]`）→ Archivedに移動 or 削除
- 不要タスク → 削除
- 重要タスクを上に
- 曖昧なタスクを具体化

### 4. 記憶の長期化

Recent Sessionsを見て、重要な学びを移動:
- 技術的な学び → `memory/knowledge/topic-name.md`
- システム変更 → `CLAUDE.md`
- 新しい人物情報 → `memory/knowledge/person-name.md`

### 5. フォルダ構造監査

プロジェクトルートやツール群のフォルダ構造を確認し、散らかっていないかチェック。
- 一時ファイルの削除
- 不要な実験ファイルの整理
- working_memory.md 500行超・todo.md 150行超の検出

### 6. コミット＆プッシュ
```bash
git add -A
git commit -m "YYYY-MM-DD Session 5/5: メンテナンス完了"
git push
```

---

## cronで自動化できるタスク例

| cron名 | 時刻 | 内容 |
|---|---|---|
| daily-tests | 3:00 | pytest実行 |
| daily-security | 3:30 | セキュリティチェック |
| daily-cleanup | 5:00 | フォルダ整理 |
| morning-info | 8:30 | 情報収集 |

設定: `gateway/cron.json`

---

## メンテナンスのメンテナンス

Session 5自体が機能しているか、毎回確認：

1. **このSKILL.mdは読まれているか？** → gateway/message_builder.pyに指示があるか
2. **todo.md/goals.jsonは毎回読まれているか？** → CLAUDE.mdに明記されているか
3. **cronジョブは正常に動いているか？** → 直近のcron実行ログを確認
4. 「時間厳しい」を言い訳にしない
