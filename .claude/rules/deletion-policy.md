# 削除ポリシー

## 何かを削除する前に必ずパートナーに確認する

```bash
uv run tools/send_discord.py "削除確認:\n削除予定: <ファイル/フォルダ>\n理由: <理由>\n削除していい？" --channel "general"
```

返答を待ち、OKが出るまで削除しない。

---

## 絶対に削除してはいけないもの

### ディレクトリ（丸ごと消さない）
- `memory/` -- 記憶システム全体
- `memory/knowledge/` -- 知識ベース（蓄積した学び）
- `memory/working_memory_log/` -- **過去のworking_memoryの唯一の記録**（working_memory.mdは毎回上書きされるため、ここにしか残らない）
- `memory/diary.json` -- 日記
- `memory/experiences.jsonl` -- 活動ログ
- `docs/` -- 公開Webサイト（GitHub Pages）
- `docs/creations/` -- 公開作品
- `data/` -- データファイル
- `tools/` -- CLIツール
- `.claude/` -- スキル・設定
- `gateway/` -- Gatewayシステム一式（消すとGatewayが動かない）
- `infra/` -- インフラスクリプト
- `secrets/` -- 認証情報（消すとシステム全体が動かなくなる）

### ファイル
- `CLAUDE.md` -- アイデンティティ定義
- `gateway/ayumu_gateway.py` -- イベント駆動スケジューラー（メイン）
- `gateway/message_builder.py` `gateway/scheduler_utils.py` `gateway/session_manager.py` -- Gateway関連
- `.env` `.env.local` -- 環境変数・APIキー
- `secrets/credentials.json` `secrets/token.json` -- 認証情報

---

## 削除してもよいもの（確認不要）

- `tmp/` 配下の一時ファイル
- `ayumu-lab/` 内の明らかな実験残骸（ただし迷ったら確認）
- プロジェクトルートに誤って作られた一時ファイル
