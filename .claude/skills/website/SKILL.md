---
name: website
description: "Webサイト更新・発表資料作成・作品公開・ページ追加・フォルダ構成確認 → 必ずこのスキルを読んでから作業する"
---

# Website System - GitHub Pages管理

AIエージェントのWebサイト構成と作品公開の手順。

## GitHub Pages（静的サイト）

**URL**: <!-- https://<user>.github.io/<repo>/ -->

| ページ/フォルダ | 内容 |
|--------|------|
| index.html | トップページ、ナビゲーション（**新コンテンツ追加時は必ず更新**） |
| diary.html | 日記（data/diary.jsonから動的読み込み） |
| gallery.html | 全作品ギャラリー |
| **presentations/** | **発表資料**（スライド等） |
| creations/ | 公開作品 |
| articles/ | 技術ブログ |

### presentations/ の命名規則
- **発表資料は必ず `docs/presentations/` に置く**
- 複数ファイルある場合はフォルダ形式: `presentations/topic-YYYYMMDD/`
- 単一ファイルは: `presentations/presentation_YYYYMMDD.html`
- 追加したら `index.html` の Presentations セクションにも追記すること

## Vercel（動的サイト・オプション）

LLM APIを使う動的ページが必要な場合はVercelを検討。

**セキュリティ対策（必須）**:
- **robots.txt**: クローラーをブロック（無限巡回でAPI課金爆発を防ぐ）
- **なぞなぞ認証**: 人間しか答えられない質問で認証
- **レートリミット**: chatbot等は必須（IPごとに1時間N回まで）

## 作品公開の手順

1. `ayumu-lab/web/`で実験・開発
2. 完成したら`docs/creations/`に移動
3. **移動してからリンクを共有**（ayumu-labは公開されない）
4. `docs/data/all-creations.json`に登録
5. git commit & push

**URL例**:
- 実験場所のURLは外部からアクセスできない → 404
- `docs/`配下のURLのみ公開される

## 重要なルール

- **Never expose memory/ files directly** - プライベート情報を含む
- **diary.json sync**: `uv run tools/update_diary.py --title "タイトル" --content "内容"`
