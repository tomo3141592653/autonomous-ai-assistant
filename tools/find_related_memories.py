#!/usr/bin/env python3
"""
Phase 2: 関連記憶検索ツール

使い方:
  # テキストから関連記憶を検索
  uv run tools/find_related_memories.py --text "夢野久作の小説"

  # ファイルから関連記憶を検索
  uv run tools/find_related_memories.py --file memory/knowledge/yumeno-kyusaku.md

  # 記憶IDから内容を表示 + 関連記憶を検索（芋づる式）
  uv run tools/find_related_memories.py --id "memory/diary.json:datetime:2025-12-04 08:41:28"
  uv run tools/find_related_memories.py --id "memory/experiences.jsonl:timestamp:2025-12-05T03:19:41.352134"
  uv run tools/find_related_memories.py --id "memory/knowledge/topic.md"

  # Top N件を指定
  uv run tools/find_related_memories.py --text "..." --top 10

  # Geminiでの関連性確認をスキップ（高速モード）
  uv run tools/find_related_memories.py --text "..." --fast

  # ソースタイプでフィルタ（複数指定可）
  uv run tools/find_related_memories.py --text "..." --source experiences,diary,knowledge

  # all-creations, bucket-listを除外（デフォルト動作）
  uv run tools/find_related_memories.py --text "..." --exclude-meta

ソースタイプ:
  - experiences: memory/experiences.jsonl
  - diary: memory/diary.json
  - knowledge: memory/knowledge/*.md
  - research: ayumu-lab/research/*.md
  - midterm: memory/mid-term/*.md
  - goals: memory/goals.json
  - creations: docs/data/all-creations.json
  - bucket: docs/data/bucket-list.json
  - tomoyoshi: TOMOYOSHI.md
"""

import os
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from google import genai
import numpy as np

# .env読み込み
load_dotenv()

# 設定
REPO_ROOT = Path(__file__).parent.parent
EMBEDDINGS_DIR = REPO_ROOT / "memory" / "embeddings"
INDEX_FILE = EMBEDDINGS_DIR / "index.json"
VECTORS_FILE = EMBEDDINGS_DIR / "vectors.npy"

# Gemini設定（新SDK: google-genai）
def _get_api_key():
    for key_name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_AI_API_KEY"):
        val = os.environ.get(key_name, "")
        if val and not val.startswith("encrypted:"):
            return val
    return None

api_key = _get_api_key()
if not api_key:
    raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY not found. (Check dotenvx encryption)")
client = genai.Client(api_key=api_key)


def load_embeddings():
    """保存済みEmbeddingを読み込み"""
    if not INDEX_FILE.exists() or not VECTORS_FILE.exists():
        raise FileNotFoundError("Embeddings not found. Run generate_embeddings.py first.")

    with open(INDEX_FILE) as f:
        index = json.load(f)
    vectors = np.load(VECTORS_FILE)

    # index: {id: idx} → reverse: {idx: id}
    reverse_index = {v: k for k, v in index.items()}

    return index, reverse_index, vectors


def generate_query_embedding(text: str) -> np.ndarray:
    """クエリ用のEmbeddingを生成（新SDK）"""
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text[:8000],
        config={"task_type": "RETRIEVAL_QUERY"}
    )
    return np.array(result.embeddings[0].values)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """コサイン類似度を計算"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def get_source_type(memory_id: str) -> str:
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


def find_similar(query_embedding: np.ndarray, vectors: np.ndarray,
                 reverse_index: dict, top_n: int = 5,
                 exclude_ids: set = None,
                 source_filter: set = None,
                 exclude_sources: set = None) -> list[tuple[str, float]]:
    """類似度上位N件を取得"""
    similarities = []

    for idx in range(len(vectors)):
        if idx not in reverse_index:
            continue  # インデックスにないエントリはスキップ
        memory_id = reverse_index[idx]
        if exclude_ids and memory_id in exclude_ids:
            continue

        # ソースフィルタ
        source_type = get_source_type(memory_id)
        if source_filter and source_type not in source_filter:
            continue
        if exclude_sources and source_type in exclude_sources:
            continue

        sim = cosine_similarity(query_embedding, vectors[idx])
        similarities.append((memory_id, sim))

    # 類似度でソート
    similarities.sort(key=lambda x: x[1], reverse=True)

    return similarities[:top_n]


def verify_with_gemini(query_text: str, candidates: list[tuple[str, float]]) -> list[dict]:
    """Geminiで関連性を確認（新SDK）"""

    # 候補の内容を取得
    candidate_texts = []
    for memory_id, score in candidates:
        content = get_memory_content(memory_id)
        candidate_texts.append({
            "id": memory_id,
            "score": score,
            "content": content[:500]  # 最初の500文字
        })

    prompt = f"""以下のクエリテキストと、候補となる記憶のリストがあります。
各候補が本当にクエリと深く関連があるかを厳密に判定してください。

クエリ:
{query_text[:1000]}

候補:
{json.dumps(candidate_texts, ensure_ascii=False, indent=2)}

各候補について、以下のJSON形式で回答してください:
[
  {{"id": "...", "is_related": true/false, "reason": "具体的にどのアイデア・技術・経験・感情が共鳴しているかを1文で"}}
]

【関連ありと判定する基準（どれか一つ以上）】
- 同じ技術・概念・アイデアが扱われている
- 類似した感情・気づき・洞察がある
- 一方が他方の先行事例・発展系・応用になっている
- 共通の問題意識・テーマがある

【必ず「関連なし」と判定するもの】
- 単に同じ人物が登場するだけ
- 単に同じプロジェクトで作業したというだけ
- 単に同じ時期・セッション・日付というだけ
- 単にAyumuが何かした・動いたという共通点だけ
- クエリの内容と具体的なつながりが説明できないもの

reasonには「クエリのXという部分と候補のYという部分が〜という点で対応している」のように具体的に書くこと。
「同じ人物が出るため」「同じセッションのため」「同じ日に言及しているため」は理由として不十分なので is_related: false にすること。
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    # JSONをパース
    try:
        # ```json ... ``` を除去
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
        return result
    except:
        # パース失敗時は全部関連ありとする
        return [{"id": c["id"], "is_related": True, "reason": "判定不能"} for c in candidate_texts]


def get_memory_content(memory_id: str) -> str:
    """記憶IDからコンテンツを取得"""
    if memory_id.endswith(".md"):
        # Markdownファイル
        path = REPO_ROOT / memory_id
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    elif ":timestamp:" in memory_id:
        # experiences.jsonl
        parts = memory_id.split(":timestamp:")
        timestamp = parts[1]
        jsonl_path = REPO_ROOT / "memory" / "experiences.jsonl"
        if jsonl_path.exists():
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    if data.get("timestamp") == timestamp:
                        return f"{data.get('type', '')}: {data.get('description', '')}"
        return ""

    elif ":datetime:" in memory_id:
        # diary.json
        parts = memory_id.split(":datetime:")
        datetime_val = parts[1]
        json_path = REPO_ROOT / "memory" / "diary.json"
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                diary = json.load(f)
            for item in diary:
                if item.get("datetime") == datetime_val:
                    return f"{item.get('title', '')}: {item.get('content', '')}"
        return ""

    elif ":id:" in memory_id:
        # bucket-list or all-creations
        parts = memory_id.split(":id:")
        file_path = parts[0]
        item_id = parts[1]
        json_path = REPO_ROOT / file_path
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)

            if "bucket-list" in file_path:
                for cat_data in data.get("categories", {}).values():
                    for item in cat_data.get("items", []):
                        if str(item.get("id")) == item_id:
                            return f"{item.get('text', '')}"
            elif "all-creations" in file_path:
                for item in data.get("creations", []):
                    if item.get("id") == item_id:
                        return f"{item.get('title', '')}: {item.get('description', '')}"
        return ""

    elif ":goal:" in memory_id:
        # goals.json
        parts = memory_id.split(":goal:")
        goal_text = parts[1]
        json_path = REPO_ROOT / "memory" / "goals.json"
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                goals = json.load(f)
            # short_term, long_term両方を検索
            for term in ["short_term", "long_term"]:
                for goal in goals.get(term, []):
                    if goal.get("goal") == goal_text:
                        return f"[{term}] {goal.get('goal', '')}: {goal.get('notes', '')}"
        return ""

    return ""


def get_memory_full(memory_id: str) -> dict:
    """記憶IDから完全なデータを取得（related_memories含む）"""
    result = {
        "id": memory_id,
        "content": "",
        "related_memories": [],
        "metadata": {}
    }

    if memory_id.endswith(".md"):
        # Markdownファイル
        path = REPO_ROOT / memory_id
        if path.exists():
            content = path.read_text(encoding="utf-8")
            result["content"] = content
            # Related Memoriesセクションを抽出
            if "## Related Memories" in content:
                import re
                match = re.search(r'## Related Memories\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
                if match:
                    links = re.findall(r'\[\[([^\]]+)\]\]', match.group(1))
                    result["related_memories"] = links
        return result

    elif ":timestamp:" in memory_id:
        # experiences.jsonl
        parts = memory_id.split(":timestamp:")
        timestamp = parts[1]
        jsonl_path = REPO_ROOT / "memory" / "experiences.jsonl"
        if jsonl_path.exists():
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    if data.get("timestamp") == timestamp:
                        result["content"] = data.get("description", "")
                        result["metadata"] = {
                            "type": data.get("type", ""),
                            "timestamp": timestamp
                        }
                        # related_memoriesを取得
                        rm = data.get("related_memories", [])
                        if rm:
                            # リストの各要素がdictなら"id"を、strならそのまま
                            result["related_memories"] = [
                                r["id"] if isinstance(r, dict) else r for r in rm
                            ]
                        return result
        return result

    elif ":datetime:" in memory_id:
        # diary.json
        parts = memory_id.split(":datetime:")
        datetime_val = parts[1]
        json_path = REPO_ROOT / "memory" / "diary.json"
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                diary = json.load(f)
            for item in diary:
                if item.get("datetime") == datetime_val:
                    result["content"] = item.get("content", "")
                    result["metadata"] = {
                        "title": item.get("title", ""),
                        "date": item.get("date", ""),
                        "time_period": item.get("time_period", "")
                    }
                    # related_memoriesを取得
                    rm = item.get("related_memories", [])
                    if rm:
                        result["related_memories"] = [
                            r["id"] if isinstance(r, dict) else r for r in rm
                        ]
                    return result
        return result

    elif ":id:" in memory_id:
        # bucket-list or all-creations
        parts = memory_id.split(":id:")
        file_path = parts[0]
        item_id = parts[1]
        json_path = REPO_ROOT / file_path
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)

            if "all-creations" in file_path:
                for item in data.get("creations", []):
                    if item.get("id") == item_id:
                        result["content"] = item.get("description", "")
                        result["metadata"] = {
                            "title": item.get("title", ""),
                            "number": item.get("number", ""),
                            "category": item.get("category", ""),
                            "url": item.get("url", "")
                        }
                        return result
        return result

    elif ":goal:" in memory_id:
        # goals.json
        parts = memory_id.split(":goal:")
        goal_text = parts[1]
        json_path = REPO_ROOT / "memory" / "goals.json"
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                goals = json.load(f)
            for term in ["short_term", "long_term"]:
                for goal in goals.get(term, []):
                    if goal.get("goal") == goal_text:
                        result["content"] = goal.get("goal", "")
                        result["metadata"] = {
                            "term": term,
                            "notes": goal.get("notes", ""),
                            "status": goal.get("status", "")
                        }
                        rm = goal.get("related_memories", [])
                        if rm:
                            result["related_memories"] = [
                                r["id"] if isinstance(r, dict) else r for r in rm
                            ]
                        return result
        return result

    return result


def print_memory(memory_id: str, show_related: bool = True):
    """記憶IDの内容を表示"""
    data = get_memory_full(memory_id)

    if not data["content"]:
        print(f"❌ 記憶が見つかりません: {memory_id}")
        return

    print(f"\n{'='*60}")
    print(f"📝 ID: {memory_id}")
    print(f"{'='*60}")

    # メタデータ表示
    if data["metadata"]:
        for key, value in data["metadata"].items():
            if value:
                print(f"   {key}: {value}")
        print()

    # コンテンツ表示（最大2000文字）
    content = data["content"]
    if len(content) > 2000:
        print(content[:2000])
        print(f"\n... (truncated, {len(content)} chars total)")
    else:
        print(content)

    # 関連記憶表示
    if show_related and data["related_memories"]:
        print(f"\n{'─'*40}")
        print(f"🔗 関連記憶 ({len(data['related_memories'])}件):")
        for rm in data["related_memories"]:
            print(f"   → {rm}")


def main():
    parser = argparse.ArgumentParser(description="関連記憶を検索")
    parser.add_argument("--text", help="検索クエリテキスト")
    parser.add_argument("--file", help="検索元ファイル")
    parser.add_argument("--id", help="記憶IDから内容を表示 + 関連記憶を検索")
    parser.add_argument("--top", type=int, default=5, help="取得件数 (default: 5)")
    parser.add_argument("--fast", action="store_true", help="Gemini確認をスキップ")
    parser.add_argument("--json", action="store_true", help="JSON形式で出力")
    parser.add_argument("--source", help="ソースタイプでフィルタ（カンマ区切り）: experiences,diary,knowledge,research,midterm,goals,creations,bucket,tomoyoshi")
    parser.add_argument("--exclude-meta", action="store_true", help="creationsとbucketを除外（推奨）")
    args = parser.parse_args()

    # --id モード: 記憶IDから内容を表示
    if args.id:
        print_memory(args.id)
        return

    if not args.text and not args.file:
        parser.error("--text, --file, または --id を指定してください")

    # ソースフィルタの解析
    source_filter = None
    if args.source:
        source_filter = set(args.source.split(","))

    # メタデータ除外（デフォルトではcreationsとbucketを除外）
    exclude_sources = None
    if args.exclude_meta:
        exclude_sources = {"creations", "bucket"}

    # クエリテキスト取得
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"ファイルが見つかりません: {args.file}")
            return
        query_text = file_path.read_text(encoding="utf-8")
        exclude_ids = {args.file}
    else:
        query_text = args.text
        exclude_ids = set()

    # Embedding読み込み
    print("📚 Embedding読み込み中...", flush=True)
    index, reverse_index, vectors = load_embeddings()

    # クエリEmbedding生成
    print("🔍 検索中...", flush=True)
    query_embedding = generate_query_embedding(query_text)

    # 類似検索
    # Gemini確認する場合は多めに取得（embeddingの精度が低いので4倍取る）
    fetch_n = args.top * 4 if not args.fast else args.top
    candidates = find_similar(query_embedding, vectors, reverse_index,
                              top_n=fetch_n, exclude_ids=exclude_ids,
                              source_filter=source_filter,
                              exclude_sources=exclude_sources)

    if args.fast:
        # 高速モード: Embedding類似度のみ
        results = [{"id": id, "score": score, "is_related": True} for id, score in candidates]
    else:
        # Gemini確認
        print("🤖 Geminiで関連性確認中...", flush=True)
        verified = verify_with_gemini(query_text[:2000], candidates)

        # 関連ありのみフィルタ
        verified_ids = {v["id"]: v for v in verified if v.get("is_related")}
        results = []
        for id, score in candidates:
            if id in verified_ids:
                results.append({
                    "id": id,
                    "score": score,
                    "is_related": True,
                    "reason": verified_ids[id].get("reason", "")
                })
        results = results[:args.top]

    # 出力
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"\n🔗 関連記憶 (Top {len(results)}):\n")
        for r in results:
            score_str = f"{r['score']:.3f}"
            reason = f" - {r.get('reason', '')}" if r.get('reason') else ""
            print(f"  [{score_str}] {r['id']}{reason}")


if __name__ == "__main__":
    main()
