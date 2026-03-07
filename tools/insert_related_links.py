#!/usr/bin/env python3
"""
Phase 2.5: 既存memoryにリンク挿入スクリプト

既存のMarkdownファイルに Related Memories セクションを追加する。

使い方:
  # ドライラン（変更確認のみ）
  uv run tools/insert_related_links.py --dry-run

  # 実行
  uv run tools/insert_related_links.py

  # 特定のファイルのみ
  uv run tools/insert_related_links.py --file memory/knowledge/nakano-koya.md

対象:
  - memory/knowledge/*.md
  - memory/mid-term/*.md
  - ayumu-lab/research/*.md
"""

import os
import re
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
api_key = None
for key_name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_AI_API_KEY"):
    val = os.environ.get(key_name, "")
    if val and not val.startswith("encrypted:"):
        api_key = val
        break
if not api_key:
    raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY not found.")
client = genai.Client(api_key=api_key)


def load_embeddings():
    """保存済みEmbeddingを読み込み"""
    with open(INDEX_FILE) as f:
        index = json.load(f)
    vectors = np.load(VECTORS_FILE)
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


def find_related(query_embedding: np.ndarray, vectors: np.ndarray,
                 index: dict, reverse_index: dict,
                 exclude_id: str, top_n: int = 20) -> list[tuple[str, float]]:
    """関連記憶を検索（メタデータ除外）"""
    similarities = []

    for idx in range(len(vectors)):
        if idx not in reverse_index:
            continue
        memory_id = reverse_index[idx]

        # 自分自身を除外
        if memory_id == exclude_id:
            continue

        # creations, bucket-listを除外
        if "all-creations.json" in memory_id or "bucket-list.json" in memory_id:
            continue

        sim = cosine_similarity(query_embedding, vectors[idx])
        similarities.append((memory_id, sim))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_n]


def verify_with_gemini(query_text: str, candidates: list[tuple[str, float]]) -> list[dict]:
    """Geminiで関連性を確認（新SDK）"""

    # 候補の内容を取得
    candidate_texts = []
    for memory_id, score in candidates:
        content = get_memory_content(memory_id)
        if not content:
            continue
        candidate_texts.append({
            "id": memory_id,
            "score": score,
            "content": content[:500]
        })

    if not candidate_texts:
        return []

    prompt = f"""以下のクエリテキストと、候補となる記憶のリストがあります。
各候補が本当にクエリと関連があるかを判定してください。
「関連がある」とは、同じトピック、同じ人物、同じ場所、同じイベント、同じ技術などを指します。

クエリ:
{query_text[:1500]}

候補:
{json.dumps(candidate_texts, ensure_ascii=False, indent=2)}

各候補について、以下のJSON形式で回答してください:
[
  {{"id": "...", "is_related": true/false, "reason": "関連性の理由（10文字以内）"}}
]
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
        return result
    except:
        return []


def get_memory_content(memory_id: str) -> str:
    """記憶IDからコンテンツを取得"""
    if memory_id.endswith(".md"):
        path = REPO_ROOT / memory_id
        if path.exists():
            return path.read_text(encoding="utf-8")
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
                        return f"{data.get('type', '')}: {data.get('description', '')}"
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
                    return f"{item.get('title', '')}: {item.get('content', '')}"
        return ""

    return ""


def format_link(memory_id: str) -> str:
    """記憶IDをObsidian風リンクに変換

    形式: [[path:key:value]] または [[path/to/file.md]]
    例:
      - [[memory/knowledge/nakano-koya.md]]
      - [[memory/experiences.jsonl:timestamp:2025-12-03T01:30:00]]
      - [[memory/diary.json:datetime:2025-12-03 03:13:14]]
    """
    # memory_idをそのまま使用（すでにpath:key:value形式になっている）
    return f"[[{memory_id}]]"


def remove_related_section(content: str) -> str:
    """既存のRelated Memoriesセクションを削除"""
    # ## Related Memories から次の## または末尾まで削除
    pattern = r'\n## Related Memories\n.*?(?=\n## |\Z)'
    return re.sub(pattern, '', content, flags=re.DOTALL)


def add_related_section(content: str, related: list[dict]) -> str:
    """Related Memoriesセクションを追加"""
    if not related:
        return content

    # 既存のセクションを削除
    content = remove_related_section(content)

    # 新しいセクションを作成
    lines = ["\n## Related Memories\n"]
    for r in related:
        link = format_link(r["id"])
        reason = r.get("reason", "")
        if reason:
            lines.append(f"- {link} - {reason}")
        else:
            lines.append(f"- {link}")

    # 末尾に追加
    return content.rstrip() + "\n" + "\n".join(lines) + "\n"


def collect_md_files() -> list[Path]:
    """対象のMarkdownファイルを収集"""
    files = []
    patterns = [
        ("memory/knowledge", "*.md"),
        ("memory/mid-term", "*.md"),
        ("ayumu-lab/research", "*.md"),
    ]

    for dir_path, pattern in patterns:
        full_path = REPO_ROOT / dir_path
        if full_path.exists():
            for f in full_path.glob(pattern):
                if f.name.startswith("README"):
                    continue
                files.append(f)

    return files


def process_file(file_path: Path, index: dict, reverse_index: dict,
                 vectors: np.ndarray, dry_run: bool = True) -> bool:
    """ファイルを処理してリンクを挿入"""
    # 絶対パスに変換
    file_path = file_path.resolve()
    if not file_path.is_relative_to(REPO_ROOT):
        file_path = REPO_ROOT / file_path
    rel_path = str(file_path.relative_to(REPO_ROOT))
    content = file_path.read_text(encoding="utf-8")

    print(f"\n📄 Processing: {rel_path}", flush=True)

    # Embedding生成
    query_embedding = generate_query_embedding(content)

    # 関連記憶検索（候補多め）
    candidates = find_related(query_embedding, vectors, index, reverse_index,
                             exclude_id=rel_path, top_n=20)

    if not candidates:
        print("   No candidates found", flush=True)
        return False

    # Gemini確認
    verified = verify_with_gemini(content[:2000], candidates)

    # 関連ありのみ抽出
    related = [v for v in verified if v.get("is_related")][:5]

    if not related:
        print("   No related memories found", flush=True)
        return False

    print(f"   Found {len(related)} related memories:", flush=True)
    for r in related:
        print(f"     - {r['id'][:50]}... ({r.get('reason', 'N/A')})", flush=True)

    # 新しいコンテンツを生成
    new_content = add_related_section(content, related)

    if dry_run:
        print("   [DRY RUN] Would update file", flush=True)
    else:
        file_path.write_text(new_content, encoding="utf-8")
        print("   ✅ Updated file", flush=True)

    return True


def main():
    parser = argparse.ArgumentParser(description="既存memoryにリンクを挿入")
    parser.add_argument("--dry-run", action="store_true", help="変更を実行せずに確認のみ")
    parser.add_argument("--file", help="特定のファイルのみ処理")
    args = parser.parse_args()

    print("🔗 Related Memories Link Insertion", flush=True)
    print(f"   Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}", flush=True)

    # Embedding読み込み
    print("\n📚 Loading embeddings...", flush=True)
    index, reverse_index, vectors = load_embeddings()
    print(f"   Loaded {len(index)} embeddings", flush=True)

    # ファイル収集
    if args.file:
        files = [Path(args.file)]
    else:
        files = collect_md_files()

    print(f"\n📁 Processing {len(files)} files...", flush=True)

    updated = 0
    for file_path in files:
        try:
            if process_file(file_path, index, reverse_index, vectors, args.dry_run):
                updated += 1
        except Exception as e:
            print(f"   ⚠️ Error: {e}", flush=True)

    print(f"\n✅ Done! {'Would update' if args.dry_run else 'Updated'}: {updated}/{len(files)} files")


if __name__ == "__main__":
    main()
