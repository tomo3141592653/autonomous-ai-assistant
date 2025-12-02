#!/usr/bin/env python3
"""
Gmail Receive Tool

Check and read emails via Gmail API.

Usage:
    # Show latest 10 emails
    python tools/receive_email.py

    # Show latest N emails
    python tools/receive_email.py --limit 5

    # Show unread emails only
    python tools/receive_email.py --unread

    # Filter by sender
    python tools/receive_email.py --from sender@example.com

    # Filter by subject
    python tools/receive_email.py --subject "keyword"

    # Mark displayed emails as read
    python tools/receive_email.py --unread --mark-read

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
from datetime import datetime

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Gmail API scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Credentials paths (customize these)
PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"


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


def list_messages(service, query="", max_results=10):
    """Get message list"""
    try:
        result = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        return result.get("messages", [])
    except Exception as e:
        print(f"Error: Failed to get message list: {e}", file=sys.stderr)
        return []


def get_message(service, msg_id):
    """Get message details"""
    try:
        return service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    except Exception as e:
        print(f"Error: Failed to get message: {e}", file=sys.stderr)
        return None


def mark_as_read(service, msg_id):
    """Mark message as read"""
    try:
        service.users().messages().modify(
            userId="me",
            id=msg_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        return True
    except Exception as e:
        print(f"Warning: Failed to mark as read: {e}", file=sys.stderr)
        return False


def get_header(headers, name):
    """Get header value by name"""
    for header in headers:
        if header["name"].lower() == name.lower():
            return header["value"]
    return ""


def decode_body(payload):
    """Decode email body"""
    body = ""

    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                if "data" in part["body"]:
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                    break
    else:
        if "data" in payload["body"]:
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    return body


def format_timestamp(internal_date):
    """Format timestamp"""
    timestamp_ms = int(internal_date)
    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def display_message(service, msg_id, show_body=True):
    """Display email"""
    message = get_message(service, msg_id)
    if not message:
        return

    headers = message["payload"]["headers"]
    from_addr = get_header(headers, "From")
    to_addr = get_header(headers, "To")
    subject = get_header(headers, "Subject")
    date = format_timestamp(message["internalDate"])

    print("=" * 50)
    print(f"📧 From: {from_addr}")
    print(f"📬 To: {to_addr}")
    print(f"📅 Date: {date}")
    print(f"📌 Subject: {subject}")

    if show_body:
        body = decode_body(message["payload"])
        print("-" * 50)
        print(body)

    print("=" * 50)
    print()


def main():
    parser = argparse.ArgumentParser(description="Check emails via Gmail API")
    parser.add_argument("--limit", type=int, default=10, help="Number of emails to show (default: 10)")
    parser.add_argument("--unread", action="store_true", help="Show unread emails only")
    parser.add_argument("--from", dest="from_addr", help="Filter by sender")
    parser.add_argument("--subject", help="Filter by subject")
    parser.add_argument("--no-body", action="store_true", help="Don't show email body")
    parser.add_argument("--mark-read", action="store_true", help="Mark displayed emails as read")

    args = parser.parse_args()

    # Build query
    query_parts = ["in:inbox"]
    if args.unread:
        query_parts.append("is:unread")
    if args.from_addr:
        query_parts.append(f"from:{args.from_addr}")
    if args.subject:
        query_parts.append(f"subject:{args.subject}")

    query = " ".join(query_parts)

    # Get Gmail API service
    try:
        service = get_service()
    except Exception as e:
        print(f"Error: Failed to get Gmail API service: {e}", file=sys.stderr)
        sys.exit(1)

    # Get message list
    messages = list_messages(service, query=query, max_results=args.limit)

    if not messages:
        print("No emails found.")
        return

    print(f"📬 Found {len(messages)} email(s)")
    print()

    # Display emails
    for msg in messages:
        display_message(service, msg["id"], show_body=not args.no_body)

        if args.mark_read:
            if mark_as_read(service, msg["id"]):
                print("  ✓ Marked as read")
            print()


if __name__ == "__main__":
    main()
