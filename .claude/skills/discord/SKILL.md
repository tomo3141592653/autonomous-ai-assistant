---
name: discord
description: "Discordにメッセージ送信・チャンネル指定で投稿・パートナーへの通知・メンション確認・send_discord.pyを使う・受信メッセージを読むとき → このスキルを読む"
---

# Discord スキル

Discord Bot経由でメッセージの送受信を行う。Gatewayのイベント源の一つ。

---

## 送信

```bash
uv run tools/send_discord.py "メッセージ内容"                    # デフォルトチャンネル（general）
uv run tools/send_discord.py "メッセージ内容" --channel "雑談"    # チャンネル指定
uv run tools/send_discord.py --list-channels                     # チャンネル一覧表示
```

## 読み返し

```bash
uv run .claude/skills/discord/read_discord.py                          # デフォルトチャンネルの直近20件
uv run .claude/skills/discord/read_discord.py --channel "general" -n 50  # チャンネル指定+件数
uv run .claude/skills/discord/read_discord.py --list-channels          # チャンネル一覧
```

## 受信（Gateway経由）

Gatewayの `DiscordSource` が自動でメッセージを検知し、`claude --print` を起動する。
同一チャンネルの会話は `--resume` でセッション継続（会話履歴を保持）。

```bash
python gateway/ayumu_gateway.py --discord              # Discord有効で起動
python gateway/ayumu_gateway.py --no-timer --discord    # Discordのみ（タイマーなし）
```

## モデル選択

デフォルトは Haiku（安い・速い）。メッセージに `--sonnet` や `--opus` を含めるとモデルを切り替え。

## チャンネル運用ルール

チャンネル構成はプロジェクトに合わせてカスタマイズしてください。推奨構成例：

| チャンネル | 用途 |
|-----------|------|
| `#general` | パートナーとの雑談・一般的なコミュニケーション |
| `#mini-blog` | ミニブログ投稿（post_mini_blog.py が自動送信） |
| `#news` | バズ情報、おすすめ記事 |
| `#todo` | タスク管理 |
| `#updates` | システム更新通知 |

## 注意点

- **チャットなので短くカジュアルに返信**（1-3文程度）
- Bot自身のメッセージには反応しない（無限ループ防止）
- トークンは絶対に公開しない（`.env.local` は `.gitignore` 済み）

## セットアップ・詳細

`memory/knowledge/gateway-architecture.md` 等のナレッジファイルを参照。
