#!/usr/bin/env python3
"""
Phase 1: 記憶のEmbedding生成

対象:
- memory/knowledge/*.md
- ayumu-lab/research/*.md
- memory/mid-term/*.md
- TOMOYOSHI.md
- memory/experiences.jsonl
- memory/diary.json
- memory/goals.json
- docs/data/all-creations.json
- docs/data/articles.json

出力:
- memory/embeddings/vectors.npy - Embeddingベクトル
- memory/embeddings/index.json - ID→インデックスのマッピング
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
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
CACHE_FILE = EMBEDDINGS_DIR / "cache.json"  # ファイルハッシュキャッシュ

# Gemini設定（新しいSDK）
api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY not found. Please set it in .env file.")
client = genai.Client(api_key=api_key)


def get_file_hash(content: str) -> str:
    """コンテンツのハッシュを計算"""
    return hashlib.md5(content.encode()).hexdigest()


def load_cache() -> dict:
    """キャッシュを読み込み"""
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    """キャッシュを保存"""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def contextualize_knowledge(content: str) -> str:
    """knowledge/*.mdの内容にタグ・リンク情報を文脈として付加（Contextual Retrieval）

    MDファイルのタグ（#tech #workflow等）と内部リンク（[[...]]）を抽出して
    文脈ヘッダーとして付加。検索時にタグやリンク関係で見つかりやすくなる。
    """
    import re

    # タグ抽出（#で始まるワード、ただしMarkdown見出しの # は除外）
    tags = re.findall(r'(?:^|\s)(#[a-zA-Z]\w+)', content)
    # 内部リンク抽出 [[...]]
    links = re.findall(r'\[\[([^\]]+)\]\]', content)
    # タイトル抽出（最初の # 見出し行）
    title_match = re.match(r'^#\s+(.+)', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    context_parts = []
    if title:
        context_parts.append(f"タイトル: {title}")
    if tags:
        context_parts.append(f"タグ: {' '.join(set(tags))}")
    if links:
        context_parts.append(f"関連ファイル: {', '.join(links[:10])}")

    if context_parts:
        context = "\n".join(context_parts)
        return f"[文脈]\n{context}\n\n{content}"
    return content


def collect_md_files() -> list[dict]:
    """Markdownファイルを収集（knowledge/*はContextual Retrieval対応）"""
    entries = []

    # 対象パターン
    patterns = [
        ("memory/knowledge", "*.md"),
        ("ayumu-lab/research", "*.md"),
        ("memory/mid-term", "*.md"),
    ]

    for dir_path, pattern in patterns:
        full_path = REPO_ROOT / dir_path
        if full_path.exists():
            for f in full_path.glob(pattern):
                if f.name.startswith("README"):
                    continue
                rel_path = str(f.relative_to(REPO_ROOT))
                raw_content = f.read_text(encoding="utf-8")
                # knowledge/*.mdにはCR文脈を付加
                if dir_path == "memory/knowledge":
                    content = contextualize_knowledge(raw_content)
                else:
                    content = raw_content
                entries.append({
                    "id": rel_path,
                    "type": "md",
                    "content": content[:8000],  # 長すぎる場合は切り詰め
                    "mtime": f.stat().st_mtime
                })

    # Partner profile (PARTNER.md or similar)
    for partner_file in ["PARTNER.md", "TOMOYOSHI.md"]:
        pf = REPO_ROOT / partner_file
        if pf.exists():
            content = pf.read_text(encoding="utf-8")
            entries.append({
                "id": partner_file,
                "type": "md",
                "content": content[:8000],
                "mtime": pf.stat().st_mtime
            })
            break

    return entries


def contextualize_experience(all_data: list[dict], idx: int) -> str:
    """experiences.jsonlの1エントリに前後の文脈を付加（Contextual Retrieval）

    各エントリに前後2件の活動要約と日付を付加することで、
    embeddingが時間的文脈を保持し、検索精度が向上する。
    API課金不要（メカニカルな文脈付加）。
    """
    entry = all_data[idx]
    current = f"{entry.get('type', '')}: {entry.get('description', '')}"
    if entry.get("metadata"):
        current += f" metadata: {json.dumps(entry['metadata'], ensure_ascii=False)}"

    context_parts = []
    for delta in [-2, -1]:
        j = idx + delta
        if 0 <= j < len(all_data):
            e = all_data[j]
            ts = e.get("timestamp", "")[:16]
            context_parts.append(f"[前{abs(delta)}] {ts} {e.get('type', '')}: {e.get('description', '')[:80]}")
    for delta in [1, 2]:
        j = idx + delta
        if 0 <= j < len(all_data):
            e = all_data[j]
            ts = e.get("timestamp", "")[:16]
            context_parts.append(f"[後{delta}] {ts} {e.get('type', '')}: {e.get('description', '')[:80]}")

    date_str = entry.get("timestamp", "")[:10]
    context = "\n".join(context_parts)
    return f"[日付:{date_str}] 前後の活動:\n{context}\n\n{current}"


def collect_jsonl_entries() -> list[dict]:
    """experiences.jsonlを収集（Contextual Retrieval対応）"""
    entries = []
    jsonl_file = REPO_ROOT / "memory" / "experiences.jsonl"

    if jsonl_file.exists():
        all_data = []
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    all_data.append(json.loads(line))

        for idx, data in enumerate(all_data):
            timestamp = data.get("timestamp", "")
            entry_id = f"memory/experiences.jsonl:timestamp:{timestamp}"
            content = contextualize_experience(all_data, idx)
            entries.append({
                "id": entry_id,
                "type": "jsonl",
                "content": content[:2000],
                "mtime": jsonl_file.stat().st_mtime
            })

    return entries


def contextualize_diary(all_diary: list[dict], idx: int) -> str:
    """diary.jsonの1エントリに前後の日記文脈を付加（Contextual Retrieval）

    各日記エントリに前後1件の日記タイトル・日付を付加することで、
    embeddingが時間的文脈を保持し、検索精度が向上する。
    """
    entry = all_diary[idx]
    current = f"{entry.get('title', '')}: {entry.get('content', '')}"

    context_parts = []
    for delta in [-1]:
        j = idx + delta
        if 0 <= j < len(all_diary):
            e = all_diary[j]
            dt = e.get("datetime", e.get("date", ""))[:10]
            context_parts.append(f"[前日記] {dt} {e.get('title', '')}")
    for delta in [1]:
        j = idx + delta
        if 0 <= j < len(all_diary):
            e = all_diary[j]
            dt = e.get("datetime", e.get("date", ""))[:10]
            context_parts.append(f"[次日記] {dt} {e.get('title', '')}")

    date_str = entry.get("datetime", entry.get("date", ""))[:10]
    time_period = entry.get("time_period", "")
    context = "\n".join(context_parts)
    if context:
        return f"[日記 {date_str} {time_period}] 前後:\n{context}\n\n{current}"
    return f"[日記 {date_str} {time_period}]\n{current}"


def collect_json_entries() -> list[dict]:
    """JSONファイルを収集（diary.jsonはContextual Retrieval対応）"""
    entries = []

    # diary.json
    diary_file = REPO_ROOT / "memory" / "diary.json"
    if diary_file.exists():
        with open(diary_file, encoding="utf-8") as f:
            diary = json.load(f)
        for idx, item in enumerate(diary):
            dt = item.get("datetime", item.get("date", ""))
            entry_id = f"memory/diary.json:datetime:{dt}"
            content = contextualize_diary(diary, idx)
            entries.append({
                "id": entry_id,
                "type": "json",
                "content": content[:2000],
                "mtime": diary_file.stat().st_mtime
            })

    # goals.json
    goals_file = REPO_ROOT / "memory" / "goals.json"
    if goals_file.exists():
        with open(goals_file, encoding="utf-8") as f:
            goals = json.load(f)
        for category in ["short_term", "long_term", "completed"]:
            for item in goals.get(category, []):
                goal = item.get("goal", "")
                entry_id = f"memory/goals.json:goal:{goal[:50]}"
                content = f"{category}: {goal}. {item.get('notes', '')}"
                entries.append({
                    "id": entry_id,
                    "type": "json",
                    "content": content[:2000],
                    "mtime": goals_file.stat().st_mtime
                })

    # all-creations.json
    creations_file = REPO_ROOT / "docs" / "data" / "all-creations.json"
    if creations_file.exists():
        with open(creations_file, encoding="utf-8") as f:
            creations = json.load(f)
        for item in creations.get("creations", []):
            item_id = item.get("id", "")
            entry_id = f"docs/data/all-creations.json:id:{item_id}"
            content = f"{item.get('title', '')}: {item.get('description', '')} category:{item.get('category', '')} date:{item.get('date', '')}"
            entries.append({
                "id": entry_id,
                "type": "json",
                "content": content[:2000],
                "mtime": creations_file.stat().st_mtime
            })

    # articles.json（技術記事）
    articles_file = REPO_ROOT / "docs" / "data" / "articles.json"
    if articles_file.exists():
        with open(articles_file, encoding="utf-8") as f:
            articles = json.load(f)
        for article in articles:
            article_id = article.get("id", "")
            entry_id = f"docs/data/articles.json:id:{article_id}"
            content = f"{article.get('title', '')}: {article.get('summary', '')} tags:{','.join(article.get('tags', []))} date:{article.get('date', '')}"
            entries.append({
                "id": entry_id,
                "type": "json",
                "content": content[:2000],
                "mtime": articles_file.stat().st_mtime
            })

    return entries


def generate_embedding(text: str) -> list[float]:
    """Gemini gemini-embedding-001でEmbedding生成（最新モデル、3072次元）"""
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config={"task_type": "RETRIEVAL_DOCUMENT"}
    )
    return result.embeddings[0].values


def main():
    print("🧠 記憶のEmbedding生成を開始...", flush=True)

    # ディレクトリ作成
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

    # 全エントリ収集
    print("📚 記憶を収集中...", flush=True)
    all_entries = []
    all_entries.extend(collect_md_files())
    all_entries.extend(collect_jsonl_entries())
    all_entries.extend(collect_json_entries())

    print(f"   合計: {len(all_entries)} 件", flush=True)

    # キャッシュ読み込み
    cache = load_cache()

    # 既存のindex/vectorsを読み込み
    existing_index = {}
    existing_vectors = []
    if INDEX_FILE.exists() and VECTORS_FILE.exists():
        with open(INDEX_FILE) as f:
            existing_index = json.load(f)
        existing_vectors = np.load(VECTORS_FILE).tolist()

    # 新しいindex/vectors
    new_index = {}
    new_vectors = []

    # 処理
    processed = 0
    skipped = 0

    # --force-type オプション: 指定タイプのエントリを強制再生成
    force_types = set()
    import sys
    if "--force-type" in sys.argv:
        idx_arg = sys.argv.index("--force-type")
        if idx_arg + 1 < len(sys.argv):
            force_types = set(sys.argv[idx_arg + 1].split(","))
            print(f"   ⚡ 強制再生成: type={force_types}", flush=True)

    for entry in all_entries:
        entry_id = entry["id"]
        content_hash = get_file_hash(entry["content"])

        # 強制再生成対象かチェック
        force_regen = entry.get("type", "") in force_types

        # 既存のベクトルがあれば再利用（IDベースで判定）
        if entry_id in existing_index and not force_regen:
            idx = existing_index[entry_id]
            if idx < len(existing_vectors):
                new_index[entry_id] = len(new_vectors)
                new_vectors.append(existing_vectors[idx])
                skipped += 1
                continue

        # 新規生成（indexにないIDのみ）
        try:
            embedding = generate_embedding(entry["content"])
            new_index[entry_id] = len(new_vectors)
            new_vectors.append(embedding)
            cache[entry_id] = {"hash": content_hash, "mtime": entry["mtime"]}
            processed += 1

            if processed % 50 == 0:
                print(f"   処理中... {processed} 件完了", flush=True)
                # 途中保存
                save_cache(cache)

        except Exception as e:
            print(f"   ⚠️ エラー: {entry_id}: {e}", flush=True)

    # 保存
    print(f"\n💾 保存中...", flush=True)
    with open(INDEX_FILE, "w") as f:
        json.dump(new_index, f, indent=2, ensure_ascii=False)

    np.save(VECTORS_FILE, np.array(new_vectors))
    save_cache(cache)

    print(f"\n✅ 完了!")
    print(f"   新規生成: {processed} 件")
    print(f"   キャッシュ利用: {skipped} 件")
    print(f"   合計ベクトル数: {len(new_vectors)}")
    print(f"   保存先: {EMBEDDINGS_DIR}")


if __name__ == "__main__":
    main()
