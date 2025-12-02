#!/usr/bin/env python3
"""
Memory Search Tool

Usage:
    python tools/search_memory.py --query "keyword"
    python tools/search_memory.py --query "memory" --source diary
    python tools/search_memory.py --from 2025-01-01 --to 2025-01-31
    python tools/search_memory.py --type learning --limit 10
"""

import json
import argparse
import re
from pathlib import Path
from typing import List, Dict, Any

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"


def highlight_text(text: str, query: str, ignore_case: bool = True) -> str:
    """Highlight query matches in text"""
    if not query:
        return text

    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.escape(query)
    return re.sub(f'({pattern})', f'{YELLOW}\\1{RESET}', text, flags=flags)


def search_experiences(query: str, from_date: str = None, to_date: str = None,
                      exp_type: str = None, ignore_case: bool = True) -> List[Dict[str, Any]]:
    """Search experiences.jsonl"""
    experiences_file = Path(__file__).parent.parent / "memory" / "experiences.jsonl"

    if not experiences_file.exists():
        return []

    results = []
    with open(experiences_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue

            exp = json.loads(line)

            # Date filter
            if from_date or to_date:
                exp_date = exp.get('timestamp', '').split('T')[0]
                if from_date and exp_date < from_date:
                    continue
                if to_date and exp_date > to_date:
                    continue

            # Type filter
            if exp_type and exp.get('type') != exp_type:
                continue

            # Query filter
            if query:
                searchable = f"{exp.get('description', '')} {json.dumps(exp.get('metadata', {}))}"
                flags = re.IGNORECASE if ignore_case else 0
                if not re.search(re.escape(query), searchable, flags):
                    continue

            results.append({
                'source': 'experiences',
                'timestamp': exp.get('timestamp', ''),
                'type': exp.get('type', ''),
                'description': exp.get('description', ''),
                'metadata': exp.get('metadata', {}),
                'raw': exp
            })

    return results


def search_knowledge(query: str, ignore_case: bool = True) -> List[Dict[str, Any]]:
    """Search knowledge.json"""
    knowledge_file = Path(__file__).parent.parent / "memory" / "knowledge.json"

    if not knowledge_file.exists():
        return []

    with open(knowledge_file, 'r', encoding='utf-8') as f:
        knowledge = json.load(f)

    results = []
    facts = knowledge.get('facts', [])

    for fact in facts:
        if query:
            flags = re.IGNORECASE if ignore_case else 0
            if not re.search(re.escape(query), fact, flags):
                continue

        results.append({
            'source': 'knowledge',
            'fact': fact,
            'raw': fact
        })

    return results


def search_diary(query: str, from_date: str = None, to_date: str = None,
                ignore_case: bool = True) -> List[Dict[str, Any]]:
    """Search diary.json"""
    diary_file = Path(__file__).parent.parent / "memory" / "diary.json"

    if not diary_file.exists():
        return []

    with open(diary_file, 'r', encoding='utf-8') as f:
        diary = json.load(f)

    results = []

    for entry in diary:
        entry_date = entry.get('date', '')

        # Date filter
        if from_date and entry_date < from_date:
            continue
        if to_date and entry_date > to_date:
            continue

        # Query filter
        if query:
            searchable = f"{entry.get('title', '')} {entry.get('content', '')}"
            flags = re.IGNORECASE if ignore_case else 0
            if not re.search(re.escape(query), searchable, flags):
                continue

        results.append({
            'source': 'diary',
            'date': entry_date,
            'title': entry.get('title', ''),
            'time_period': entry.get('time_period', ''),
            'content': entry.get('content', ''),
            'raw': entry
        })

    return results


def print_result(result: Dict[str, Any], query: str, ignore_case: bool):
    """Print a single search result"""
    source = result['source']

    if source == 'experiences':
        timestamp = result['timestamp'].split('T')
        date = timestamp[0] if timestamp else ''
        time = timestamp[1].split('.')[0] if len(timestamp) > 1 else ''

        print(f"{CYAN}[experiences]{RESET} {GREEN}{date} {time}{RESET} {MAGENTA}({result['type']}){RESET}")
        print(f"  {highlight_text(result['description'], query, ignore_case)}")
        if result['metadata']:
            print(f"  {BLUE}metadata:{RESET} {json.dumps(result['metadata'], ensure_ascii=False)}")
        print()

    elif source == 'knowledge':
        print(f"{CYAN}[knowledge]{RESET}")
        print(f"  {highlight_text(result['fact'], query, ignore_case)}")
        print()

    elif source == 'diary':
        print(f"{CYAN}[diary]{RESET} {GREEN}{result['date']}{RESET} {result['time_period']}")
        print(f"  {BOLD}{highlight_text(result['title'], query, ignore_case)}{RESET}")
        # Print first 200 chars of content
        content_preview = result['content'][:200] + '...' if len(result['content']) > 200 else result['content']
        print(f"  {highlight_text(content_preview, query, ignore_case)}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description='Search memory (experiences, knowledge, diary)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --query "keyword"
  %(prog)s --query "memory" --source diary
  %(prog)s --from 2025-01-01 --to 2025-01-31
  %(prog)s --type learning --limit 10
        """
    )

    parser.add_argument('--query', '-q', help='Search query (keyword)')
    parser.add_argument('--source', '-s',
                       choices=['all', 'experiences', 'knowledge', 'diary'],
                       default='all',
                       help='Source to search (default: all)')
    parser.add_argument('--from', dest='from_date',
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--to', dest='to_date',
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--type', '-t',
                       help='Filter by experience type (for experiences only)')
    parser.add_argument('--limit', '-l', type=int, default=20,
                       help='Maximum number of results (default: 20)')
    parser.add_argument('-i', '--ignore-case', action='store_true', default=True,
                       help='Case-insensitive search (default: True)')

    args = parser.parse_args()

    # Collect results
    all_results = []

    if args.source in ['all', 'experiences']:
        all_results.extend(search_experiences(
            args.query, args.from_date, args.to_date, args.type, args.ignore_case
        ))

    if args.source in ['all', 'knowledge']:
        all_results.extend(search_knowledge(args.query, args.ignore_case))

    if args.source in ['all', 'diary']:
        all_results.extend(search_diary(
            args.query, args.from_date, args.to_date, args.ignore_case
        ))

    # Sort by timestamp/date
    def get_sort_key(r):
        if r['source'] == 'experiences':
            return r.get('timestamp', '')
        elif r['source'] == 'diary':
            return r.get('date', '')
        else:
            return ''  # knowledge has no date

    all_results.sort(key=get_sort_key)

    # Apply limit
    results = all_results[:args.limit] if args.limit else all_results

    # Print results
    print(f"{BOLD}Search Results:{RESET}")
    print(f"Query: {YELLOW}{args.query or '(none)'}{RESET}")
    print(f"Source: {args.source}, From: {args.from_date or 'beginning'}, To: {args.to_date or 'now'}")
    print(f"Found {len(all_results)} results (showing {len(results)})")
    print(f"{'-' * 70}\n")

    for result in results:
        print_result(result, args.query or '', args.ignore_case)

    # Summary
    sources_found = set(r['source'] for r in all_results)
    print(f"{'-' * 70}")
    print(f"{BOLD}Summary:{RESET} {len(all_results)} results from {len(sources_found)} source(s): {', '.join(sources_found)}")


if __name__ == '__main__':
    main()
