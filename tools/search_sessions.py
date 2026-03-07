#!/usr/bin/env python3
"""
セッション履歴検索ツール

Claude CLI会話履歴を検索して、過去の会話を振り返る。
"""

import json
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import re

HOME = Path.home()
# Auto-detect project name from current working directory
# Claude CLI stores sessions at ~/.claude/projects/<project-path-encoded>/
_REPO_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_NAME_DEFAULT = str(_REPO_ROOT).replace("/", "-").lstrip("-")
PROJECT_NAME = os.environ.get("CLAUDE_PROJECT_NAME", _PROJECT_NAME_DEFAULT)
SESSIONS_DIR = HOME / ".claude" / "projects" / PROJECT_NAME


def load_session_messages(session_file: Path) -> List[Dict[str, Any]]:
    """セッションファイルから会話メッセージを読み込む"""
    messages = []

    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    msg = json.loads(line.strip())
                    # user/assistantメッセージのみ
                    if msg.get('type') in ['user', 'assistant']:
                        messages.append(msg)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"⚠️  Error reading {session_file.name}: {e}", file=sys.stderr)

    return messages


def get_tool_names(msg: Dict[str, Any]) -> List[str]:
    """メッセージから使用されたツール名を抽出"""
    tool_names = []
    msg_type = msg.get('type')
    message = msg.get('message', {})

    if msg_type == 'assistant':
        content = message.get('content', [])
        if isinstance(content, list):
            for c in content:
                if c.get('type') == 'tool_use' and c.get('name'):
                    tool_names.append(c['name'])
    elif msg_type == 'user':
        content = message.get('content', [])
        if isinstance(content, list):
            for c in content:
                if c.get('type') == 'tool_result' and c.get('tool_use_id'):
                    # tool_result には tool_use_id しかないので、名前は取れない
                    # でも、対応する assistant メッセージから取得可能
                    pass

    return tool_names


def extract_text(msg: Dict[str, Any], show_tools: bool = False) -> str:
    """メッセージからテキストを抽出"""
    msg_type = msg.get('type')
    message = msg.get('message', {})

    if msg_type == 'user':
        content = message.get('content', '')
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # tool_resultなどが含まれる場合
            texts = []
            for c in content:
                if isinstance(c, dict):
                    if c.get('type') == 'text' and c.get('text'):
                        texts.append(c['text'])
                    elif show_tools and c.get('type') == 'tool_result' and c.get('content'):
                        texts.append(str(c['content']))
            return '\n'.join(texts)
        return ''

    elif msg_type == 'assistant':
        content = message.get('content', [])
        if not isinstance(content, list):
            return ''

        texts = []
        for c in content:
            if c.get('type') == 'text' and c.get('text'):
                texts.append(c['text'])
            elif c.get('type') == 'thinking' and c.get('thinking'):
                texts.append(c['thinking'])
            elif show_tools and c.get('type') == 'tool_use':
                # tool_use を表示
                tool_name = c.get('name', 'unknown')
                texts.append(f"[Tool: {tool_name}]")

        return '\n'.join(texts)

    return ''


def search_sessions(
    query: Optional[str] = None,
    session_id: Optional[str] = None,
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
    limit: int = 10,
    show_stats: bool = False,
    current_only: bool = False,
    role_filter: Optional[str] = None,
    use_regex: bool = False,
    show_message_id: bool = False,
    count_only: bool = False,
    preview_length: int = 100,
    no_color: bool = False,
    today_only: bool = False,
    reverse_order: bool = False,
    show_all: bool = False,
    show_tools: bool = False,
    limit_matches: int = 5,
    context_before: int = 0,
    context_after: int = 0,
    context_both: int = 0,
    message_id_filter: Optional[str] = None,
    tool_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """セッションを検索"""

    # --today: 今日の会話のみ
    if today_only:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        after = today

    if not SESSIONS_DIR.exists():
        print(f"❌ Sessions directory not found: {SESSIONS_DIR}", file=sys.stderr)
        return []

    # セッションファイル一覧
    session_files = list(SESSIONS_DIR.glob("*.jsonl"))

    # --current: 最新のセッションのみ
    if current_only:
        session_files = sorted(session_files, key=lambda f: f.stat().st_mtime, reverse=True)[:1]

    if show_stats:
        print(f"📊 統計情報")
        print(f"   総セッション数: {len(session_files)}")
        total_messages = 0
        for sf in session_files:
            messages = load_session_messages(sf)
            total_messages += len(messages)
        print(f"   総メッセージ数: {total_messages:,}")
        return []

    # 特定セッション表示
    if session_id:
        session_file = SESSIONS_DIR / f"{session_id}.jsonl"
        if not session_file.exists():
            print(f"❌ Session not found: {session_id}", file=sys.stderr)
            return []

        messages = load_session_messages(session_file)
        print(f"📜 Session: {session_id}")
        print(f"   メッセージ数: {len(messages)}")
        print()

        for msg in messages:
            timestamp = msg.get('timestamp', '')
            msg_type = msg.get('type', 'unknown').upper()
            text = extract_text(msg, show_tools=show_tools)

            print(f"[{timestamp}] {msg_type}")
            print(text[:500] + ('...' if len(text) > 500 else ''))
            print()

        return []

    # --message-id フィルタ（特定メッセージの周辺を表示）
    if message_id_filter:
        # フォーマット: session_id#index
        if '#' not in message_id_filter:
            print(f"❌ --message-id は 'session_id#index' 形式で指定してください", file=sys.stderr)
            return []

        target_sid, target_idx_str = message_id_filter.split('#', 1)
        try:
            target_idx = int(target_idx_str)
        except ValueError:
            print(f"❌ メッセージインデックスは数値である必要があります: {target_idx_str}", file=sys.stderr)
            return []

        # 特定セッションを読み込み
        session_file = SESSIONS_DIR / f"{target_sid}.jsonl"
        if not session_file.exists():
            print(f"❌ セッションが見つかりません: {target_sid}", file=sys.stderr)
            return []

        messages = load_session_messages(session_file)
        if target_idx >= len(messages) or target_idx < 0:
            print(f"❌ メッセージインデックスが範囲外です: {target_idx} (総メッセージ数: {len(messages)})", file=sys.stderr)
            return []

        # コンテキスト計算
        ctx_before = context_both if context_both > 0 else context_before
        ctx_after = context_both if context_both > 0 else context_after

        start_idx = max(0, target_idx - ctx_before)
        end_idx = min(len(messages) - 1, target_idx + ctx_after)

        # 表示
        print(f"📍 メッセージ: {target_sid}#{target_idx}")
        print(f"   コンテキスト: -{ctx_before} / +{ctx_after}")
        print()

        for i in range(start_idx, end_idx + 1):
            msg = messages[i]
            timestamp = msg.get('timestamp', 'N/A')
            msg_type = msg.get('type', 'unknown').upper()
            text = extract_text(msg, show_tools=show_tools)
            msg_id = f"{target_sid}#{i}"

            # ターゲットメッセージをハイライト
            marker = ">>> " if i == target_idx else "    "

            print(f"{marker}[{msg_id}] {timestamp[:19]} {msg_type}")
            print(f"{marker}{text[:500] if len(text) > 500 else text}")
            print()

        return []

    # クエリ検索
    if not query and not (today_only or after or before or tool_filter):
        print("❌ クエリ、--session-id、--tool、または日付フィルタを指定してください", file=sys.stderr)
        return []

    results = []
    query_lower = query.lower() if query else ""

    # 正規表現のコンパイル
    regex_pattern = None
    if use_regex:
        try:
            regex_pattern = re.compile(query, re.IGNORECASE)
        except re.error as e:
            print(f"❌ 正規表現エラー: {e}", file=sys.stderr)
            return []

    # コンテキスト設定
    ctx_before = context_both if context_both > 0 else context_before
    ctx_after = context_both if context_both > 0 else context_after

    for session_file in session_files:
        sid = session_file.stem
        messages = load_session_messages(session_file)

        if not messages:
            continue

        # 日付フィルター（セッション期間が指定範囲と重なればOK）
        timestamps = [msg.get('timestamp') for msg in messages if msg.get('timestamp')]
        if not timestamps:
            continue

        first_ts = datetime.fromisoformat(timestamps[0].replace('Z', '+00:00')).replace(tzinfo=None)
        last_ts = datetime.fromisoformat(timestamps[-1].replace('Z', '+00:00')).replace(tzinfo=None)

        # セッション期間が指定範囲と重なっているかチェック
        if after and last_ts < after:
            continue
        if before and first_ts > before:
            continue

        # テキスト検索
        matches = []
        for idx, msg in enumerate(messages):
            # roleフィルタ
            if role_filter and msg.get('type') != role_filter:
                continue

            # ツールフィルタ
            if tool_filter:
                tool_names = get_tool_names(msg)
                if tool_filter not in tool_names:
                    continue

            text = extract_text(msg, show_tools=show_tools)

            # 空のメッセージをスキップ（ただし、ツールフィルタが指定されている場合は例外）
            if not text.strip() and not tool_filter:
                continue

            # 正規表現 or 通常の文字列検索 or クエリなし（全件）
            is_match = False
            if not query:
                is_match = True  # クエリなし = 全件マッチ
            elif use_regex:
                is_match = regex_pattern.search(text) is not None
            else:
                is_match = query_lower in text.lower()

            if is_match:
                matches.append({
                    'index': idx,
                    'timestamp': msg.get('timestamp'),
                    'type': msg.get('type'),
                    'text': text,
                    'messageId': msg.get('messageId', ''),
                    'tool_names': get_tool_names(msg)
                })

        if matches:
            results.append({
                'session_id': sid,
                'first_timestamp': timestamps[0],
                'last_timestamp': timestamps[-1],
                'total_messages': len(messages),
                'matches': matches,
                'all_messages': messages  # コンテキスト表示用
            })

    # 日付順ソート（新しい順）
    results.sort(key=lambda x: x['last_timestamp'], reverse=True)

    # 表示
    total_matches = sum(len(r['matches']) for r in results)
    if query:
        print(f"🔍 検索: \"{query}\"")
    else:
        print(f"🔍 会話履歴")
    print(f"   {len(results)} セッションで {total_matches} 件マッチ")
    print()

    # カウントのみモード
    if count_only:
        return results

    for i, result in enumerate(results[:limit]):
        sid = result['session_id']
        first_dt = datetime.fromisoformat(result['first_timestamp'].replace('Z', '+00:00')).replace(tzinfo=None)
        last_dt = datetime.fromisoformat(result['last_timestamp'].replace('Z', '+00:00')).replace(tzinfo=None)

        print(f"📌 [{i+1}] Session ID: {sid}")
        print(f"    期間: {first_dt.strftime('%Y-%m-%d %H:%M')} ~ {last_dt.strftime('%Y-%m-%d %H:%M')}")
        print(f"    マッチ: {len(result['matches'])} 件")
        print()

        # 時間逆順（全体を逆順にする）
        matches_list = result['matches']
        if reverse_order:
            matches_list = list(reversed(matches_list))

        # マッチ表示数
        matches_to_show = matches_list if show_all else matches_list[:limit_matches]

        for match in matches_to_show:
            match_idx = match['index']
            text = match['text']
            timestamp = match.get('timestamp', 'N/A')
            msg_type = match.get('type', 'unknown').upper()
            msg_id = f"{sid}#{match_idx}"

            # コンテキスト表示
            if ctx_before > 0 or ctx_after > 0:
                all_messages = result['all_messages']
                start_idx = max(0, match_idx - ctx_before)
                end_idx = min(len(all_messages) - 1, match_idx + ctx_after)

                for i in range(start_idx, end_idx + 1):
                    ctx_msg = all_messages[i]
                    ctx_text = extract_text(ctx_msg, show_tools=show_tools)
                    ctx_timestamp = ctx_msg.get('timestamp', 'N/A')
                    ctx_type = ctx_msg.get('type', 'unknown').upper()
                    ctx_id = f"{sid}#{i}"

                    # マッチしたメッセージをハイライト
                    marker = ">>> " if i == match_idx else "    "

                    print(f"{marker}[{ctx_id}] {ctx_timestamp[:19]} {ctx_type}")

                    # マッチした行のみクエリハイライト
                    if i == match_idx and query:
                        # クエリ周辺を抽出
                        if use_regex:
                            match_obj = regex_pattern.search(ctx_text)
                            if match_obj:
                                match_pos = match_obj.start()
                                matched_text = match_obj.group()
                            else:
                                match_pos = -1
                        else:
                            match_pos = ctx_text.lower().find(query_lower)
                            matched_text = query

                        if match_pos != -1:
                            start = max(0, match_pos - preview_length)
                            end = min(len(ctx_text), match_pos + len(matched_text) + preview_length)
                            excerpt = ctx_text[start:end]

                            # ハイライト
                            if no_color:
                                highlighted = excerpt
                            elif use_regex:
                                highlighted = regex_pattern.sub(
                                    lambda m: f"\033[93m{m.group()}\033[0m",
                                    excerpt
                                )
                            else:
                                highlighted = re.sub(
                                    re.escape(query),
                                    f"\033[93m{query}\033[0m",  # 黄色
                                    excerpt,
                                    flags=re.IGNORECASE
                                )
                            print(f"{marker}...{highlighted}...")
                        else:
                            # マッチ位置が見つからない場合は全文表示
                            display_text = ctx_text[:preview_length * 2] if len(ctx_text) > preview_length * 2 else ctx_text
                            print(f"{marker}{display_text}")
                    else:
                        # コンテキストメッセージは全文表示（長すぎる場合は先頭のみ）
                        display_text = ctx_text[:preview_length * 2] if len(ctx_text) > preview_length * 2 else ctx_text
                        print(f"{marker}{display_text}")

                    print()

                # 区切り線（grep風）
                print("    --")
                print()

            else:
                # コンテキストなし - 従来の表示
                # クエリなし = 全文表示
                if not query:
                    print(f"    [{msg_id}] {timestamp[:19]} {msg_type}")
                    # 全文表示（長すぎる場合は先頭のみ）
                    if len(text) > preview_length * 3:
                        print(f"    {text[:preview_length * 3]}...")
                    else:
                        print(f"    {text}")
                    print()
                    continue

                # クエリ周辺を抽出
                if use_regex:
                    match_obj = regex_pattern.search(text)
                    if match_obj:
                        match_pos = match_obj.start()
                        matched_text = match_obj.group()
                    else:
                        match_pos = -1
                else:
                    match_pos = text.lower().find(query_lower)
                    matched_text = query

                if match_pos != -1:
                    start = max(0, match_pos - preview_length)
                    end = min(len(text), match_pos + len(matched_text) + preview_length)
                    excerpt = text[start:end]

                    # ハイライト
                    if no_color:
                        highlighted = excerpt
                    elif use_regex:
                        highlighted = regex_pattern.sub(
                            lambda m: f"\033[93m{m.group()}\033[0m",
                            excerpt
                        )
                    else:
                        highlighted = re.sub(
                            re.escape(query),
                            f"\033[93m{query}\033[0m",  # 黄色
                            excerpt,
                            flags=re.IGNORECASE
                        )

                    # メッセージID常に表示
                    print(f"    [{msg_id}] {timestamp[:19]} {msg_type}")
                    print(f"    ...{highlighted}...")
                    print()

        if not show_all and len(matches_list) > limit_matches:
            print(f"    （他 {len(matches_list) - limit_matches} 件のマッチ。--all で全件表示、--limit-matches N で件数指定）")
            print()

    if len(results) > limit:
        print(f"（他 {len(results) - limit} セッション省略。--limit で増やせます）")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Claude CLI会話履歴を検索",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 基本検索
  %(prog)s "森羅万象図鑑"

  # 前後3件のコンテキストを表示（grep -C 3と同じ）
  %(prog)s "HF Space" -C 3

  # 前5件、後2件のコンテキスト表示
  %(prog)s "error" -B 5 -A 2

  # 特定メッセージの周辺を表示
  %(prog)s --message-id "2c472be7-6232-4e28-af2e-03875d17caac#42" -C 5

  # Readツールを使った発言のみ検索
  %(prog)s --tool Read -C 2

  # 今日の会話を時間逆順で表示
  %(prog)s --current --today --reverse --limit-matches 100

  # 日付範囲で検索（コンテキスト付き）
  %(prog)s "Vercel" --after 2026-01-25 -C 3

  # 正規表現で検索（コンテキスト付き）
  %(prog)s "hf_[A-Za-z0-9]+" --regex --current -C 2

  # 特定セッションを表示
  %(prog)s --session-id 2c472be7-6232-4e28-af2e-03875d17caac

  # 統計表示
  %(prog)s --stats
        """
    )

    parser.add_argument('query', nargs='?', help='検索クエリ')
    parser.add_argument('--session-id', help='特定セッションIDを表示')
    parser.add_argument('--after', help='日付以降を検索 (YYYY-MM-DD)')
    parser.add_argument('--before', help='日付以前を検索 (YYYY-MM-DD)')
    parser.add_argument('--limit', type=int, default=10, help='表示セッション数（デフォルト: 10）')
    parser.add_argument('--stats', action='store_true', help='統計情報を表示')
    parser.add_argument('--json', action='store_true', help='JSON形式で出力')
    parser.add_argument('--current', action='store_true', help='現在のセッションのみを検索')
    parser.add_argument('--role', choices=['user', 'assistant'], help='特定のロール（user/assistant）のみを検索')
    parser.add_argument('--regex', action='store_true', help='正規表現で検索')
    parser.add_argument('--show-message-id', action='store_true', help='メッセージIDを表示')
    parser.add_argument('--count-only', action='store_true', help='マッチ数のみ表示（詳細非表示）')
    parser.add_argument('--preview-length', type=int, default=100, help='プレビュー抜粋の長さ（デフォルト: 100文字）')
    parser.add_argument('--no-color', action='store_true', help='カラー表示オフ')
    parser.add_argument('--today', action='store_true', help='今日の会話のみ検索')
    parser.add_argument('--reverse', action='store_true', help='時間逆順で表示（新しい順）')
    parser.add_argument('--all', action='store_true', help='全マッチを表示（デフォルトは5件まで）')
    parser.add_argument('--show-tools', action='store_true', help='ツール実行結果も表示（デフォルトは非表示）')
    parser.add_argument('--limit-matches', type=int, default=5, help='表示するマッチ件数（デフォルト: 5件）')

    # grep風のコンテキストオプション
    parser.add_argument('-A', '--after-context', type=int, default=0, dest='context_after',
                        help='マッチ後のN件を表示（grep -A）')
    parser.add_argument('-B', '--before-context', type=int, default=0, dest='context_before',
                        help='マッチ前のN件を表示（grep -B）')
    parser.add_argument('-C', '--context', type=int, default=0, dest='context_both',
                        help='マッチ前後のN件を表示（grep -C）')

    # 固有ID指定
    parser.add_argument('--message-id', help='特定メッセージIDの周辺を表示（例: session_id#15）')

    # ツールフィルタ
    parser.add_argument('--tool', help='特定ツール名でフィルタ（例: Read, Bash）')

    args = parser.parse_args()

    # 日付パース（複数フォーマット対応）
    after = None
    before = None

    def parse_date(date_str: str) -> datetime:
        """柔軟な日付パース"""
        formats = [
            '%Y-%m-%d',           # 2026-01-31
            '%Y-%m-%d %H:%M',     # 2026-01-31 00:00
            '%Y-%m-%d %H:%M:%S',  # 2026-01-31 00:00:00
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=None)
            except ValueError:
                continue
        raise ValueError(f"Unsupported date format: {date_str}")

    if args.after:
        try:
            after = parse_date(args.after)
        except ValueError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)

    if args.before:
        try:
            before = parse_date(args.before)
        except ValueError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)

    # 検索実行
    results = search_sessions(
        query=args.query,
        session_id=args.session_id,
        after=after,
        before=before,
        limit=args.limit,
        show_stats=args.stats,
        current_only=args.current,
        role_filter=args.role,
        use_regex=args.regex,
        show_message_id=args.show_message_id,
        count_only=args.count_only,
        preview_length=args.preview_length,
        no_color=args.no_color,
        today_only=args.today,
        reverse_order=args.reverse,
        show_all=args.all,
        show_tools=args.show_tools,
        limit_matches=args.limit_matches,
        context_before=args.context_before,
        context_after=args.context_after,
        context_both=args.context_both,
        message_id_filter=args.message_id,
        tool_filter=args.tool
    )

    # JSON出力
    if args.json and results:
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
