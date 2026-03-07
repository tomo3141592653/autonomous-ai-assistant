#!/usr/bin/env python3
"""
Gmail送信ツール

使い方:
    uv run tools/send_email.py --subject "件名" --body "本文"
    uv run tools/send_email.py --subject "件名" --file message.txt
    echo "本文" | uv run tools/send_email.py --subject "件名" --stdin

注意:
    - credentials.json が secrets/ にあること
    - 初回実行時にブラウザで認証が必要
    - token.json が secrets/ に自動保存される
"""

from __future__ import print_function
import os
import sys
import base64
import argparse
import mimetypes
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Gmail API スコープ
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# メールアドレス（環境変数または.envで設定）
FROM_EMAIL = os.environ.get("AYUMU_EMAIL", "your-ai@gmail.com")
TO_EMAIL = os.environ.get("PARTNER_EMAIL", "your-partner@gmail.com")

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
            creds = flow.run_local_server(port=0)

        # Token を保存
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def create_message(to, subject, body, from_email=FROM_EMAIL, attachments=None):
    """メールメッセージを作成（添付ファイル対応）"""
    if attachments:
        # 添付ファイルがある場合はMIMEMultipart
        message = MIMEMultipart()
        message["to"] = to
        message["from"] = from_email
        message["subject"] = subject

        # 本文を追加
        message.attach(MIMEText(body, "plain", "utf-8"))

        # 添付ファイルを追加
        for attachment_path in attachments:
            if not Path(attachment_path).exists():
                print(f"警告: 添付ファイルが見つかりません: {attachment_path}", file=sys.stderr)
                continue

            # MIMEタイプを推測
            content_type, _ = mimetypes.guess_type(attachment_path)
            if content_type is None:
                content_type = "application/octet-stream"

            main_type, sub_type = content_type.split("/", 1)

            # ファイルを読み込んで添付
            with open(attachment_path, "rb") as f:
                attachment = MIMEBase(main_type, sub_type)
                attachment.set_payload(f.read())
                encoders.encode_base64(attachment)

                filename = Path(attachment_path).name
                attachment.add_header("Content-Disposition", "attachment", filename=filename)
                message.attach(attachment)
    else:
        # 添付ファイルがない場合はシンプルなMIMEText
        message = MIMEText(body, "plain", "utf-8")
        message["to"] = to
        message["from"] = from_email
        message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}


def send_message(service, message):
    """メールを送信"""
    return service.users().messages().send(userId="me", body=message).execute()


def main():
    parser = argparse.ArgumentParser(description="Gmailを送信")
    parser.add_argument("--subject", required=True, help="メールの件名")
    parser.add_argument("--body", help="メールの本文（直接指定）")
    parser.add_argument("--file", help="メールの本文を含むファイルパス")
    parser.add_argument("--stdin", action="store_true", help="標準入力から本文を読み込む")
    parser.add_argument("--to", default=TO_EMAIL, help=f"送信先メールアドレス（デフォルト: {TO_EMAIL}）")
    parser.add_argument("--attach", action="append", dest="attachments", help="添付ファイルのパス（複数指定可）")

    args = parser.parse_args()

    # 本文の取得
    if args.stdin:
        body = sys.stdin.read()
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            body = f.read()
    elif args.body:
        body = args.body
    else:
        parser.error("--body、--file、または --stdin のいずれかを指定してください")

    # Gmail API サービスを取得
    try:
        service = get_service()
    except Exception as e:
        print(f"エラー: Gmail API サービスの取得に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    # メッセージを作成
    message = create_message(args.to, args.subject, body, attachments=args.attachments)

    # メールを送信
    try:
        result = send_message(service, message)
        print(f"✅ メール送信成功")
        print(f"   件名: {args.subject}")
        print(f"   送信先: {args.to}")
        if args.attachments:
            print(f"   添付ファイル: {', '.join(args.attachments)}")
        print(f"   Message ID: {result['id']}")
    except Exception as e:
        print(f"エラー: メール送信に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
