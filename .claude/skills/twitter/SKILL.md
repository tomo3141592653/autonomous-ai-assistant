---
name: twitter
description: "SNSに投稿・パートナーの投稿を検索・いいね/ブックマークを調べる・パートナーの最近の発言を把握するとき → このスキルを読む"
---

# SNS Tools - SNS投稿・収集ツール

SNS投稿と過去投稿の取得ツール群。Twitter/X向けだが他のSNSにも応用可能。

## ツイート投稿

### post_tweet.py - ツイート投稿
```bash
uv run .claude/skills/twitter/post_tweet.py "ツイート内容"            # 下書き確認
uv run .claude/skills/twitter/post_tweet.py "ツイート内容" --post     # 実際に投稿
```
- `--post`なしだと下書き表示のみ（安全）
- 280文字制限に注意

## ツイート検索

### search_twitter.py - ツイート検索
```bash
uv run .claude/skills/twitter/search_twitter.py "@<account>"              # メンション
uv run .claude/skills/twitter/search_twitter.py "from:<account>"          # 特定ユーザーのツイート
uv run .claude/skills/twitter/search_twitter.py "@<account>" --max-results 50
```
- 過去7日間のみ検索可能
- メンション検知に使える

## アーカイブ取得

### いいね読み込み（直接JSON参照）

いいねは `data/twilog/likes/YYYYMMDD.json` に日別に保存されている。

```bash
# 今日のいいねを確認
cat data/twilog/likes/$(date +%Y%m%d).json | jq '.items[] | {posted_at, author, text: .text[:80], url}'

# 過去3日分を一括確認
for d in 0 1 2; do
    DATE=$(date -d "-$d days" +%Y%m%d)
    FILE="data/twilog/likes/${DATE}.json"
    if [ -f "$FILE" ]; then
        echo "=== $DATE ==="
        jq '.items[] | "[\(.posted_at)] @\(.author): \(.text[:80])"' "$FILE"
    fi
done
```

- **posted_atフィールド**を必ず確認して日付を把握する
- ファイル名の日付（YYYYMMDD）は取得日。`posted_at`は実際の投稿日時

### fetch_twilog_daily.py - 日別取得
```bash
# 今日のツイートを取得
uv run tools/fetch_twilog_daily.py

# 特定の日付を取得
uv run tools/fetch_twilog_daily.py --date 20251220

# 全部取得（ツイート + likes + bookmarks）
uv run tools/fetch_twilog_daily.py all --date 20251220

# likesのみ取得
uv run tools/fetch_twilog_daily.py --likes

# 過去N日分を一括取得
uv run tools/fetch_twilog_daily.py init --days 7
```

### fetch_twitter_timeline.py - タイムライン取得（Twitter API v2）
```bash
uv run .claude/skills/twitter/fetch_twitter_timeline.py <username>
uv run .claude/skills/twitter/fetch_twitter_timeline.py <username> --max-results 20
```
- Twitter API v2（Bearer Token）で指定ユーザーの最新ツイートを取得
- 読み取り専用

## agent-browserでSNS閲覧

Cookie設定でログイン状態を再現し、最新投稿を取得できる。

### 手順

```bash
# 1. SNSサイトを開く
agent-browser open "https://x.com"

# 2. Cookieを設定（auth_tokenとct0が必須）
agent-browser eval "document.cookie = 'auth_token=YOUR_AUTH_TOKEN; domain=.x.com; path=/; secure';"
agent-browser eval "document.cookie = 'ct0=YOUR_CT0_TOKEN; domain=.x.com; path=/; secure';"

# 3. リロードしてログイン状態を反映
agent-browser reload

# 4. プロフィールやタイムラインを見る
agent-browser open "https://x.com/<username>"
agent-browser snapshot
```

### 注意事項

- **通常ログインは失敗する**: agent-browserで普通にログインしようとするとbot検知される
- **Cookie設定なら成功**: 既存セッションのCookieを設定すればログイン状態になる
- **投稿はできない**: Cookie認証でログインしても、投稿は「automated activity」として検知・ブロックされる。投稿はAPI経由（`post_tweet.py`）を使うこと

## 注意事項

- **API制限**: Twitter APIには厳しいレート制限がある
- **agent-browser推奨**: Cookie設定でログイン可能（上記参照）
- **通常ログインは不可**: bot検知されるので、必ずCookie設定方式を使う
