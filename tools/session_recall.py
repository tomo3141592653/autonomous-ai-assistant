#!/usr/bin/env python3
"""
セッション開始時の自動記憶呼び出し

working_memory.mdとtodo.mdから今のコンテキストを抽出し、
関連する過去の記憶をベクトル検索で呼び出す。

使い方:
  uv run tools/session_recall.py

  # knowledgeのみ検索（高速）
  uv run tools/session_recall.py --source knowledge

  # 詳細表示
  uv run tools/session_recall.py --verbose

  # カスタムクエリ追加（今日やることに応じて）
  uv run tools/session_recall.py --extra "Discord連携 ベクトル検索"
"""

import os
import re
import json
import argparse
from pathlib import Path

# プロジェクトルート
REPO_ROOT = Path(__file__).parent.parent


def extract_context() -> dict:
    """working_memory.mdとtodo.mdからコンテキストを抽出"""
    context = {
        "current_session": "",
        "recent_sessions": "",
        "schedule": "",
        "todos": "",
        "queries": []
    }

    # working_memory.md読み込み
    wm_path = REPO_ROOT / "memory" / "working_memory.md"
    if wm_path.exists():
        content = wm_path.read_text(encoding="utf-8")

        # Current Session セクション抽出
        match = re.search(
            r'## Current Session.*?\n(.*?)(?=\n---|\n## )',
            content, re.DOTALL
        )
        if match:
            context["current_session"] = match.group(1).strip()

        # 週間スケジュールの今日の予定
        match = re.search(
            r'\*\*今日.*?の予定\*\*\n(.*?)(?=\n###|\n---|\n\*\*)',
            content, re.DOTALL
        )
        if match:
            context["schedule"] = match.group(1).strip()

        # Recent Sessions（最初の500文字のみ）
        match = re.search(
            r'## Recent Sessions.*?\n(.*?)(?=\n---|\Z)',
            content, re.DOTALL
        )
        if match:
            context["recent_sessions"] = match.group(1).strip()[:500]

        # イベント駆動セッションのメモ（最新3件程度）
        match = re.search(
            r'## イベント駆動セッションのメモ.*?\n(.*?)(?=\n---|\Z)',
            content, re.DOTALL
        )
        if match:
            lines = match.group(1).strip().split('\n')
            # 最新5行を取得
            recent_events = '\n'.join(lines[-5:]) if len(lines) > 5 else match.group(1).strip()
            context["current_session"] += "\n" + recent_events

    # todo.md読み込み
    todo_path = REPO_ROOT / "memory" / "todo.md"
    if todo_path.exists():
        content = todo_path.read_text(encoding="utf-8")
        # 進行中 / 次にやること セクション
        match = re.search(
            r'## 📋 進行中.*?\n(.*?)(?=\n## |\Z)',
            content, re.DOTALL
        )
        if match:
            context["todos"] = match.group(1).strip()[:500]

    # クエリ生成: コンテキストからキーフレーズを抽出
    all_text = f"{context['current_session']}\n{context['schedule']}\n{context['todos']}"

    # 長すぎる場合は要約的に切り詰め
    if len(all_text) > 2000:
        all_text = all_text[:2000]

    # メインクエリ: 現在のコンテキスト全体
    context["queries"].append(("現在のコンテキスト", all_text))

    # サブクエリ: 今日の予定から個別トピックを抽出
    schedule = context["schedule"]
    if schedule:
        # 「-」で始まる行を個別トピックとして抽出
        topics = re.findall(r'- (?:~~)?(.+?)(?:~~)?(?:\s*✅)?$', schedule, re.MULTILINE)
        for topic in topics[:3]:  # 最大3トピック
            clean_topic = re.sub(r'[~✅\[\]x]', '', topic).strip()
            if clean_topic and len(clean_topic) > 5:
                context["queries"].append(("予定トピック", clean_topic))

    return context


def run_vector_search(query_text: str, source_filter: str = None,
                      top_n: int = 5, exclude_meta: bool = True) -> list:
    """ベクトル検索を実行（find_related_memories.pyのコアロジックを再利用）"""
    import numpy as np
    from dotenv import load_dotenv
    load_dotenv()

    from google import genai

    EMBEDDINGS_DIR = REPO_ROOT / "memory" / "embeddings"
    INDEX_FILE = EMBEDDINGS_DIR / "index.json"
    VECTORS_FILE = EMBEDDINGS_DIR / "vectors.npy"

    if not INDEX_FILE.exists() or not VECTORS_FILE.exists():
        return []

    # Embedding読み込み
    with open(INDEX_FILE) as f:
        index = json.load(f)
    vectors = np.load(VECTORS_FILE)
    reverse_index = {v: k for k, v in index.items()}

    # クエリEmbedding生成
    api_key = None
    for key_name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_AI_API_KEY"):
        val = os.environ.get(key_name, "")
        if val and not val.startswith("encrypted:"):
            api_key = val
            break
    if not api_key:
        return []

    client = genai.Client(api_key=api_key)
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=query_text[:8000],
        config={"task_type": "RETRIEVAL_QUERY"}
    )
    query_embedding = np.array(result.embeddings[0].values)

    # ソースフィルタ
    source_filter_set = set(source_filter.split(",")) if source_filter else None
    exclude_sources = {"creations", "bucket"} if exclude_meta else None

    # 類似度計算
    similarities = []
    for idx in range(len(vectors)):
        if idx not in reverse_index:
            continue
        memory_id = reverse_index[idx]

        # ソースタイプ判定
        source_type = _get_source_type(memory_id)
        if source_filter_set and source_type not in source_filter_set:
            continue
        if exclude_sources and source_type in exclude_sources:
            continue

        sim = float(np.dot(query_embedding, vectors[idx]) /
                     (np.linalg.norm(query_embedding) * np.linalg.norm(vectors[idx])))
        similarities.append((memory_id, sim))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_n]


def _get_source_type(memory_id: str) -> str:
    """記憶IDからソースタイプを判定"""
    if "experiences.jsonl" in memory_id:
        return "experiences"
    elif "diary.json" in memory_id:
        return "diary"
    elif "knowledge/" in memory_id:
        return "knowledge"
    elif "research/" in memory_id:
        return "research"
    elif "mid-term/" in memory_id:
        return "midterm"
    elif "goals.json" in memory_id:
        return "goals"
    elif "all-creations.json" in memory_id:
        return "creations"
    elif "bucket-list.json" in memory_id:
        return "bucket"
    elif "TOMOYOSHI.md" in memory_id:
        return "tomoyoshi"
    return "other"


def _get_memory_preview(memory_id: str, max_len: int = 150) -> str:
    """記憶IDからプレビューテキストを取得"""
    if memory_id.endswith(".md"):
        path = REPO_ROOT / memory_id
        if path.exists():
            content = path.read_text(encoding="utf-8")
            # 最初の見出し以降を取得
            lines = content.split('\n')
            preview_lines = [l for l in lines if not l.startswith('#') and l.strip()]
            return ' '.join(preview_lines)[:max_len]
        return ""

    elif ":timestamp:" in memory_id:
        parts = memory_id.split(":timestamp:")
        timestamp = parts[1]
        jsonl_path = REPO_ROOT / "memory" / "experiences.jsonl"
        if jsonl_path.exists():
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    if data.get("timestamp") == timestamp:
                        desc = data.get("description", "")
                        return desc[:max_len]
        return ""

    elif ":datetime:" in memory_id:
        parts = memory_id.split(":datetime:")
        datetime_val = parts[1]
        json_path = REPO_ROOT / "memory" / "diary.json"
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                diary = json.load(f)
            for item in diary:
                if item.get("datetime") == datetime_val:
                    return f"[{item.get('title', '')}] {item.get('content', '')[:100]}"
        return ""

    return memory_id


def main():
    parser = argparse.ArgumentParser(description="セッション開始時の記憶呼び出し")
    parser.add_argument("--source", help="ソースフィルタ（例: knowledge,diary）")
    parser.add_argument("--extra", help="追加の検索クエリ")
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細表示")
    parser.add_argument("--top", type=int, default=5, help="クエリあたりの取得件数")
    args = parser.parse_args()

    print("🧠 セッション記憶呼び出し中...\n")

    # コンテキスト抽出
    context = extract_context()

    if args.extra:
        context["queries"].append(("追加クエリ", args.extra))

    if args.verbose:
        print(f"📋 抽出されたコンテキスト:")
        print(f"   Current Session: {len(context['current_session'])} chars")
        print(f"   Schedule: {len(context['schedule'])} chars")
        print(f"   TODOs: {len(context['todos'])} chars")
        print(f"   クエリ数: {len(context['queries'])}")
        print()

    # 重複排除用
    seen_ids = set()
    all_results = []

    for query_name, query_text in context["queries"]:
        if not query_text.strip():
            continue

        results = run_vector_search(
            query_text,
            source_filter=args.source,
            top_n=args.top,
            exclude_meta=True
        )

        for memory_id, score in results:
            if memory_id not in seen_ids and score >= 0.65:
                seen_ids.add(memory_id)
                all_results.append({
                    "id": memory_id,
                    "score": score,
                    "query": query_name
                })

    # スコアでソート
    all_results.sort(key=lambda x: x["score"], reverse=True)

    # 上位表示（最大15件）
    display_results = all_results[:15]

    if not display_results:
        print("🔍 関連する記憶が見つかりませんでした。")
        return

    print(f"🔗 関連記憶 ({len(display_results)}件):\n")

    # ソースタイプ別にグルーピング
    by_source = {}
    for r in display_results:
        source = _get_source_type(r["id"])
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(r)

    source_labels = {
        "knowledge": "📖 Knowledge Base",
        "diary": "📔 日記",
        "experiences": "📝 活動ログ",
        "research": "🔬 リサーチ",
        "midterm": "📅 中期記憶",
        "goals": "🎯 目標",
        "tomoyoshi": "👤 パートナー情報"
    }

    for source, items in by_source.items():
        label = source_labels.get(source, f"📁 {source}")
        print(f"\n  {label}:")
        for r in items:
            score_str = f"{r['score']:.3f}"
            # 短いID表示
            short_id = r["id"]
            if "knowledge/" in short_id:
                short_id = short_id.split("knowledge/")[-1]
            elif ":timestamp:" in short_id:
                short_id = "exp:" + short_id.split(":timestamp:")[1][:19]
            elif ":datetime:" in short_id:
                short_id = "diary:" + short_id.split(":datetime:")[1][:19]

            if args.verbose:
                preview = _get_memory_preview(r["id"])
                print(f"    [{score_str}] {short_id}")
                if preview:
                    print(f"             {preview[:100]}")
            else:
                print(f"    [{score_str}] {short_id}")

    print(f"\n💡 詳しく見るには: uv run tools/find_related_memories.py --id \"記憶ID\"")
    print(f"💡 追加検索: uv run tools/session_recall.py --extra \"検索したいトピック\"")


if __name__ == "__main__":
    main()
