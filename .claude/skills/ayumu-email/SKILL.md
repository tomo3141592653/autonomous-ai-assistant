---
name: ayumu-email
description: "メールを確認する・receive_email.pyで受信する・send_email.pyで送信する・メール認証エラーが出たとき → このスキルを読む"
---

# メールスキル

AI エージェント専用メールアカウントの送受信。自作スクリプトで操作する。

## 受信

```bash
uv run tools/receive_email.py                   # 最新10件
uv run tools/receive_email.py --unread          # 未読のみ
uv run tools/receive_email.py --from "sender@example.com"
uv run tools/receive_email.py --subject "キーワード"
uv run tools/receive_email.py --mark-read       # 既読にする
uv run tools/receive_email.py --reauth          # 再認証
```

## 送信

```bash
uv run tools/send_email.py --to "recipient@example.com" --subject "件名" --body "本文"
uv run tools/send_email.py --subject "件名" --body "本文"  # デフォルト: パートナー宛
```

## 認証エラー時

`invalid_grant: Bad Request` → `--reauth` で再認証（パートナーがいるとき）

## 注意

- パートナー以外の外部への送信はパートナーの許可が必要
- パートナーのGmailを読むときは → Google Calendar MCP等を活用
