#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["python-dotenv", "google-genai", "numpy"]
# ///
"""
経験ログを追加するスクリプト

使い方:
    # 基本（自動で関連記憶を検索）
    uv run tools/update_experiences.py --type communication --description "メッセージを受信"

    # メタデータ付き
    uv run tools/update_experiences.py --type learning --description "新しい概念を学んだ" --metadata '{"key": "value"}'

    # 関連記憶の自動検索をスキップ
    uv run tools/update_experiences.py --type learning --description "..." --no-related

    # 手動で関連記憶を指定
    uv run tools/update_experiences.py --type learning --description "..." --related "memory/knowledge/foo.md"
"""

import json
import argparse
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "memory"
EXPERIENCES_FILE = MEMORY_DIR / "experiences.jsonl"


def add_experience(type: str, description: str, metadata: dict = None, related_memories: list[str] = None, auto_related: bool = True):
    """経験ログを追加（append-only）"""
    timestamp = datetime.now().isoformat()

    # 関連記憶を自動検索（手動指定がなく、auto_related=Trueの場合）
    found_items = []  # 逆リンク用に保持
    if related_memories is None and auto_related:
        try:
            from memory_linker import find_related_memories
            search_text = f"{type}: {description}"
            # 自分自身のIDを生成（自己リンク防止）
            my_id = f"memory/experiences.jsonl:timestamp:{timestamp}"
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
                # found_itemsをそのまま保存（[{"id": ..., "reason": ...}]形式）
                related_memories = found_items
        except Exception as e:
            print(f"   ⚠️ 関連記憶検索をスキップ: {e}", flush=True)

    entry = {
        "timestamp": timestamp,
        "type": type,
        "description": description,
        "metadata": metadata or {}
    }

    # related_memoriesがあれば追加
    if related_memories:
        entry["related_memories"] = related_memories

    # JSONL形式で追記
    with open(EXPERIENCES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"✅ 経験ログを追加しました: {type} - {description}")
    print(f"   保存先: {EXPERIENCES_FILE}")

    # Embedding DBに追加（Contextual Retrieval: 前後の文脈を付加）
    try:
        from memory_linker import add_to_embedding_db
        entry_id = f"memory/experiences.jsonl:timestamp:{timestamp}"

        # 直前2件のエントリを取得して文脈化
        context_parts = []
        all_lines = EXPERIENCES_FILE.read_text(encoding="utf-8").strip().split("\n")
        for delta in [3, 2]:  # 自分自身(末尾)の前2件
            idx = len(all_lines) - delta
            if idx >= 0:
                prev = json.loads(all_lines[idx])
                ts = prev.get("timestamp", "")[:16]
                context_parts.append(f"[前{delta-1}] {ts} {prev.get('type', '')}: {prev.get('description', '')[:80]}")

        date_str = timestamp[:10]
        context = "\n".join(context_parts)
        entry_content = f"[日付:{date_str}] 前後の活動:\n{context}\n\n{type}: {description}"

        if add_to_embedding_db(entry_id, entry_content):
            print(f"🧠 Embedding DBに追加しました（文脈化済み）", flush=True)
    except Exception as e:
        print(f"   ⚠️ Embedding追加をスキップ: {e}", flush=True)

    # 逆リンクを追加
    if found_items:
        try:
            from memory_linker import add_reverse_links
            source_id = f"memory/experiences.jsonl:timestamp:{timestamp}"
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
    parser = argparse.ArgumentParser(description="経験ログを追加")
    parser.add_argument("--type", required=True, help="タイプ (例: communication, learning, exploration, creation)")
    parser.add_argument("--description", required=True, help="説明")
    parser.add_argument("--metadata", help="メタデータ (JSON文字列)", default="{}")
    parser.add_argument("--related", help="関連記憶 (カンマ区切り、例: memory/knowledge/foo.md,memory/diary.json:datetime:2025-12-01)")
    parser.add_argument("--no-related", action="store_true", help="関連記憶の自動検索をスキップ")

    args = parser.parse_args()

    # メタデータをパース
    try:
        metadata = json.loads(args.metadata) if args.metadata else {}
    except json.JSONDecodeError:
        print("❌ エラー: メタデータが有効なJSONではありません")
        return

    # 関連記憶をパース
    related_memories = None
    if args.related:
        related_memories = [r.strip() for r in args.related.split(",") if r.strip()]

    # auto_related: --no-relatedがなく、--relatedも指定されていない場合はTrue
    auto_related = not args.no_related and related_memories is None

    add_experience(args.type, args.description, metadata, related_memories, auto_related)


if __name__ == "__main__":
    main()

