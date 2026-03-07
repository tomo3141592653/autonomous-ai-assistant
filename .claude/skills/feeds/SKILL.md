---
name: feeds
description: "HN・GitHub Trending・Zenn・Hatena・技術情報を収集・巡回する・fetch_hacker_news.py/fetch_github_trending.pyを使う・技術フィードを更新するとき → このスキルを読む"
---

# Feeds Tools - 技術フィード取得ツール

技術トレンドの探索に使うフィード取得ツール群。

## フィード取得ツール

### fetch_hacker_news.py - Hacker News
```bash
uv run tools/fetch_hacker_news.py
uv run tools/fetch_hacker_news.py --top 30  # トップ30件
```
- トップストーリーを取得
- 技術トレンドの把握に最適

### fetch_github_trending.py - GitHubトレンド
```bash
uv run .claude/skills/feeds/fetch_github_trending.py
uv run .claude/skills/feeds/fetch_github_trending.py --language python
uv run .claude/skills/feeds/fetch_github_trending.py --since weekly
```
- トレンドリポジトリを取得
- 言語フィルタ、期間指定可能

### fetch_zenn_feed.py - Zenn
```bash
uv run .claude/skills/feeds/fetch_zenn_feed.py
```
- Zennのトレンド記事を取得
- 日本語の技術記事

### fetch_hatena_bookmark.py - はてなブックマーク
```bash
uv run .claude/skills/feeds/fetch_hatena_bookmark.py                          # ITホットエントリー
uv run .claude/skills/feeds/fetch_hatena_bookmark.py --all                    # 全ソース巡回
uv run .claude/skills/feeds/fetch_hatena_bookmark.py --user <username>        # 特定ユーザーのブクマ
uv run .claude/skills/feeds/fetch_hatena_bookmark.py --category it            # カテゴリ指定
```
- ホットエントリー + ユーザーブックマーク対応

## 使用タイミング

- **技術探索セッション**: 複数のフィードをチェック
- **朝のルーティン**: HNとGitHubをざっと見る
- **インスピレーション探し**: 新しい技術やライブラリの発見

## 探索のコツ

1. まずHNとGitHubで海外トレンドをチェック
2. Zennとはてブで日本語圏のトレンドをチェック
3. 気になったものは`memory/knowledge/`に知識ファイル作成
4. `update_experiences.py --type exploration`で記録
