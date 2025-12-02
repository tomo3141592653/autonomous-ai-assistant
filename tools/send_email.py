#!/usr/bin/env python3
"""
Gmail Send Tool

Send emails via Gmail API.

Usage:
    python tools/send_email.py --subject "Subject" --body "Body"
    python tools/send_email.py --subject "Subject" --file message.txt
    echo "Body" | python tools/send_email.py --subject "Subject" --stdin

Setup:
    1. Create OAuth 2.0 credentials in Google Cloud Console
    2. Download credentials.json to credentials/ folder
    3. Run once to authenticate (browser will open)
    4. token.json will be saved automatically
"""

import sys
import base64
import argparse
from pathlib import Path
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Gmail API scope
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Credentials paths (customize these)
PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"

# Default email addresses (customize these)
FROM_EMAIL = "your-email@gmail.com"
TO_EMAIL = "recipient@gmail.com"


def get_service():
    """Get Gmail API service"""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"Error: credentials.json not found: {CREDENTIALS_FILE}", file=sys.stderr)
                print("Create OAuth 2.0 credentials in Google Cloud Console", file=sys.stderr)
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def create_message(to, subject, body, from_email=FROM_EMAIL):
    """Create email message"""
    message = MIMEText(body, "plain", "utf-8")
    message["to"] = to
    message["from"] = from_email
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}


def send_message(service, message):
    """Send email"""
    return service.users().messages().send(userId="me", body=message).execute()


def main():
    parser = argparse.ArgumentParser(description="Send email via Gmail API")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--body", help="Email body (direct)")
    parser.add_argument("--file", help="File containing email body")
    parser.add_argument("--stdin", action="store_true", help="Read body from stdin")
    parser.add_argument("--to", default=TO_EMAIL, help=f"Recipient (default: {TO_EMAIL})")
    parser.add_argument("--from", dest="from_email", default=FROM_EMAIL, help=f"Sender (default: {FROM_EMAIL})")

    args = parser.parse_args()

    # Get body
    if args.stdin:
        body = sys.stdin.read()
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            body = f.read()
    elif args.body:
        body = args.body
    else:
        parser.error("Specify --body, --file, or --stdin")

    # Get Gmail API service
    try:
        service = get_service()
    except Exception as e:
        print(f"Error: Failed to get Gmail API service: {e}", file=sys.stderr)
        sys.exit(1)

    # Create and send message
    message = create_message(args.to, args.subject, body, args.from_email)

    try:
        result = send_message(service, message)
        print(f"✅ Email sent successfully")
        print(f"   Subject: {args.subject}")
        print(f"   To: {args.to}")
        print(f"   Message ID: {result['id']}")
    except Exception as e:
        print(f"Error: Failed to send email: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
