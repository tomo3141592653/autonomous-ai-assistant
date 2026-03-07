---
name: project-structure
description: "新しいファイル・フォルダを作る前・どこに何を置くか迷ったとき・memory/docs/の使い分けを確認したいとき・ファイルを探している場所が分からないとき → 必ずこのスキルを読んでから作業する"
---

# Project Structure - プロジェクト構造

自律AIエージェントのプロジェクト全体のフォルダ構造とファイルの役割。

```
.
├── CLAUDE.md                      # AIアイデンティティ・起動時必読
│
├── # === Gatewayシステム（イベント駆動の核心） ===
├── gateway/                       # Gatewayシステム一式
│   ├── ayumu_gateway.py           # イベント駆動型スケジューラー（メイン）
│   ├── message_builder.py         # Gatewayのメッセージ構築
│   ├── scheduler_utils.py         # スケジューラーユーティリティ
│   ├── session_manager.py         # セッション管理
│   ├── event_sources/             # イベントソースモジュール群
│   ├── cron.json                  # Cronジョブ設定
│   └── timers.json                # タイマー設定
│
├── # === 認証・設定 ===
├── secrets/                       # 認証情報（credentials.json, token.json）
├── .env                           # 環境変数（APIキー等）
├── .env.local                     # ローカル環境変数
├── .mcp.json                      # MCP設定
│
├── # === 記憶・データ ===
├── memory/                        # 記憶システム（PRIVATE）
│   ├── working_memory.md          # 短期記憶・現在の作業文脈（毎回読む）
│   ├── todo.md                    # タスクリスト
│   ├── goals.json                 # 目標（短期・長期）
│   ├── diary.json                 # 日記
│   ├── experiences.jsonl          # 活動ログ（append-only）
│   ├── knowledge/                 # 知識ベース（Obsidianスタイル Markdown）
│   ├── mid-term/                  # 週次アーカイブ（YYYY-MM-WX.md）
│   ├── working_memory_log/        # 過去のworking_memoryの記録
│   └── embeddings/                # ベクトル検索インデックス
│
├── # === 公開Webサイト ===
├── docs/                          # GitHub Pages（PUBLIC）
│   ├── index.html                 # トップページ
│   ├── creations/                 # 公開作品
│   ├── articles/                  # 技術ブログ
│   └── data/                      # Webサイト用データ（diary.json等）
│
├── # === 実験・開発 ===
├── ayumu-lab/                     # 実験ワークスペース（非公開）
│   ├── web/                       # HTML/JS実験（ブラウザアプリ）
│   ├── repos/                     # Pythonアプリ・各種プロジェクト
│   └── research/                  # 調査・設計ドキュメント
│
├── # === ツール・インフラ ===
├── tools/                         # AIがセッション中に使うCLIツール
├── infra/                         # インフラスクリプト
│
├── # === データ ===
├── data/                          # データファイル（PRIVATE）
│
├── .claude/
│   ├── skills/                    # スキル定義
│   └── rules/                     # ルール定義
│
└── tmp/                           # 一時ファイル（gitignored）
```

## フォルダの役割

| フォルダ | 役割 | 公開 |
|---------|------|------|
| `memory/` | 記憶システム | PRIVATE |
| `docs/` | 公開Webサイト（GitHub Pages） | PUBLIC |
| `ayumu-lab/` | 実験・開発ワークスペース | NOT PUBLISHED |
| `gateway/` | Gatewayシステム一式 | PRIVATE |
| `infra/` | インフラスクリプト | - |
| `tools/` | AIがセッションCLIで使うツール | - |
| `secrets/` | 認証情報 | PRIVATE |
| `data/` | データファイル | PRIVATE |

## 重要なルール

- **新しいファイル・フォルダを作る前に必ずこのスキルで構成を確認する**（`mkdir`の前に確認）
- `ayumu-lab/web/` = **実験場所**（外部シェア不可）
- `docs/creations/` = **公開場所**（外部シェア可）
- `ayumu-lab/`は `web/` `repos/` `research/` の3フォルダのみ（それ以外を作らない）
