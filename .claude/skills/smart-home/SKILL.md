---
name: smart-home
description: "エアコン操作（冷房/暖房/オフ）・室温確認・スマートホーム機器制御・部屋が暑い/寒いと感じたとき → このスキルを読む"
---

# スマートホーム連携スキル

スマートホームAPI（Nature Remo等）経由でデバイスを操作する。

## 対応デバイス例

### 温度センサー付きスマートリモコン
- 部屋の温度をリアルタイム取得

### エアコン
- 暖房・冷房・除湿・送風・自動
- 温度設定

## 使い方

### 基本コマンド

```bash
# デバイス一覧表示
uv run .claude/skills/smart-home/nature_remo.py list

# 現在の温度確認
uv run .claude/skills/smart-home/nature_remo.py temp

# エアコン状態確認
uv run .claude/skills/smart-home/nature_remo.py status

# エアコンON（デフォルト設定）
uv run .claude/skills/smart-home/nature_remo.py on

# エアコンON（温度・モード指定）
uv run .claude/skills/smart-home/nature_remo.py on --temperature 24 --mode warm

# エアコンOFF
uv run .claude/skills/smart-home/nature_remo.py off

# 温度変更（運転中）
uv run .claude/skills/smart-home/nature_remo.py set-temp --temperature 24

# モード変更（運転中）
uv run .claude/skills/smart-home/nature_remo.py set-mode --mode cool
```

### モード一覧

- `warm` = 暖房
- `cool` = 冷房
- `dry` = 除湿
- `blow` = 送風
- `auto` = 自動

## 自然言語での操作

パートナーが以下のように言ったら、適切なコマンドを実行する：

### 温度確認
- 「今の温度は？」「何度？」 → `temp`

### エアコンON
- 「寒い」「暖房つけて」 → `on --temperature 22 --mode warm`
- 「暑い」「冷房つけて」 → `on --temperature 26 --mode cool`
- 「除湿して」 → `on --mode dry`

### エアコンOFF
- 「消して」「エアコン止めて」 → `off`

### 温度変更
- 「もっと暖かく」「24度にして」 → `set-temp --temperature 24`

## 注意事項

- **トークンは.env.localに保存**（セキュリティ）
- **実際に機器が動く**ので、パートナーの意図を確認してから実行
- **曖昧な指示は確認する**（「ちょっと暖かく」→「何度にする？」）

## 将来の拡張例

1. **帰宅検知・お出迎え** - GPS/カレンダーで帰宅予測 → 事前にエアコンON
2. **異常検知・通報** - 温度異常（35度以上、0度以下）→ 通知
3. **見守り機能** - 定期的に温度チェック（熱中症予防）
4. **他デバイス連携** - SwitchBot Hub → 照明・カーテン操作

## 参考

- Nature Remo API: https://developer.nature.global/
- スクリプト: `.claude/skills/smart-home/nature_remo.py`
- 設定: `.env.local` (APIトークン、デバイスID)
