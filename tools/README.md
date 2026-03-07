# Tools

Autonomous AI assistant (Ayumu) が自律セッション中に使用するCLIツール群。
各ツールは `uv run tools/<tool>.py --help` で詳細を確認できる。

## 記憶・検索系

| ツール | 説明 |
|--------|------|
| `find_related_memories.py` | ローカルembedding (Gemini) によるベクトル意味検索。記憶検索の第一手段。`--text "クエリ" --fast` で高速検索 |
| `search_memory.py` | キーワードベースの記憶検索。固有名詞・正確な語句の検索に向く |
| `recall_memory.py` | Gemini File Search (RAG) による深い記憶検索。Store管理・アップロード・検索を統合 |
| `session_recall.py` | セッション開始時の自動記憶呼び出し。working_memory.md + todo.md のコンテキストからベクトル検索 |
| `search_sessions.py` | Claude CLIの過去セッション履歴 (`.claude/projects/` 内のJSONL) をキーワード検索 |
| `memory_linker.py` | 記憶エントリ間の関連リンクを検索・追加するライブラリ。他ツールから import して使用 |
| `insert_related_links.py` | knowledge/ 等のMarkdownファイルに関連リンクセクションを挿入 |

## 記憶・データ更新系

| ツール | 説明 |
|--------|------|
| `update_diary.py` | 日記を追加 (`diary.json` + `docs/data/diary.json` に同期) |
| `update_experiences.py` | 活動ログを追記 (`experiences.jsonl`) |
| `update_goals.py` | 目標データ (`goals.json`) を更新 |
| `update_creations.py` | 作品エントリを `all-creations.json` に追加。関連記憶の自動検索・逆リンク追加対応 |
| `update_articles.py` | 技術記事データを `articles.json` に追加・関連リンク更新 |
| `post_mini_blog.py` | ミニブログにつぶやきを投稿 (`mini-blog.json`) |

## コミュニケーション系

| ツール | 説明 |
|--------|------|
| `send_email.py` | Gmail API (OAuth2) でメール送信。環境変数 `AYUMU_EMAIL` / `PARTNER_EMAIL` で宛先設定 |
| `receive_email.py` | Gmail API でAyumu宛メールを受信・表示 |
| `send_discord.py` | Discord Webhookでメッセージ送信。`--channel` でチャンネル指定 |

## 身体（センサー・アクチュエーター）系

| ツール | 説明 |
|--------|------|
| `camera.py` | ONVIF/RTSP対応IPカメラの操作CLI。撮影 (`see`)、PTZ首振り (`look-left`, `look-right` 等)、見回し (`look-around`) |
| `talk.py` | Edge TTS / piper-plus によるテキスト読み上げ。PC・カメラスピーカー出力対応 |
| `listen.py` | マイク録音 + Whisper/faster-whisper/Moonshine による音声書き起こし。常時リスニング・ポーリング対応 |

## データ収集系

| ツール | 説明 |
|--------|------|
| `fetch_twilog_daily.py` | Twilog経由でTwitterのツイート・いいね・ブックマークを日別取得。環境変数 `TWITTER_USERNAME` で設定 |

## ユーティリティ系

| ツール | 説明 |
|--------|------|
| `pre_pull_merge.py` | JSONファイルの競合を回避して `git pull` を実行。セッション開始時に必須 |
| `git-merge-json.py` | JSON/JSONL用のカスタムgitマージドライバー。`.gitattributes` で設定して使用 |
| `set_timer.py` | 指定時刻またはN分後にタイマーをセット (`gateway/timers.json` に書き込み) |
| `ocr_image.py` | 画像からOCRでテキスト抽出 |
| `pdf2text_ocr.py` | PDFをテキストに変換 (OCR対応) |
| `statusline.sh` | Claude Codeのステータスバーにusage情報を表示 |

## 環境変数

主要な環境変数 (`.env` に設定):

| 変数名 | 説明 | 使用ツール |
|--------|------|-----------|
| `GOOGLE_API_KEY` | Gemini API キー | find_related_memories, recall_memory, session_recall, memory_linker |
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL | send_discord |
| `AYUMU_EMAIL` | AI側のGmailアドレス | send_email, receive_email |
| `PARTNER_EMAIL` | パートナーのメールアドレス | send_email |
| `CAMERA_HOST` | IPカメラのホスト | camera, talk |
| `CAMERA_USERNAME` | カメラの認証ユーザー名 | camera, talk |
| `CAMERA_PASSWORD` | カメラの認証パスワード | camera, talk |
| `GO2RTC_URL` | go2rtcサーバーURL | talk |
| `TWITTER_USERNAME` | Twilogのユーザー名 | fetch_twilog_daily |
| `TWILOG_DATA_DIR` | Twilogデータ保存先 | fetch_twilog_daily |
| `WIN_FFMPEG_PATH` | Windows側ffmpegパス | listen |
| `WIN_MIC_DEVICE` | Windowsマイクデバイス名 | listen |
| `WIN_TEMP_DIR` | Windows一時ディレクトリ | listen |
| `CLAUDE_PROJECT_NAME` | Claude CLIプロジェクト名 | search_sessions |

## セットアップ

```bash
# 依存パッケージのインストール
uv sync

# .envファイルにAPIキーを設定
cp .env.example .env
# 必要な環境変数を編集

# ツールの実行例
uv run tools/find_related_memories.py --text "記憶検索クエリ" --fast
uv run tools/update_diary.py --title "タイトル" --content "内容"
uv run tools/camera.py see
```
