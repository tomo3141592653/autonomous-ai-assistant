---
name: life
description: "パートナーのライフイベント管理・GitHub issueでタスク管理・issue提案・カレンダー/メール/SNSから新issue候補を見つけるとき → このスキルを読む"
---

# Life スキル

パートナーの人生をGitHubで管理するシステム。情報収集→issue管理の一連の流れ。

## 関連スキル

- `/calendar` - Google Calendar確認（MCP Google Calendar）

## リポジトリ

- **URL**: <!-- https://github.com/<user>/life (private) -->
- **ローカル**: `<partner-repos>/life/`

---

## 1. 情報収集（Session 1で実行）

### チェック項目

**カレンダー**（MCP Google Calendar）:
```
mcp__claude_ai_Google_Calendar__gcal_list_events(
  calendarId="<partner-email>",
  timeMin="<today>T00:00:00",
  timeMax="<+14days>T23:59:59",
  timeZone="Asia/Tokyo"
)
```

**現在のissues**:
```bash
cd <partner-repos>/life && gh issue list --state open
```

**SNS投稿**:
```bash
# パートナーの最近の投稿を確認
cat data/sns/<today>.json 2>/dev/null | jq -r '.[]|.text'
```

**メール（予約系）**（MCP Gmail）:
```
mcp__claude_ai_Gmail__gmail_search_messages(
  q="from:noreply (予約 OR confirmation)",
  maxResults=5
)
```

---

## 2. Issue操作

### 基本コマンド

```bash
gh repo set-default <user>/life

# 一覧
gh issue list

# 作成
gh issue create --title "タイトル" --body "内容" --label "ラベル"

# 更新
gh issue edit <番号> --body "新しい内容"

# 閉じる
gh issue close <番号>
```

### ラベル（カスタマイズ推奨）

| ラベル | 用途 |
|--------|------|
| 旅行 | 旅行計画・準備 |
| イベント | 展覧会、ライブ、勉強会 |
| 買い物 | 買いたいもの |
| 健康 | 病院、健康診断 |
| 手続き | 役所、契約、更新 |
| 読書 | 読みたい本 |
| 仕事 | 仕事関連 |

---

## 3. issue候補の判定

**SNS投稿から**:
- 「〇〇行く」「〇〇行きたい」→ 旅行/イベント
- 「〇〇買う」「〇〇欲しい」→ 買い物

**カレンダーから**:
- 新しい予定 → issue化を提案
- 準備が必要な予定（旅行、発表など）

**メールから**:
- 新しい予約確認 → 対応するissueがなければ作成提案

---

## 出力フォーマット

```markdown
## カレンダー（今後2週間）
- 1/17: 旅行
- 1/24-25: 出張

## 現在のlife issues
- #1: 病院 (1/27)
- #5: 旅行計画 (2/7-15)

## 新規issue候補
1. **[提案] 〇〇展覧会** (イベント)
   - 根拠: SNSでいいねした投稿

## 既存issueの更新提案
- #5 旅行: 新しいホテル予約メールあり
```

---

## プライバシー注意

- 他の人の名前・予定は出力に含めない
- 「〇〇さんと会う」→「予定あり」程度に抽象化
- lifeリポジトリはprivate（他人の情報含むため）
- 公開ファイルには書かない
