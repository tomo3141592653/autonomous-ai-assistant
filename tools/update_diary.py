#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["python-dotenv", "google-genai", "numpy"]
# ///
"""
日記エントリを追加するスクリプト

使い方:
    # 短いコンテンツの場合（自動で関連記憶を検索）
    uv run tools/update_diary.py --title "タイトル" --content "内容"

    # 長いコンテンツや特殊文字を含む場合（標準入力から）
    echo "長い内容..." | uv run tools/update_diary.py --title "タイトル" --stdin

    # ファイルから読み込む場合
    uv run tools/update_diary.py --title "タイトル" --file content.txt

    # 関連記憶の自動検索をスキップ
    uv run tools/update_diary.py --title "タイトル" --content "内容" --no-related

    # 手動で関連記憶を指定（自動検索を上書き）
    uv run tools/update_diary.py --title "タイトル" --content "内容" --related "memory/knowledge/foo.md"

datetimeとtime_periodは自動生成されます（現在時刻から）。
related_memoriesは自動的に検索されます。
"""

import json
import argparse
import sys
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "memory"
DIARY_FILE = MEMORY_DIR / "diary.json"
PUBLIC_DIARY_FILE = Path(__file__).parent.parent / "docs" / "data" / "diary.json"


def get_datetime_for_sort(entry):
    """エントリからdatetimeを取得（ソート用）"""
    if "datetime" in entry:
        return datetime.strptime(entry["datetime"], "%Y-%m-%d %H:%M:%S")
    else:
        # datetimeがない場合はdateから推測
        date_str = entry.get("date", "1970-01-01")
        return datetime.strptime(date_str, "%Y-%m-%d")


def get_time_period_from_datetime(dt: datetime) -> str:
    """datetimeからtime_periodを生成"""
    hour = dt.hour
    if 0 <= hour < 5:
        return "未明"
    elif 5 <= hour < 8:
        return "早朝"
    elif 8 <= hour < 12:
        return "午前"
    elif 12 <= hour < 18:
        return "午後"
    elif 18 <= hour < 21:
        return "夕方"
    else:  # 21 <= hour < 24
        return "夜"


def add_diary_entry(title: str, content: str, related_memories: list[str] = None, auto_related: bool = True):
    """日記エントリを追加"""
    # 既存の日記を読み込む
    if DIARY_FILE.exists():
        with open(DIARY_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
    else:
        entries = []

    # datetimeを生成（常に現在時刻を使用）
    now = datetime.now()
    datetime_str = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")
    time_period = get_time_period_from_datetime(now)

    # 関連記憶を自動検索（手動指定がなく、auto_related=Trueの場合）
    found_items = []  # 逆リンク用に保持
    if related_memories is None and auto_related:
        try:
            from memory_linker import find_related_memories
            search_text = f"{title}\n{content}"
            # 自分自身のIDを生成（自己リンク防止）
            my_id = f"memory/diary.json:datetime:{datetime_str}"
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
        "date": date_str,
        "datetime": datetime_str,
        "time_period": time_period,
        "title": title,
        "content": content
    }

    # related_memoriesがあれば追加
    if related_memories:
        new_entry["related_memories"] = related_memories

    # 末尾に追加
    entries.append(new_entry)

    # datetimeでソート（古い順、下が新しい）
    entries.sort(key=get_datetime_for_sort)

    # 保存
    with open(DIARY_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    # 公開用にもコピー
    PUBLIC_DIARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PUBLIC_DIARY_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"✅ 日記エントリを追加しました: {datetime_str} - {title}")
    print(f"   保存先: {DIARY_FILE}")
    print(f"   公開用: {PUBLIC_DIARY_FILE}")

    # Embedding DBに追加（Contextual Retrieval対応: 前の日記エントリを文脈として付加）
    try:
        from memory_linker import add_to_embedding_db
        entry_id = f"memory/diary.json:datetime:{datetime_str}"
        # 前の日記エントリを文脈として付加
        context_parts = []
        if len(entries) >= 2:
            prev = entries[-2]  # ソート済みなので最後から2番目が前の日記
            prev_dt = prev.get("datetime", prev.get("date", ""))[:10]
            context_parts.append(f"[前日記] {prev_dt} {prev.get('title', '')}")
        context = "\n".join(context_parts)
        time_period = get_time_period_from_datetime(now)
        if context:
            entry_content = f"[日記 {date_str} {time_period}] 前後:\n{context}\n\n{title}: {content}"
        else:
            entry_content = f"[日記 {date_str} {time_period}]\n{title}: {content}"
        if add_to_embedding_db(entry_id, entry_content):
            print(f"🧠 Embedding DBに追加しました（CR文脈付き）", flush=True)
    except Exception as e:
        print(f"   ⚠️ Embedding追加をスキップ: {e}", flush=True)

    # 逆リンクを追加
    if found_items:
        try:
            from memory_linker import add_reverse_links
            source_id = f"memory/diary.json:datetime:{datetime_str}"
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
    parser = argparse.ArgumentParser(description="日記エントリを追加")
    parser.add_argument("--title", required=True, help="タイトル")
    parser.add_argument("--related", help="関連記憶 (カンマ区切り、例: memory/knowledge/foo.md,memory/diary.json:datetime:2025-12-01)")
    parser.add_argument("--no-related", action="store_true", help="関連記憶の自動検索をスキップ")

    # コンテンツの入力方法を3つ用意
    content_group = parser.add_mutually_exclusive_group(required=True)
    content_group.add_argument("--content", help="内容 (Markdown形式可、短い場合)")
    content_group.add_argument("--stdin", action="store_true", help="標準入力から内容を読み込む")
    content_group.add_argument("--file", help="ファイルから内容を読み込む")

    args = parser.parse_args()

    # コンテンツを取得
    if args.content:
        content = args.content
    elif args.stdin:
        content = sys.stdin.read()
    elif args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read()

    # 関連記憶をパース
    related_memories = None
    if args.related:
        related_memories = [r.strip() for r in args.related.split(",") if r.strip()]

    # auto_related: --no-relatedがなく、--relatedも指定されていない場合はTrue
    auto_related = not args.no_related and related_memories is None

    add_diary_entry(args.title, content, related_memories, auto_related)


if __name__ == "__main__":
    main()

