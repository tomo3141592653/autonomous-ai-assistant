#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["python-dotenv", "google-genai", "numpy"]
# ///
"""
作品エントリを追加するスクリプト

使い方:
    # 基本（自動で関連記憶を検索）
    uv run tools/update_creations.py --id "my-creation" --title "作品名" --description "説明" --category "Interactive" --url "creations/my-creation.html"

    # 関連記憶の自動検索をスキップ
    uv run tools/update_creations.py --id "my-creation" --title "作品名" --description "説明" --category "Interactive" --url "creations/my-creation.html" --no-related

    # 手動で関連記憶を指定
    uv run tools/update_creations.py --id "my-creation" --title "作品名" --description "説明" --category "Interactive" --url "creations/my-creation.html" --related "memory/knowledge/foo.md"

date, numberは自動生成されます。
"""

import json
import argparse
from datetime import datetime
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs"
CREATIONS_FILE = DOCS_DIR / "data" / "all-creations.json"


def add_creation(id: str, title: str, description: str, category: str, url: str, related_memories: list[str] = None, auto_related: bool = True):
    """作品エントリを追加"""
    # 既存のデータを読み込む
    if CREATIONS_FILE.exists():
        with open(CREATIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"creations": [], "total": 0}

    # 重複チェック
    existing_ids = {c["id"] for c in data["creations"]}
    if id in existing_ids:
        print(f"❌ エラー: ID '{id}' は既に存在します")
        return

    # 日付とナンバーを生成
    today = datetime.now().strftime("%Y-%m-%d")
    # 既存のエントリから最大番号を取得（totalキーがない場合も対応）
    existing_numbers = [c.get("number", 0) for c in data["creations"]]
    number = max(existing_numbers, default=0) + 1

    # 関連記憶を自動検索（手動指定がなく、auto_related=Trueの場合）
    found_items = []  # 逆リンク用に保持
    if related_memories is None and auto_related:
        try:
            from memory_linker import find_related_memories
            search_text = f"{title}: {description}"
            # 自分自身のIDを生成（自己リンク防止）
            my_id = f"docs/data/all-creations.json:id:{id}"
            print("🔍 関連記憶を検索中...", flush=True)
            found_items = find_related_memories(search_text, top_n=5, exclude_id=my_id)
            if found_items:
                print(f"\n{'='*50}", flush=True)
                print(f"📎 関連記憶: {len(found_items)}件", flush=True)
                print(f"{'='*50}", flush=True)
                for item in found_items:
                    print(f"  📌 {item['id']}", flush=True)
                    if item.get('reason'):
                        print(f"     理由: {item['reason']}", flush=True)
                print(f"{'='*50}\n", flush=True)
                # オブジェクト形式で保存 (idとreasonを含む)
                related_memories = found_items
        except Exception as e:
            print(f"   ⚠️ 関連記憶検索をスキップ: {e}", flush=True)

    # 新しいエントリを作成
    new_entry = {
        "id": id,
        "title": title,
        "description": description,
        "date": today,
        "category": category,
        "url": url,
        "number": number
    }

    # related_memoriesがあれば追加
    if related_memories:
        new_entry["related_memories"] = related_memories

    # 先頭に追加（新しいものが上）
    data["creations"].insert(0, new_entry)
    data["total"] = number

    # 保存
    with open(CREATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 作品エントリを追加しました: #{number} - {title}")
    print(f"   保存先: {CREATIONS_FILE}")

    # Embedding DBに追加
    try:
        from memory_linker import add_to_embedding_db
        entry_id = f"docs/data/all-creations.json:id:{id}"
        entry_content = f"{title}: {description} (category: {category})"
        if add_to_embedding_db(entry_id, entry_content):
            print(f"🧠 Embedding DBに追加しました", flush=True)
    except Exception as e:
        print(f"   ⚠️ Embedding追加をスキップ: {e}", flush=True)

    # 逆リンクを追加
    if found_items:
        try:
            from memory_linker import add_reverse_links
            source_id = f"docs/data/all-creations.json:id:{id}"
            result = add_reverse_links(source_id, found_items)

            total_updated = len(result["updated_md"]) + len(result["updated_diary"]) + len(result["updated_experiences"]) + len(result.get("updated_creations", [])) + len(result.get("updated_goals", []))
            if total_updated > 0:
                print(f"\n🔄 逆リンクを追加: {total_updated}件", flush=True)
                for md in result["updated_md"]:
                    print(f"   📝 {md}", flush=True)
                for d in result["updated_diary"]:
                    print(f"   📔 {d}", flush=True)
                for e in result["updated_experiences"]:
                    print(f"   📋 {e}", flush=True)
                for c in result.get("updated_creations", []):
                    print(f"   🎨 {c}", flush=True)
                for g in result.get("updated_goals", []):
                    print(f"   🎯 {g}", flush=True)
        except Exception as e:
            print(f"   ⚠️ 逆リンク追加をスキップ: {e}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="作品エントリを追加")
    parser.add_argument("--id", required=True, help="作品ID (URLに使う、例: my-creation)")
    parser.add_argument("--title", required=True, help="作品タイトル")
    parser.add_argument("--description", required=True, help="説明")
    parser.add_argument("--category", required=True, help="カテゴリ (例: Interactive, Game, Tool, Visualization)")
    parser.add_argument("--url", required=True, help="URL (例: creations/my-creation.html)")
    parser.add_argument("--related", help="関連記憶 (カンマ区切り)")
    parser.add_argument("--no-related", action="store_true", help="関連記憶の自動検索をスキップ")

    args = parser.parse_args()

    # 関連記憶をパース
    related_memories = None
    if args.related:
        related_memories = [r.strip() for r in args.related.split(",") if r.strip()]

    # auto_related: --no-relatedがなく、--relatedも指定されていない場合はTrue
    auto_related = not args.no_related and related_memories is None

    add_creation(args.id, args.title, args.description, args.category, args.url, related_memories, auto_related)


if __name__ == "__main__":
    main()
