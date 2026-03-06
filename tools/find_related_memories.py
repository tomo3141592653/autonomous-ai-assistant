#!/usr/bin/env python3
"""
Semantic memory search using local embeddings.

Searches across all memory sources (experiences, diary, knowledge, mid-term)
using vector similarity. No external API required — runs entirely offline.

Usage:
    # Search by text query
    python tools/find_related_memories.py --text "what did I learn about Python async?"

    # Search with more results
    python tools/find_related_memories.py --text "email from partner" --top 10

    # Filter by source type
    python tools/find_related_memories.py --text "project status" --source diary,knowledge

    # Rebuild the embedding index
    python tools/find_related_memories.py --rebuild

Requirements:
    pip install sentence-transformers numpy
    # or: uv add sentence-transformers numpy

First run will download the embedding model (~90MB, cached locally).
Subsequent runs are fast.
"""

import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False


# ── Configuration ─────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
EMBEDDINGS_DIR = REPO_ROOT / 'memory' / 'embeddings'
INDEX_FILE = EMBEDDINGS_DIR / 'index.json'
VECTORS_FILE = EMBEDDINGS_DIR / 'vectors.npy'

# Lightweight multilingual model (works for English and Japanese)
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'

# Memory sources to index
SOURCES = {
    'experiences': REPO_ROOT / 'memory' / 'experiences.jsonl',
    'diary':       REPO_ROOT / 'memory' / 'diary.json',
    'knowledge':   REPO_ROOT / 'memory' / 'knowledge',
    'midterm':     REPO_ROOT / 'memory' / 'mid-term',
}


# ── Text extraction ───────────────────────────────────────────────────────────

def extract_from_experiences(path: Path) -> List[Dict]:
    """Extract text chunks from experiences.jsonl."""
    items = []
    if not path.exists():
        return items
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = entry.get('timestamp', '')
                desc = entry.get('description', '')
                etype = entry.get('type', '')
                text = f"[{etype}] {desc}"
                items.append({
                    'id': f'experiences:{ts}',
                    'source': 'experiences',
                    'text': text,
                    'timestamp': ts,
                })
            except json.JSONDecodeError:
                pass
    return items


def extract_from_diary(path: Path) -> List[Dict]:
    """Extract text chunks from diary.json."""
    items = []
    if not path.exists():
        return items
    try:
        entries = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(entries, dict):
            entries = entries.get('entries', [])
        for entry in entries:
            dt = entry.get('datetime', '')
            title = entry.get('title', '')
            content = entry.get('content', '')
            text = f"{title}: {content[:500]}"
            items.append({
                'id': f'diary:{dt}',
                'source': 'diary',
                'text': text,
                'timestamp': dt,
            })
    except (json.JSONDecodeError, TypeError):
        pass
    return items


def extract_from_markdown_dir(directory: Path, source_name: str) -> List[Dict]:
    """Extract text from all .md files in a directory."""
    items = []
    if not directory.is_dir():
        return items
    for md_file in sorted(directory.glob('**/*.md')):
        try:
            content = md_file.read_text(encoding='utf-8')
            rel_path = md_file.relative_to(REPO_ROOT)
            # Use first heading as title, fallback to filename
            title = md_file.stem
            for line in content.splitlines():
                if line.startswith('# '):
                    title = line[2:].strip()
                    break
            # Truncate for indexing
            items.append({
                'id': str(rel_path),
                'source': source_name,
                'text': f"{title}\n{content[:800]}",
                'timestamp': '',
            })
        except Exception:
            pass
    return items


def collect_all_items() -> List[Dict]:
    """Collect all indexable text items from memory sources."""
    items = []
    items.extend(extract_from_experiences(SOURCES['experiences']))
    items.extend(extract_from_diary(SOURCES['diary']))
    items.extend(extract_from_markdown_dir(SOURCES['knowledge'], 'knowledge'))
    items.extend(extract_from_markdown_dir(SOURCES['midterm'], 'midterm'))
    return items


# ── Index management ─────────────────────────────────────────────────────────

def compute_checksum(items: List[Dict]) -> str:
    """Compute a checksum of item IDs to detect changes."""
    ids = [item['id'] for item in items]
    return hashlib.md5(json.dumps(ids, sort_keys=True).encode()).hexdigest()


def load_index() -> Tuple[Optional[List[Dict]], Optional[np.ndarray]]:
    """Load existing index and vectors from disk."""
    if not INDEX_FILE.exists() or not VECTORS_FILE.exists():
        return None, None
    try:
        index = json.loads(INDEX_FILE.read_text(encoding='utf-8'))
        vectors = np.load(str(VECTORS_FILE))
        return index, vectors
    except Exception:
        return None, None


def save_index(items: List[Dict], vectors: 'np.ndarray') -> None:
    """Save index and vectors to disk."""
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
    np.save(str(VECTORS_FILE), vectors)


def build_index(model: 'SentenceTransformer', items: List[Dict]) -> 'np.ndarray':
    """Build embedding vectors for all items."""
    texts = [item['text'] for item in items]
    print(f'   Building embeddings for {len(texts)} items...')
    vectors = model.encode(texts, show_progress_bar=True, batch_size=64)
    # Normalize for cosine similarity
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return vectors / norms


def get_or_build_index(force_rebuild: bool = False) -> Tuple[List[Dict], 'np.ndarray', 'SentenceTransformer']:
    """Load existing index or build a new one if needed."""
    print(f'Loading model: {MODEL_NAME}')
    model = SentenceTransformer(MODEL_NAME)

    items = collect_all_items()
    checksum = compute_checksum(items)

    if not force_rebuild:
        index, vectors = load_index()
        if index is not None and vectors is not None:
            # Check if index is still valid
            saved_checksum = index[0].get('_checksum') if index else None
            if saved_checksum == checksum and len(index) - 1 == len(items):
                print(f'✅ Using cached index ({len(items)} items)')
                # Remove checksum entry
                return index[1:], vectors[1:], model

    print(f'📝 Building new index ({len(items)} items)...')
    vectors = build_index(model, items)

    # Prepend checksum sentinel
    sentinel = [{'_checksum': checksum, 'id': '__sentinel__', 'source': '', 'text': '', 'timestamp': ''}]
    sentinel_vec = np.zeros((1, vectors.shape[1]))
    save_index(sentinel + items, np.vstack([sentinel_vec, vectors]))
    print(f'✅ Index saved to {EMBEDDINGS_DIR}')

    return items, vectors, model


# ── Search ────────────────────────────────────────────────────────────────────

def cosine_similarity(query_vec: 'np.ndarray', vectors: 'np.ndarray') -> 'np.ndarray':
    """Compute cosine similarity between query and all vectors."""
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return np.zeros(len(vectors))
    query_normalized = query_vec / query_norm
    return vectors @ query_normalized


def search(
    query: str,
    top_k: int = 5,
    source_filter: Optional[List[str]] = None,
    force_rebuild: bool = False,
) -> List[Dict]:
    """
    Search memory for items semantically related to query.

    Returns list of dicts with keys: id, source, text, timestamp, score
    """
    items, vectors, model = get_or_build_index(force_rebuild)

    # Encode query
    query_vec = model.encode([query])[0]
    query_norm = np.linalg.norm(query_vec)
    if query_norm > 0:
        query_vec = query_vec / query_norm

    # Compute similarities
    scores = cosine_similarity(query_vec, vectors)

    # Apply source filter
    if source_filter:
        for i, item in enumerate(items):
            if item['source'] not in source_filter:
                scores[i] = -1.0

    # Get top K
    top_indices = np.argsort(scores)[::-1][:top_k]
    results = []
    for idx in top_indices:
        if scores[idx] <= 0:
            break
        result = dict(items[idx])
        result['score'] = float(scores[idx])
        results.append(result)

    return results


# ── Fallback keyword search ───────────────────────────────────────────────────

def keyword_search(query: str, top_k: int = 5) -> List[Dict]:
    """Simple keyword search fallback (no embedding model required)."""
    items = collect_all_items()
    query_lower = query.lower()
    scored = []
    for item in items:
        text_lower = item['text'].lower()
        # Count query term occurrences
        score = sum(text_lower.count(term) for term in query_lower.split())
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, item in scored[:top_k]:
        result = dict(item)
        result['score'] = score / 10.0  # Normalize loosely
        results.append(result)
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def format_result(result: Dict, rank: int) -> str:
    """Format a search result for display."""
    score = result.get('score', 0)
    source = result.get('source', '')
    item_id = result.get('id', '')
    text = result.get('text', '')[:200]
    ts = result.get('timestamp', '')

    lines = [
        f'  [{rank}] score={score:.3f}  source={source}',
        f'      id: {item_id}',
    ]
    if ts:
        lines.append(f'      time: {ts}')
    lines.append(f'      {text[:120]}...' if len(text) > 120 else f'      {text}')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Semantic memory search')
    parser.add_argument('--text', '-t', help='Search query text')
    parser.add_argument('--top', type=int, default=5, help='Number of results (default: 5)')
    parser.add_argument('--source', help='Filter by source: experiences,diary,knowledge,midterm')
    parser.add_argument('--rebuild', action='store_true', help='Force rebuild the embedding index')
    args = parser.parse_args()

    if args.rebuild and not args.text:
        if not EMBEDDINGS_AVAILABLE:
            print('❌ sentence-transformers not installed. Run: pip install sentence-transformers numpy')
            return
        get_or_build_index(force_rebuild=True)
        return

    if not args.text:
        parser.print_help()
        return

    source_filter = [s.strip() for s in args.source.split(',')] if args.source else None

    print(f'\n🔍 Searching for: "{args.text}"')
    print('=' * 60)

    if EMBEDDINGS_AVAILABLE:
        try:
            results = search(args.text, top_k=args.top, source_filter=source_filter, force_rebuild=args.rebuild)
        except Exception as e:
            print(f'⚠️  Embedding search failed: {e}')
            print('   Falling back to keyword search...')
            results = keyword_search(args.text, top_k=args.top)
    else:
        print('⚠️  sentence-transformers not installed, using keyword search')
        print('   For semantic search: pip install sentence-transformers numpy\n')
        results = keyword_search(args.text, top_k=args.top)

    if not results:
        print('No results found.')
        return

    print(f'Found {len(results)} results:\n')
    for i, result in enumerate(results, 1):
        print(format_result(result, i))
        print()


if __name__ == '__main__':
    main()
