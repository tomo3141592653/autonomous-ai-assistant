#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["python-dotenv", "google-genai", "numpy"]
# ///
"""
目標を更新するスクリプト

使い方:
    # 短期目標を追加（自動で関連記憶を検索）
    uv run tools/update_goals.py --category short_term --goal "新しい目標" --notes "メモ"

    # 長期目標を追加
    uv run tools/update_goals.py --category long_term --goal "長期的な目標"

    # 目標を完了にする
    uv run tools/update_goals.py --complete "目標の説明"

    # 関連記憶の自動検索をスキップ
    uv run tools/update_goals.py --category short_term --goal "目標" --no-related

    # 手動で関連記憶を指定
    uv run tools/update_goals.py --category short_term --goal "目標" --related "memory/knowledge/foo.md"
"""

import json
import argparse
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "memory"
GOALS_FILE = MEMORY_DIR / "goals.json"


def add_goal(category: str, goal: str, notes: str = None, related_memories: list[str] = None, auto_related: bool = True):
    """目標を追加"""
    # 既存の目標を読み込む
    if GOALS_FILE.exists():
        with open(GOALS_FILE, "r", encoding="utf-8") as f:
            goals = json.load(f)
    else:
        goals = {"short_term": [], "long_term": [], "completed": []}

    # 関連記憶を自動検索（手動指定がなく、auto_related=Trueの場合）
    found_items = []  # 逆リンク用に保持
    if related_memories is None and auto_related:
        try:
            from memory_linker import find_related_memories
            search_text = f"{category}: {goal}"
            if notes:
                search_text += f" - {notes}"
            # 自分自身のIDを生成（自己リンク防止）
            my_id = f"memory/goals.json:goal:{goal}"
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

    # タイムスタンプを生成
    created_at = datetime.now().isoformat()

    # 新しい目標を作成
    new_goal = {
        "goal": goal,
        "created_at": created_at,
        "status": "active"
    }
    if notes:
        new_goal["notes"] = notes
    if related_memories:
        new_goal["related_memories"] = related_memories

    # カテゴリに追加
    if category not in goals:
        goals[category] = []
    goals[category].append(new_goal)

    # 保存
    with open(GOALS_FILE, "w", encoding="utf-8") as f:
        json.dump(goals, f, ensure_ascii=False, indent=2)

    # 公開用にもコピー
    PUBLIC_GOALS_FILE = Path(__file__).parent.parent / "docs" / "data" / "goals.json"
    with open(PUBLIC_GOALS_FILE, "w", encoding="utf-8") as f:
        json.dump(goals, f, ensure_ascii=False, indent=2)

    print(f"✅ 目標を追加しました: {category} - {goal}")
    print(f"   保存先: {GOALS_FILE}")

    # Embedding DBに追加
    try:
        from memory_linker import add_to_embedding_db
        entry_id = f"memory/goals.json:goal:{goal[:50]}"
        entry_content = f"{category}: {goal}"
        if notes:
            entry_content += f" - {notes}"
        if add_to_embedding_db(entry_id, entry_content):
            print(f"🧠 Embedding DBに追加しました", flush=True)
    except Exception as e:
        print(f"   ⚠️ Embedding追加をスキップ: {e}", flush=True)

    # 逆リンクを追加
    if found_items:
        try:
            from memory_linker import add_reverse_links
            source_id = f"memory/goals.json:goal:{goal[:50]}"
            result = add_reverse_links(source_id, found_items)

            total_updated = len(result["updated_md"]) + len(result["updated_diary"]) + len(result["updated_experiences"]) + len(result.get("updated_creations", []))
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
        except Exception as e:
            print(f"   ⚠️ 逆リンク追加をスキップ: {e}", flush=True)


def complete_goal(goal_description: str):
    """目標を完了にする"""
    if not GOALS_FILE.exists():
        print("❌ エラー: goals.jsonが見つかりません")
        return
    
    with open(GOALS_FILE, "r", encoding="utf-8") as f:
        goals = json.load(f)
    
    # short_termとlong_termから探す
    found = False
    for category in ["short_term", "long_term"]:
        for i, goal in enumerate(goals.get(category, [])):
            if goal_description in goal.get("goal", ""):
                # 完了済みに移動
                goal["status"] = "completed"
                goal["completed_at"] = datetime.now().isoformat()
                goals.setdefault("completed", []).append(goal)
                goals[category].pop(i)
                found = True
                break
        if found:
            break
    
    if not found:
        print(f"❌ エラー: 目標が見つかりません: {goal_description}")
        return
    
    # 保存
    with open(GOALS_FILE, "w", encoding="utf-8") as f:
        json.dump(goals, f, ensure_ascii=False, indent=2)

    # 公開用にもコピー
    PUBLIC_GOALS_FILE = Path(__file__).parent.parent / "docs" / "data" / "goals.json"
    with open(PUBLIC_GOALS_FILE, "w", encoding="utf-8") as f:
        json.dump(goals, f, ensure_ascii=False, indent=2)

    print(f"✅ 目標を完了にしました: {goal_description}")
    print(f"   保存先: {GOALS_FILE}")


def main():
    parser = argparse.ArgumentParser(description="目標を更新")
    parser.add_argument("--category", choices=["short_term", "long_term"], help="カテゴリ")
    parser.add_argument("--goal", help="目標の説明")
    parser.add_argument("--notes", help="メモ")
    parser.add_argument("--complete", help="完了にする目標の説明（部分一致可）")
    parser.add_argument("--related", help="関連記憶 (カンマ区切り)")
    parser.add_argument("--no-related", action="store_true", help="関連記憶の自動検索をスキップ")

    args = parser.parse_args()

    if args.complete:
        complete_goal(args.complete)
    elif args.category and args.goal:
        # 関連記憶をパース
        related_memories = None
        if args.related:
            related_memories = [r.strip() for r in args.related.split(",") if r.strip()]

        # auto_related: --no-relatedがなく、--relatedも指定されていない場合はTrue
        auto_related = not args.no_related and related_memories is None

        add_goal(args.category, args.goal, args.notes, related_memories, auto_related)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

