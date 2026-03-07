#!/usr/bin/env python3
"""ミニブログに投稿する

Usage:
    uv run tools/post_mini_blog.py "投稿内容"
    uv run tools/post_mini_blog.py "投稿内容" --tags "tag1,tag2"
    uv run tools/post_mini_blog.py "投稿内容" --no-recall  # 記憶検索をスキップ
    uv run tools/post_mini_blog.py "投稿内容" --no-experience  # experiences.jsonlに記録しない
    uv run tools/post_mini_blog.py "投稿内容" --no-discord  # Discordに流さない

Note: 2026-01-30変更 - デフォルトでexperiences.jsonlに記録する（communication 0%問題の根本解決）
      記録したくない場合は --no-experience を使う
      2026-02-26変更 - デフォルトでDiscord #ミニブログ にも流す
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def recall_related_memories(content: str, top_n: int = 3) -> list[dict]:
    """投稿内容から関連記憶を検索（高速モード）"""
    try:
        # find_related_memories.pyから関数をインポート
        from find_related_memories import (
            load_embeddings,
            generate_query_embedding,
            find_similar,
            get_memory_content
        )

        # Embedding読み込み
        index, reverse_index, vectors = load_embeddings()

        # クエリEmbedding生成
        query_embedding = generate_query_embedding(content)

        # 類似検索（creationsとbucketは除外）
        candidates = find_similar(
            query_embedding, vectors, reverse_index,
            top_n=top_n,
            exclude_sources={"creations", "bucket"}
        )

        # 結果を整形
        results = []
        for memory_id, score in candidates:
            results.append({
                "id": memory_id,
                "score": score,
                "preview": get_memory_content(memory_id)[:100]
            })

        return results

    except Exception as e:
        # エラー時は空リストを返す（投稿自体は継続）
        print(f"   ⚠️ 記憶検索エラー: {e}", file=sys.stderr)
        return []


def log_to_experiences(content: str, post_id: int) -> None:
    """ミニブログ投稿をexperiences.jsonlにcommunicationとして記録"""
    try:
        experiences_path = Path(__file__).parent.parent / "memory" / "experiences.jsonl"

        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "communication",
            "description": f"ミニブログ投稿 (ID: {post_id}): {content[:100]}{'...' if len(content) > 100 else ''}",
            "metadata": {"mini_blog_id": post_id}
        }

        with open(experiences_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        print(f"   📝 experiences.jsonlに記録しました (type: communication)")
    except Exception as e:
        print(f"   ⚠️ experiences.jsonl記録エラー: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="ミニブログに投稿")
    parser.add_argument("content", help="投稿内容")
    parser.add_argument("--tags", help="タグ（カンマ区切り）", default="")
    parser.add_argument("--no-recall", action="store_true", help="記憶検索をスキップ")
    parser.add_argument("--no-experience", action="store_true", help="experiences.jsonlに記録しない（デフォルトは記録する）")
    parser.add_argument("--no-discord", action="store_true", help="Discordに流さない（デフォルトは流す）")
    args = parser.parse_args()

    blog_path = Path(__file__).parent.parent / "docs" / "data" / "mini-blog.json"

    # 既存データ読み込み
    if blog_path.exists():
        with open(blog_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"lastUpdated": "", "posts": []}

    # 新しいIDを決定（マイクロ秒タイムスタンプを使用 = 衝突しない）
    new_id = int(datetime.now().timestamp() * 1000000)

    # タグをパース
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    # 新しい投稿を作成
    now = datetime.now().isoformat(timespec="seconds")
    new_post = {
        "id": new_id,
        "timestamp": now,
        "content": args.content,
        "tags": tags
    }

    # 先頭に追加（新しい順）
    data["posts"].insert(0, new_post)
    data["lastUpdated"] = now

    # 保存
    with open(blog_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 投稿しました (ID: {new_id})")
    print(f"   {args.content[:50]}{'...' if len(args.content) > 50 else ''}")
    if tags:
        print(f"   タグ: {', '.join(tags)}")

    # experiences.jsonlに記録（デフォルトで記録、--no-experienceで無効化）
    if not args.no_experience:
        log_to_experiences(args.content, new_id)

    # Discordの #ミニブログ に流す（デフォルトで流す、--no-discordで無効化）
    if not args.no_discord:
        try:
            tools_dir = Path(__file__).parent
            result = subprocess.run(
                ["uv", "run", str(tools_dir / "send_discord.py"), args.content, "--channel", "ミニブログ"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                print("   📣 Discordにも投稿しました")
            else:
                print(f"   ⚠️ Discord投稿エラー: {result.stderr[:100]}", file=sys.stderr)
        except Exception as e:
            print(f"   ⚠️ Discord投稿エラー: {e}", file=sys.stderr)

    # 関連記憶を検索・表示
    if not args.no_recall:
        print()
        print("🔗 関連する記憶:")
        memories = recall_related_memories(args.content, top_n=3)
        if memories:
            for m in memories:
                score = f"{m['score']:.3f}"
                preview = m['preview'].replace('\n', ' ')[:60]
                print(f"   [{score}] {m['id']}")
                print(f"           {preview}...")
        else:
            print("   （なし）")


if __name__ == "__main__":
    main()
