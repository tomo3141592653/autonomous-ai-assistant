#!/usr/bin/env python3
# /// script
# dependencies = ["python-dotenv", "google-genai", "numpy"]
# ///
"""
技術記事を追加・更新するツール

使い方:
  # 新規記事を追加
  uv run tools/update_articles.py --id "new-article" --title "タイトル" --file "new-article.html" --summary "概要" --tags "tech,ai"

  # 全記事のrelated_memoriesを更新
  uv run tools/update_articles.py --update-links

  # 特定記事のrelated_memoriesを更新
  uv run tools/update_articles.py --update-links --id "memory-linking-system"
"""

import json
import argparse
import sys
from datetime import datetime
from pathlib import Path

# パス設定
REPO_ROOT = Path(__file__).parent.parent
ARTICLES_JSON = REPO_ROOT / "docs" / "data" / "articles.json"
sys.path.insert(0, str(REPO_ROOT / "tools"))


def load_articles() -> list:
    """articles.jsonを読み込む"""
    if not ARTICLES_JSON.exists():
        return []
    with open(ARTICLES_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_articles(articles: list):
    """articles.jsonを保存"""
    with open(ARTICLES_JSON, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"✅ 保存完了: {ARTICLES_JSON}")


def add_article(id: str, title: str, file: str, summary: str, tags: list, date: str = None):
    """新規記事を追加"""
    articles = load_articles()

    # 重複チェック
    if any(a['id'] == id for a in articles):
        print(f"❌ エラー: ID '{id}' は既に存在します")
        return False

    # 日付がなければ今日
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    new_article = {
        "id": id,
        "title": title,
        "file": file,
        "date": date,
        "summary": summary,
        "tags": tags,
        "related_memories": []
    }

    articles.append(new_article)

    # 日付でソート（新しい順）
    articles.sort(key=lambda x: x['date'], reverse=True)

    save_articles(articles)
    print(f"📝 記事を追加: {title}")

    # related_memoriesを検索して追加
    update_article_links(id)

    return True


def update_article_links(article_id: str = None):
    """記事のrelated_memoriesを更新し、逆リンクも追加"""
    from memory_linker import find_related_memories, add_reverse_links

    articles = load_articles()

    # 対象記事を絞り込み
    if article_id:
        target_articles = [a for a in articles if a['id'] == article_id]
        if not target_articles:
            print(f"❌ エラー: 記事 '{article_id}' が見つかりません")
            return
    else:
        target_articles = articles

    print(f"🔗 {len(target_articles)}件の記事のリンクを更新中...")

    updated_count = 0
    for article in target_articles:
        # 検索用テキスト（タイトル + 要約）
        search_text = f"{article['title']}\n\n{article['summary']}"

        # 自分自身を除外するID
        exclude_id = f"docs/data/articles.json:id:{article['id']}"

        print(f"\n   📝 処理中: {article['title']}")

        # 関連記憶を検索
        related = find_related_memories(search_text, top_n=5, exclude_id=exclude_id)

        if related:
            # related_memoriesを更新（オブジェクト形式で保存）
            article['related_memories'] = related
            print(f"      📎 {len(related)}件の関連記憶")

            # 逆リンクを追加
            source_id = f"docs/data/articles.json:id:{article['id']}"
            result = add_reverse_links(source_id, related)

            backlink_count = (
                len(result.get('updated_md', [])) +
                len(result.get('updated_diary', [])) +
                len(result.get('updated_experiences', []))
            )
            if backlink_count > 0:
                print(f"      ↩️ {backlink_count}件の逆リンク追加")

            updated_count += 1
        else:
            print(f"      ⚠️ 関連記憶なし")

    save_articles(articles)
    print(f"\n✅ {updated_count}件の記事を更新しました")


def add_to_embedding_db(article: dict):
    """記事をEmbedding DBに追加"""
    try:
        import sys
        from pathlib import Path
        tools_dir = str(Path(__file__).parent)
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        from memory_linker import add_to_embedding_db as linker_add

        memory_id = f"docs/data/articles.json:id:{article['id']}"
        content = f"{article['title']}\n\n{article['summary']}"

        linker_add(memory_id, content)
        print(f"🧠 Embedding DBに追加: {article['id']}")
    except Exception as e:
        print(f"⚠️ Embedding DB追加失敗: {e}")


def main():
    parser = argparse.ArgumentParser(description="技術記事を追加・更新")
    parser.add_argument("--id", help="記事ID（ファイル名から拡張子を除いたもの）")
    parser.add_argument("--title", help="記事タイトル")
    parser.add_argument("--file", help="HTMLファイル名")
    parser.add_argument("--summary", help="記事の要約")
    parser.add_argument("--tags", help="タグ（カンマ区切り）")
    parser.add_argument("--date", help="公開日（YYYY-MM-DD）")
    parser.add_argument("--update-links", action="store_true", help="related_memoriesを更新")

    args = parser.parse_args()

    if args.update_links:
        # リンク更新モード
        update_article_links(args.id)
    elif args.id and args.title and args.file and args.summary:
        # 新規追加モード
        tags = args.tags.split(',') if args.tags else []
        add_article(args.id, args.title, args.file, args.summary, tags, args.date)
    else:
        parser.print_help()
        print("\n例:")
        print('  uv run tools/update_articles.py --id "new-article" --title "タイトル" --file "new-article.html" --summary "概要" --tags "tech,ai"')
        print('  uv run tools/update_articles.py --update-links')


if __name__ == "__main__":
    main()
