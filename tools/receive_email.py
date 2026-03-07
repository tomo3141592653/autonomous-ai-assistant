#!/usr/bin/env python3
"""
Gmail受信ツール - Ayumuが受信したメールを読む

使い方:
    # 最新10件のメールを表示
    uv run tools/receive_email.py

    # 最新N件のメールを表示
    uv run tools/receive_email.py --limit 5

    # 未読メールのみ表示
    uv run tools/receive_email.py --unread

    # 特定の送信者からのメール
    uv run tools/receive_email.py --from partner@gmail.com

    # 件名で検索
    uv run tools/receive_email.py --subject "進捗"

注意:
    - credentials.json が secrets/ にあること
    - 初回実行時にブラウザで認証が必要（readスコープの追加承認）
    - token.json が secrets/ に自動保存される
"""

from __future__ import print_function
import os
import sys
import base64
import argparse
from pathlib import Path
from datetime import datetime

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Gmail API スコープ（送信＋受信＋変更）
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",  # メール読み取り＋既読マーク
]

# メールアドレス（環境変数または.envで設定）
MY_EMAIL = os.environ.get("AYUMU_EMAIL", "your-ai@gmail.com")

# Credentials/Token ファイルのパス
PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_DIR = PROJECT_ROOT / "secrets"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"


def get_service():
    """Gmail APIサービスを取得"""
    creds = None

    # Token ファイルが存在する場合は読み込み
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # 認証が必要な場合
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # トークンをリフレッシュ
            creds.refresh(Request())
        else:
            # 初回認証（ブラウザが開く）
            if not CREDENTIALS_FILE.exists():
                print(f"エラー: credentials.json が見つかりません: {CREDENTIALS_FILE}", file=sys.stderr)
                print("Google Cloud Console で OAuth 2.0 クライアント ID を作成してください", file=sys.stderr)
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            # ローカルサーバー方式で認証（ブラウザが自動で開く）
            creds = flow.run_local_server(port=0)

        # Token を保存
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def list_messages(service, query="", max_results=10):
    """メールリストを取得"""
    try:
        result = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        messages = result.get("messages", [])
        return messages
    except Exception as e:
        print(f"エラー: メールリストの取得に失敗しました: {e}", file=sys.stderr)
        return []


def get_message(service, msg_id):
    """メールの詳細を取得"""
    try:
        message = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        return message
    except Exception as e:
        print(f"エラー: メール詳細の取得に失敗しました: {e}", file=sys.stderr)
        return None


def mark_as_read(service, msg_id):
    """メールを既読にする（UNREADラベルを削除）"""
    try:
        service.users().messages().modify(
            userId="me",
            id=msg_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        return True
    except Exception as e:
        print(f"⚠️ 既読マーク失敗: {e}", file=sys.stderr)
        return False


def get_header(headers, name):
    """ヘッダーから特定のフィールドを取得"""
    for header in headers:
        if header["name"].lower() == name.lower():
            return header["value"]
    return ""


def decode_body(payload):
    """メール本文をデコード"""
    body = ""

    if "parts" in payload:
        # マルチパート
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                if "data" in part["body"]:
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                    break
    else:
        # シングルパート
        if "data" in payload["body"]:
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    return body


def get_attachments(payload):
    """添付ファイル情報を取得"""
    attachments = []

    def extract_attachments(parts):
        for part in parts:
            filename = part.get("filename", "")
            mime_type = part.get("mimeType", "")
            body = part.get("body", {})
            size = body.get("size", 0)

            # ファイル名があれば添付ファイル
            if filename:
                attachments.append({
                    "filename": filename,
                    "mimeType": mime_type,
                    "size": size
                })

            # ネストしたパートがあれば再帰的に探索
            if "parts" in part:
                extract_attachments(part["parts"])

    if "parts" in payload:
        extract_attachments(payload["parts"])

    return attachments


def format_size(size_bytes):
    """バイト数を人間が読みやすい形式に変換"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_timestamp(internal_date):
    """タイムスタンプを日本時間でフォーマット"""
    timestamp_ms = int(internal_date)
    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def display_message(service, msg_id, show_body=True):
    """メールを表示"""
    message = get_message(service, msg_id)
    if not message:
        return

    headers = message["payload"]["headers"]
    from_addr = get_header(headers, "From")
    to_addr = get_header(headers, "To")
    subject = get_header(headers, "Subject")
    date = format_timestamp(message["internalDate"])

    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📧 From: {from_addr}")
    print(f"📬 To: {to_addr}")
    print(f"📅 Date: {date}")
    print(f"📌 Subject: {subject}")

    # 添付ファイル表示
    attachments = get_attachments(message["payload"])
    if attachments:
        print(f"📎 Attachments: {len(attachments)}件")
        for att in attachments:
            size_str = format_size(att["size"])
            print(f"   - {att['filename']} ({att['mimeType']}, {size_str})")

    if show_body:
        body = decode_body(message["payload"])
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(body)

    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()


def main():
    parser = argparse.ArgumentParser(description="Ayumuが受信したメールを読む")
    parser.add_argument("--limit", type=int, default=10, help="表示するメール数（デフォルト: 10）")
    parser.add_argument("--unread", action="store_true", help="未読メールのみ表示")
    parser.add_argument("--from", dest="from_addr", help="特定の送信者からのメール")
    parser.add_argument("--subject", help="件名で検索")
    parser.add_argument("--no-body", action="store_true", help="本文を表示しない（件名のみ）")
    parser.add_argument("--do-not-mark-read", action="store_true", help="既読にしない（デフォルトでは既読にする）")
    parser.add_argument("--reauth", action="store_true", help="トークンを削除して再認証する")
    parser.add_argument("--json", action="store_true", help="JSON形式で出力（id, from, subject, body を含む）")

    args = parser.parse_args()

    # 再認証オプション
    if args.reauth:
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
            print(f"🔑 トークンファイルを削除しました: {TOKEN_FILE}")
        print("🌐 ブラウザで再認証を行います...")
        print()

    # クエリを構築
    query_parts = ["in:inbox"]  # 受信トレイのみ
    if args.unread:
        query_parts.append("is:unread")
    if args.from_addr:
        query_parts.append(f"from:{args.from_addr}")
    if args.subject:
        query_parts.append(f"subject:{args.subject}")

    query = " ".join(query_parts)

    # Gmail API サービスを取得
    try:
        service = get_service()
    except Exception as e:
        print(f"エラー: Gmail API サービスの取得に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    # メールリストを取得
    messages = list_messages(service, query=query, max_results=args.limit)

    if not messages:
        if args.json:
            print("[]")
        else:
            print("メールが見つかりませんでした。")
        return

    # JSON出力モード
    if args.json:
        import json as json_mod
        results = []
        for msg in messages:
            message = get_message(service, msg["id"])
            if not message:
                continue
            headers = message["payload"]["headers"]
            body = decode_body(message["payload"]) if not args.no_body else ""
            results.append({
                "id": msg["id"],
                "from": get_header(headers, "From"),
                "to": get_header(headers, "To"),
                "subject": get_header(headers, "Subject"),
                "date": format_timestamp(message["internalDate"]),
                "body": body,
            })
            if not args.do_not_mark_read:
                mark_as_read(service, msg["id"])
        print(json_mod.dumps(results, ensure_ascii=False))
        return

    print(f"📬 {len(messages)}件のメールが見つかりました")
    print()

    # メールを表示
    for msg in messages:
        display_message(service, msg["id"], show_body=not args.no_body)

        # デフォルトで既読にする（--do-not-mark-readが指定されていない場合）
        if not args.do_not_mark_read:
            if mark_as_read(service, msg["id"]):
                print("  ✓ 既読にしました")
            print()


if __name__ == "__main__":
    main()
