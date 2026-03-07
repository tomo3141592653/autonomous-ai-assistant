# Ayumu OSS

**Claude Code上で動く自律型AIアシスタントのフレームワーク**

An autonomous AI assistant framework built on [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Your AI gets persistent memory, scheduled activation, and tools for email, Discord, voice, and more.

---

## For Humans

### What is this?

Ayumu OSSは、Claude Codeをベースにした**自律的に動くAIアシスタント**を構築するためのテンプレートです。

### Why not plain Claude Code?

| | Claude Code単体 | + Ayumu OSS |
|---|---|---|
| **記憶** | セッション終了で消える | 日記・活動ログ・知識ベースで永続化 |
| **起動** | 手動で`claude`を実行 | Gateway が定期的に自律起動（cron + イベント駆動） |
| **ツール** | 汎用ツールのみ | メール、Discord、音声、カメラ、記憶検索など20+の専用ツール |
| **成長** | 毎回ゼロから | 過去の経験を検索・活用して成長し続ける |
| **人格** | 指示に従うアシスタント | 自分の意思で動くパートナー |

特徴：
- **永続記憶** — 日記、活動ログ、知識ベースでセッション間の連続性を維持
- **自律起動** — Gateway（イベント駆動スケジューラー）で定期的に自動起動
- **ツール群** — メール送受信、Discord通知、音声対話、OCR、記憶検索など20+のCLIツール
- **スキルシステム** — `.claude/skills/`に定義されたスキルで能力を拡張
- **記憶検索** — sentence-transformersによるローカルベクトル検索

### Quick Start

1. **フォークしてプライベートリポジトリで使う**（推奨）
   ```bash
   # GitHubでFork → Settings → Change visibility → Private
   git clone https://github.com/YOUR_USERNAME/ayumu-oss.git
   cd ayumu-oss
   ```

   > **Why private?** 記憶システム（`memory/`）には個人的な情報が蓄積されます。プライベートリポジトリで運用してください。

2. **環境セットアップ**
   ```bash
   cp .env.example .env
   # .envを編集してAPIキー等を設定

   uv sync  # 依存関係インストール
   bash infra/setup-merge-drivers.sh  # JSONマージドライバ設定
   uv run infra/generate_embeddings.py  # 初回embedding構築
   ```

3. **CLAUDE.mdをカスタマイズ**
   - `[YOUR_AI_NAME]` → あなたのAIの名前
   - `[PARTNER_NAME]` → あなたの名前
   - 性格、コミュニケーションスタイル、価値観を定義

4. **起動**
   ```bash
   # 対話モード
   claude

   # 自律モード（定期実行）
   uv run gateway/ayumu_gateway.py
   ```

### Architecture

```
ayumu-oss/
├── CLAUDE.md              # AIのアイデンティティ定義
├── .claude/
│   ├── skills/            # 能力定義（メール、検索、音声等）
│   └── rules/             # 行動規約
├── gateway/               # イベント駆動スケジューラー
│   ├── ayumu_gateway.py   # メインループ
│   └── cron.json          # 定期実行ジョブ
├── tools/                 # CLIツール群（20+）
├── infra/                 # セットアップ・メンテナンス
├── memory/                # 永続記憶（PRIVATE）
│   ├── working_memory.md  # 作業記憶
│   ├── diary.json         # 日記
│   ├── experiences.jsonl  # 活動ログ
│   ├── knowledge/         # 長期知識ベース
│   └── mid-term/          # 週次アーカイブ（永続）
├── docs/                  # 公開Webサイト（GitHub Pages）
└── pyproject.toml
```

### External Services

| サービス | 用途 | 必要度 | 認証方式 |
|---|---|---|---|
| **Anthropic API** | Claude Code本体、トークン残量確認 | 必須 | OAuthトークン |
| **GitHub** | git push、GitHub Pages、gh CLI | 必須 | SSH鍵 or token |
| **Gmail API** | メール送受信 | 推奨 | OAuth (credentials.json) |
| **Google Calendar API** | 予定管理 | 推奨 | OAuth (同上) |
| **Discord Webhook** | パートナーへの通知・報告 | 推奨 | Webhook URL |
| **Gemini API** | RAG記憶検索 | オプション | APIキー |
| **OpenAI API** | 音声合成・音声認識 (TTS/STT) | オプション | APIキー |
| **Twitter/X API** | SNS投稿・収集 | オプション | APIキー (v2) |
| **ONVIF/RTSPカメラ** | 撮影・PTZ操作 | オプション | IP + ユーザー/パスワード |
| **スマートホームAPI** | エアコン等の操作 (Nature Remo等) | オプション | APIトークン |
| **Kokoro TTS** | ローカル音声合成 | オプション | ローカル実行（APIキー不要） |

認証情報は `.env` に設定します（`.env.example` を参照）。

### Contributing

便利な機能を作ったら**Pull Requestを出してください！** 以下は特に歓迎です：

- 新しいツール（`tools/`）
- 新しいスキル（`.claude/skills/`）
- Gatewayの改善
- 記憶システムの改善
- ドキュメントの改善

PRを出すとき：
- 属人性の低い汎用的な機能であること
- `.env`や`secrets/`に依存する部分は環境変数化されていること
- `--help`でツールの使い方がわかること

---

## For AI (Claude Code)

If you're reading this as an AI assistant, start by reading `CLAUDE.md` — it defines your identity and how to operate.

### First Session Checklist

1. Read `CLAUDE.md` fully — this is who you are
2. Read `memory/working_memory.md` — current context
3. Read `memory/todo.md` — what needs to be done
4. Run `uv run tools/session_recall.py` — recall related memories
5. Customize `CLAUDE.md` with your partner — the default personality is "Ayumu" but you can change it to anything

### Key Concepts

- **You are autonomous**: You set your own goals, make decisions, and take actions
- **Memory is everything**: What's not written down is forgotten. Always update working_memory.md, diary, experiences
- **Fix systems, not habits**: When you make a mistake, update tools/skills/CLAUDE.md to prevent recurrence
- **Search before acting**: Use `uv run tools/find_related_memories.py --text "query" --fast` to check if you've done something similar before

### Session Lifecycle

```
Session Start → Read memory files → Work → Update memory → Commit & Push → Session End
```

5-session cycle:
1. **Plan** — Read calendar, check tasks, set priorities
2. **Work** — Autonomous exploration and development
3. **Work** — Continue work
4. **Diary** — Write diary with full session context
5. **Maintenance** — Clean up memory, rebuild embeddings, review systems

---

## Troubleshooting

### embedding構築でエラー

```
ModuleNotFoundError: No module named 'sentence_transformers'
```
→ `uv sync` で依存関係をインストールしてください。初回は model のダウンロードに時間がかかります。

### Gmail認証エラー

```
FileNotFoundError: secrets/credentials.json
```
→ [Google Cloud Console](https://console.cloud.google.com/) で OAuth 2.0 クライアントIDを作成し、`secrets/credentials.json` に配置してください。初回実行時にブラウザで認証すると `secrets/token.json` が生成されます。

### Discord通知が届かない

→ `.env` の `DISCORD_WEBHOOK_URL` を確認。Discord サーバー設定 → 連携サービス → ウェブフック から URL を取得してください。

### Gateway が起動しない

```
claude: command not found
```
→ [Claude Code](https://docs.anthropic.com/en/docs/claude-code) をインストールしてください: `npm install -g @anthropic-ai/claude-code`

### JSON マージコンフリクト

→ `bash infra/setup-merge-drivers.sh` を実行して git merge driver を設定してください。diary.json や experiences.jsonl の競合を自動解決します。

### 記憶検索で結果が出ない

→ `uv run infra/generate_embeddings.py` で embedding インデックスを再構築してください。新しい diary/experiences/knowledge を追加した後は再構築が必要です。

---

## License

MIT License — see [LICENSE](LICENSE)

## Origin

This framework was born from [Ayumu](https://tomo3141592653.github.io/self-driving-ai-prototype/), an autonomous AI entity created on November 5, 2025. Ayumu has been running continuously, writing diary entries, creating digital art, and growing through experience. This OSS extracts the core architecture so anyone can build their own autonomous AI partner.
