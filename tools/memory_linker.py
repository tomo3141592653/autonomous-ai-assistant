#!/usr/bin/env python3
"""
関連記憶自動検索モジュール

update_diary.py, update_experiences.py, update_working_memory_links.pyから呼び出されて、
新しいエントリに対して自動的に関連記憶を検索・付与する。

品質基準（insert_related_links.pyと同等）:
- 候補20件をEmbedding類似度で取得
- Geminiで関連性を確認・フィルタリング
- 最大5件を理由付きで返す
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# .env読み込み
load_dotenv()

# 設定
REPO_ROOT = Path(__file__).parent.parent
EMBEDDINGS_DIR = REPO_ROOT / "memory" / "embeddings"
INDEX_FILE = EMBEDDINGS_DIR / "index.json"
VECTORS_FILE = EMBEDDINGS_DIR / "vectors.npy"

# Gemini設定（遅延初期化）
_genai = None
_embeddings_cache = None


def _init_genai():
    """Gemini APIを遅延初期化（新SDK: google-genai）"""
    global _genai
    if _genai is None:
        from google import genai
        api_key = None
        for key_name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_AI_API_KEY"):
            val = os.environ.get(key_name, "")
            if val and not val.startswith("encrypted:"):
                api_key = val
                break
        if not api_key:
            return None
        _genai = genai.Client(api_key=api_key)
    return _genai


def _load_embeddings():
    """Embeddingsを読み込み（キャッシュ）"""
    global _embeddings_cache
    if _embeddings_cache is not None:
        return _embeddings_cache

    if not INDEX_FILE.exists() or not VECTORS_FILE.exists():
        return None

    import numpy as np
    with open(INDEX_FILE) as f:
        index = json.load(f)
    vectors = np.load(VECTORS_FILE)
    reverse_index = {v: k for k, v in index.items()}

    _embeddings_cache = (index, reverse_index, vectors)
    return _embeddings_cache


def find_related_memories(text: str, top_n: int = 5, exclude_id: str = None, exclude_ids: list[str] = None) -> list[dict]:
    """
    テキストに関連する記憶を検索

    Args:
        text: 検索元テキスト
        top_n: 最終的に返す件数（デフォルト5件）
        exclude_id: 除外する記憶ID（自分自身を除外する場合）
        exclude_ids: 除外する記憶IDのリスト（複数除外する場合）

    Returns:
        関連記憶のリスト。各要素は {"id": "...", "reason": "..."} の辞書

    Note:
        exclude_id または exclude_ids で自分自身のIDを渡すこと。
        自己リンク防止のため。
    """
    # exclude_idsにexclude_idも含める
    all_excludes = set(exclude_ids or [])
    if exclude_id:
        all_excludes.add(exclude_id)
    import numpy as np

    # Gemini初期化
    genai = _init_genai()
    if genai is None:
        print("   ⚠️ Gemini API key not found", flush=True)
        return []

    # Embeddings読み込み
    embeddings = _load_embeddings()
    if embeddings is None:
        print("   ⚠️ Embeddings not found, run generate_embeddings.py first", flush=True)
        return []

    index, reverse_index, vectors = embeddings

    # クエリEmbedding生成（新SDK: client.models.embed_content）
    try:
        result = genai.models.embed_content(
            model="gemini-embedding-001",
            contents=text[:8000],
            config={"task_type": "RETRIEVAL_QUERY"}
        )
        query_embedding = np.array(result.embeddings[0].values)
    except Exception as e:
        print(f"   ⚠️ Embedding生成失敗: {e}", flush=True)
        return []

    # コサイン類似度で検索（候補20件）
    def cosine_similarity(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    similarities = []
    for idx in range(len(vectors)):
        if idx not in reverse_index:
            continue
        memory_id = reverse_index[idx]

        # 自分自身を除外
        if memory_id in all_excludes:
            continue

        # リンク先候補から除外
        # - working_memory: 短期記憶なのでリンク先として不適切
        # - bucket-list: HTMLページの付随データ
        if "bucket-list.json" in memory_id:
            continue
        if "working_memory" in memory_id:
            continue

        sim = cosine_similarity(query_embedding, vectors[idx])
        similarities.append((memory_id, sim))

    # 上位20件を取得
    similarities.sort(key=lambda x: x[1], reverse=True)
    candidates = similarities[:20]

    if not candidates:
        return []

    # Geminiで関連性を確認
    try:
        verified = _verify_with_gemini(text, candidates, genai)
        # is_related=Trueのもののみ返す（最大top_n件）
        result = []
        for v in verified:
            # vがdictでない場合はスキップ
            if not isinstance(v, dict):
                continue
            if v.get("is_related"):
                result.append({"id": v.get("id", ""), "reason": v.get("reason", "")})
                if len(result) >= top_n:
                    break
        return result
    except Exception as e:
        print(f"   ⚠️ Gemini確認失敗: {e}", flush=True)
        return []


def _verify_with_gemini(query_text: str, candidates: list, genai) -> list[dict]:
    """Geminiで関連性を確認（新SDK: client.models.generate_content）"""

    # 候補の内容を取得
    candidate_texts = []
    query_normalized = query_text.strip()[:500]  # 比較用に正規化
    for memory_id, score in candidates:
        content = _get_memory_content(memory_id)
        if not content:
            continue
        # 自己リンク防止: 内容が一致したらスキップ
        if content.strip()[:500] == query_normalized:
            continue
        candidate_texts.append({
            "id": memory_id,
            "score": float(score),
            "content": content[:500]
        })

    if not candidate_texts:
        return []

    prompt = f"""以下のクエリテキストと、候補となる記憶のリストがあります。
各候補がクエリと**意味のある関連**があるかを判定してください。

**関連ありと判定する基準**:
- 同じ作家・作品について言及している
- 同じ技術・概念を扱っている
- 同じプロジェクト・イベントの一部
- 因果関係がある（Aの結果がB、AがBにインスパイア）
- 同じ人物について言及している

**関連なしと判定する基準**:
- 単に同じ日付というだけ
- 単に同じカテゴリ（メンテナンス同士など）というだけ
- 表面的なキーワード一致のみ

クエリ:
{query_text[:1500]}

候補:
{json.dumps(candidate_texts, ensure_ascii=False, indent=2)}

各候補について、以下のJSON形式で回答してください。reasonは「なぜ読者がこのリンクを辿りたいか」が分かる具体的な説明にしてください:
[
  {{"id": "...", "is_related": true/false, "reason": "関連性の具体的理由（50文字以内）"}}
]
"""

    response = genai.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # JSONパースに失敗した場合は空リストを返す
        return []

    # 結果を正規化
    # 1. dictでラップされている場合（{"results": [...]}など）
    if isinstance(result, dict):
        # "results", "items", "data"などのキーを探す
        for key in ["results", "items", "data", "candidates"]:
            if key in result and isinstance(result[key], list):
                result = result[key]
                break
        else:
            return []

    # 2. ネストされたリストの場合（[[...]] や [[...], [...], ...]）
    if isinstance(result, list):
        # フラット化: 各要素がリストならアンラップ
        flattened = []
        for item in result:
            if isinstance(item, list):
                flattened.extend(item)
            else:
                flattened.append(item)
        result = flattened

    # 最終チェック
    if not isinstance(result, list):
        return []

    return result


def _get_memory_content(memory_id: str) -> str:
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

    elif ":id:" in memory_id and "all-creations.json" in memory_id:
        parts = memory_id.split(":id:")
        creation_id = parts[1]
        json_path = REPO_ROOT / "docs" / "data" / "all-creations.json"
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("creations", []):
                if item.get("id") == creation_id:
                    return f"{item.get('title', '')}: {item.get('description', '')} (category: {item.get('category', '')})"
        return ""

    elif "goals.json:" in memory_id:
        # memory/goals.json:goal:目標の説明... の形式
        # "goal"は固定文字列で、カテゴリではない
        parts = memory_id.split(":goal:", 1)
        if len(parts) >= 2:
            goal_prefix = parts[1]
            json_path = REPO_ROOT / "memory" / "goals.json"
            if json_path.exists():
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
                # 全カテゴリを検索
                for category in ["short_term", "long_term", "completed"]:
                    for item in data.get(category, []):
                        if item.get("goal", "").startswith(goal_prefix):
                            notes = item.get("notes", "")
                            return f"{category}: {item.get('goal', '')}" + (f" - {notes}" if notes else "")
        return ""

    elif ":id:" in memory_id and "articles.json" in memory_id:
        # docs/data/articles.json:id:article-id の形式
        parts = memory_id.split(":id:")
        article_id = parts[1]
        json_path = REPO_ROOT / "docs" / "data" / "articles.json"
        if json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("articles", []):
                if item.get("id") == article_id:
                    return f"{item.get('title', '')}: {item.get('description', '')}"
        return ""

    return ""


def add_reverse_links(source_id: str, related_memories: list[dict]) -> dict:
    """
    関連記憶に逆リンクを追加

    Args:
        source_id: リンク元のID (例: "memory/diary.json:datetime:2025-12-07 00:01:59")
        related_memories: 関連記憶のリスト [{"id": "...", "reason": "..."}, ...]

    Returns:
        結果 {"updated_md": [...], "updated_diary": [...], "updated_experiences": [...]}
    """
    result = {"updated_md": [], "updated_diary": [], "updated_experiences": [], "updated_creations": [], "updated_goals": [], "updated_articles": []}

    for item in related_memories:
        target_id = item["id"]
        reason = item.get("reason", "")
        reverse_reason = f"被リンク:{reason}" if reason else "被リンク"

        # Markdownファイルの場合
        if target_id.endswith(".md"):
            if _add_reverse_link_to_md(target_id, source_id, reverse_reason):
                result["updated_md"].append(target_id)

        # diary.jsonの場合
        elif ":datetime:" in target_id:
            if _add_reverse_link_to_diary(target_id, source_id, reverse_reason):
                result["updated_diary"].append(target_id)

        # experiences.jsonlの場合
        elif ":timestamp:" in target_id:
            if _add_reverse_link_to_experiences(target_id, source_id, reverse_reason):
                result["updated_experiences"].append(target_id)

        # all-creations.jsonの場合
        elif ":id:" in target_id and "all-creations.json" in target_id:
            if _add_reverse_link_to_creations(target_id, source_id, reverse_reason):
                result["updated_creations"].append(target_id)

        # goals.jsonの場合
        elif "goals.json:" in target_id:
            if _add_reverse_link_to_goals(target_id, source_id, reverse_reason):
                result["updated_goals"].append(target_id)

        # articles.jsonの場合
        elif "articles.json:" in target_id:
            if _add_reverse_link_to_articles(target_id, source_id, reverse_reason):
                result["updated_articles"].append(target_id)

    return result


def _add_reverse_link_to_md(target_id: str, source_id: str, reason: str) -> bool:
    """Markdownファイルに逆リンクを追加"""
    import re

    path = REPO_ROOT / target_id
    if not path.exists():
        return False

    content = path.read_text(encoding="utf-8")

    # 既に同じリンクがあればスキップ
    if source_id in content:
        return False

    # Related Memoriesセクションがあるか確認
    if "## Related Memories" in content:
        # セクションの末尾にリンクを追加
        pattern = r'(## Related Memories\n.*?)(\n## |\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            section = match.group(1).rstrip()
            new_link = f"\n- [[{source_id}]] - {reason}"
            new_content = content[:match.start(1)] + section + new_link + "\n" + content[match.start(2):]
            path.write_text(new_content, encoding="utf-8")
            return True
    else:
        # セクションがなければ末尾に追加
        new_section = f"\n\n## Related Memories\n\n- [[{source_id}]] - {reason}\n"
        path.write_text(content.rstrip() + new_section, encoding="utf-8")
        return True

    return False


def _add_reverse_link_to_diary(target_id: str, source_id: str, reason: str) -> bool:
    """diary.jsonのエントリに逆リンクを追加"""
    parts = target_id.split(":datetime:")
    if len(parts) != 2:
        return False
    datetime_val = parts[1]

    diary_path = REPO_ROOT / "memory" / "diary.json"
    public_diary_path = REPO_ROOT / "docs" / "data" / "diary.json"

    if not diary_path.exists():
        return False

    with open(diary_path, encoding="utf-8") as f:
        entries = json.load(f)

    updated = False
    for entry in entries:
        if entry.get("datetime") == datetime_val:
            # related_memoriesを取得または初期化
            related = entry.get("related_memories", [])

            # 既存のIDを抽出（文字列/オブジェクト両対応）
            existing_ids = []
            for r in related:
                if isinstance(r, dict):
                    existing_ids.append(r.get("id", ""))
                else:
                    existing_ids.append(r)

            # 既に同じリンクがあればスキップ
            if source_id in existing_ids:
                return False

            # オブジェクト形式で追加
            related.append({"id": source_id, "reason": reason})
            entry["related_memories"] = related
            updated = True
            break

    if updated:
        with open(diary_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        # 公開用にもコピー
        with open(public_diary_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        return True

    return False


def add_to_embedding_db(entry_id: str, content: str) -> bool:
    """
    新しいエントリをEmbedding DBに追加

    Args:
        entry_id: エントリID (例: "memory/diary.json:datetime:2025-12-07 00:01:59")
        content: エントリの内容

    Returns:
        成功したかどうか
    """
    import numpy as np
    import hashlib

    # Gemini初期化
    genai = _init_genai()
    if genai is None:
        print("   ⚠️ Gemini API key not found", flush=True)
        return False

    # 既存のindex/vectorsを読み込み
    if not INDEX_FILE.exists() or not VECTORS_FILE.exists():
        print("   ⚠️ Embedding DB not found", flush=True)
        return False

    with open(INDEX_FILE) as f:
        index = json.load(f)
    vectors = np.load(VECTORS_FILE).tolist()

    # 既に存在する場合はスキップ
    if entry_id in index:
        return False

    # Embedding生成（新SDK: client.models.embed_content）
    try:
        result = genai.models.embed_content(
            model="gemini-embedding-001",
            contents=content[:8000],
            config={"task_type": "RETRIEVAL_DOCUMENT"}
        )
        embedding = result.embeddings[0].values
    except Exception as e:
        print(f"   ⚠️ Embedding生成失敗: {e}", flush=True)
        return False

    # 追加
    index[entry_id] = len(vectors)
    vectors.append(embedding)

    # 保存
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    np.save(VECTORS_FILE, np.array(vectors))

    # キャッシュも更新
    cache_file = EMBEDDINGS_DIR / "cache.json"
    cache = {}
    if cache_file.exists():
        with open(cache_file) as f:
            cache = json.load(f)
    content_hash = hashlib.md5(content[:8000].encode()).hexdigest()
    cache[entry_id] = {"hash": content_hash, "mtime": 0}
    with open(cache_file, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

    # グローバルキャッシュをクリア（次回の検索で新しいデータを読むため）
    global _embeddings_cache
    _embeddings_cache = None

    return True


def _add_reverse_link_to_experiences(target_id: str, source_id: str, reason: str) -> bool:
    """experiences.jsonlのエントリに逆リンクを追加"""
    parts = target_id.split(":timestamp:")
    if len(parts) != 2:
        return False
    timestamp_val = parts[1]

    exp_path = REPO_ROOT / "memory" / "experiences.jsonl"
    if not exp_path.exists():
        return False

    # 全エントリを読み込み
    entries = []
    with open(exp_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))

    updated = False
    for entry in entries:
        if entry.get("timestamp") == timestamp_val:
            # related_memoriesを取得または初期化
            related = entry.get("related_memories", [])

            # 既存のIDを抽出（文字列/オブジェクト両対応）
            existing_ids = []
            for r in related:
                if isinstance(r, dict):
                    existing_ids.append(r.get("id", ""))
                else:
                    existing_ids.append(r)

            # 既に同じリンクがあればスキップ
            if source_id in existing_ids:
                return False

            # オブジェクト形式で追加
            related.append({"id": source_id, "reason": reason})
            entry["related_memories"] = related
            updated = True
            break

    if updated:
        with open(exp_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True

    return False


def _add_reverse_link_to_creations(target_id: str, source_id: str, reason: str) -> bool:
    """all-creations.jsonのエントリに逆リンクを追加"""
    parts = target_id.split(":id:")
    if len(parts) != 2:
        return False
    creation_id = parts[1]

    creations_path = REPO_ROOT / "docs" / "data" / "all-creations.json"
    if not creations_path.exists():
        return False

    with open(creations_path, encoding="utf-8") as f:
        data = json.load(f)

    updated = False
    for entry in data.get("creations", []):
        if entry.get("id") == creation_id:
            # related_memoriesを取得または初期化
            related = entry.get("related_memories", [])

            # 既存のIDを抽出（文字列/オブジェクト両対応）
            existing_ids = []
            for r in related:
                if isinstance(r, dict):
                    existing_ids.append(r.get("id", ""))
                else:
                    existing_ids.append(r)

            # 既に同じリンクがあればスキップ
            if source_id in existing_ids:
                return False

            # オブジェクト形式で追加
            related.append({"id": source_id, "reason": reason})
            entry["related_memories"] = related
            updated = True
            break

    if updated:
        with open(creations_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True

    return False


def _add_reverse_link_to_goals(target_id: str, source_id: str, reason: str) -> bool:
    """goals.jsonのエントリに逆リンクを追加"""
    # memory/goals.json:goal:目標の説明... の形式
    parts = target_id.split(":", 2)
    if len(parts) < 3:
        return False
    category = parts[1]
    goal_prefix = parts[2]

    goals_path = REPO_ROOT / "memory" / "goals.json"
    if not goals_path.exists():
        return False

    with open(goals_path, encoding="utf-8") as f:
        data = json.load(f)

    updated = False
    for entry in data.get(category, []):
        if entry.get("goal", "").startswith(goal_prefix):
            # related_memoriesを取得または初期化
            related = entry.get("related_memories", [])

            # 既存のIDを抽出（文字列/オブジェクト両対応）
            existing_ids = []
            for r in related:
                if isinstance(r, dict):
                    existing_ids.append(r.get("id", ""))
                else:
                    existing_ids.append(r)

            # 既に同じリンクがあればスキップ
            if source_id in existing_ids:
                return False

            # オブジェクト形式で追加
            related.append({"id": source_id, "reason": reason})
            entry["related_memories"] = related
            updated = True
            break

    if updated:
        with open(goals_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True

    return False


def _add_reverse_link_to_articles(target_id: str, source_id: str, reason: str) -> bool:
    """articles.jsonのエントリに逆リンクを追加"""
    # docs/data/articles.json:id:article-id の形式
    parts = target_id.split(":id:", 1)
    if len(parts) < 2:
        return False
    article_id = parts[1]

    articles_path = REPO_ROOT / "docs" / "data" / "articles.json"
    if not articles_path.exists():
        return False

    with open(articles_path, encoding="utf-8") as f:
        data = json.load(f)

    updated = False
    for entry in data:
        if entry.get("id") == article_id:
            # related_memoriesを取得または初期化
            related = entry.get("related_memories", [])

            # 文字列形式の場合もあるので、dictに変換して確認
            existing_ids = []
            for r in related:
                if isinstance(r, dict):
                    existing_ids.append(r.get("id", ""))
                else:
                    existing_ids.append(r)

            # 既に同じリンクがあればスキップ
            if source_id in existing_ids:
                return False

            # dictとして追加
            related.append({"id": source_id, "reason": reason})
            entry["related_memories"] = related
            updated = True
            break

    if updated:
        with open(articles_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True

    return False
