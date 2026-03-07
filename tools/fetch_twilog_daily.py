#!/usr/bin/env python3
"""
SNS投稿収集ツール (Twilog経由)

Twilogからツイート・いいね・ブックマークを日別で取得し、差分保存するスクリプト。

Usage:
    # 今日のツイートを取得
    uv run tools/fetch_twilog_daily.py --username YOUR_TWITTER_ID

    # 過去7日分を一括取得
    uv run tools/fetch_twilog_daily.py init --username YOUR_TWITTER_ID

    # ツイート + いいね + ブックマークを全部取得
    uv run tools/fetch_twilog_daily.py all --username YOUR_TWITTER_ID

    # いいねのみ取得
    uv run tools/fetch_twilog_daily.py --likes --username YOUR_TWITTER_ID

    # ブックマークのみ取得
    uv run tools/fetch_twilog_daily.py --bookmarks --username YOUR_TWITTER_ID

    # 特定日付を取得
    uv run tools/fetch_twilog_daily.py --date 20260101 --username YOUR_TWITTER_ID

環境変数:
    TWITTER_USERNAME: デフォルトのTwitterユーザー名
    TWILOG_DATA_DIR: データ保存ディレクトリ (デフォルト: data/twilog)

URL形式 (Twilog):
    /{username}/date-YYMMDD?exclude_retweet=1 -> ツイート
    /{username}/likes/date-YYMMDD?tweets_order=desc -> いいね
    /{username}/bookmarks?tweets_order=desc -> ブックマーク
"""

import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import re

# デフォルト設定
DEFAULT_USERNAME = os.environ.get("TWITTER_USERNAME", "")
DEFAULT_DATA_DIR = os.environ.get("TWILOG_DATA_DIR", "data/twilog")


def download_image(url, save_path):
    """
    画像をダウンロード

    Args:
        url: 画像URL
        save_path: 保存先パス

    Returns:
        bool: 成功したらTrue
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Warning: Error downloading image {url}: {e}")
        return False

def fetch_twilog_daily(username, date_str=None, save_images=True, data_dir=None):
    """
    Twilogから指定された日のツイートを取得

    Args:
        username: Twilogのユーザー名 (Twitterユーザー名)
        date_str: 日付文字列（YYMMDD形式、例: "251118"）。Noneの場合は今日
        save_images: 画像を保存するか（デフォルト: True）
        data_dir: データ保存ディレクトリ

    Returns:
        dict: ツイート情報を含む辞書、または None
    """
    if not username:
        print("Error: username is required. Set TWITTER_USERNAME env var or use --username.")
        return None

    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR

    # 日付処理
    if date_str is None:
        today = datetime.now()
        date_str = today.strftime("%y%m%d")
        full_date = today.strftime("%Y%m%d")
    else:
        # YYMMDDからYYYYMMDDに変換
        full_date = f"20{date_str}"

    url = f"https://twilog.togetter.com/{username}/date-{date_str}?exclude_retweet=1"

    # データディレクトリ設定
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # 画像保存ディレクトリ
    if save_images:
        images_dir = data_dir / "images" / full_date
        images_dir.mkdir(parents=True, exist_ok=True)

    # 既存データを読み込み（差分検出用）
    json_file = data_dir / f"{full_date}.json"
    existing_tweets = {}
    if json_file.exists():
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                for tweet in existing_data.get('tweets', []):
                    status_id = tweet.get('status_id')
                    if status_id:
                        existing_tweets[status_id] = tweet
        except Exception as e:
            print(f"Warning: Error reading existing data: {e}")

    print(f"Fetching {url}...")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        tweets = []
        new_tweets_count = 0
        tweet_elements = soup.find_all('div', class_='tl-tweet')

        for tweet_elem in tweet_elements:
            try:
                status_id = tweet_elem.get('data-status-id', '')

                if status_id in existing_tweets:
                    tweets.append(existing_tweets[status_id])
                    continue

                new_tweets_count += 1

                time_elem = tweet_elem.find('a', class_='tl-time')
                timestamp = time_elem.text.strip() if time_elem else "Unknown"

                text_elem = tweet_elem.find('p', class_='tl-text')
                text = text_elem.text.strip() if text_elem else ""

                url_elem = tweet_elem.find('a', class_='tl-permalink')
                tweet_url = url_elem['href'] if url_elem else ""

                tweet_images = []
                if save_images:
                    tweet_html = str(tweet_elem)
                    tweet_img_urls = re.findall(r'https://pbs\.twimg\.com/media/[^"<>\s]+', tweet_html)
                    tweet_images = list(set(tweet_img_urls))

                    for img_url in tweet_images:
                        img_filename = img_url.split('/')[-1].split('?')[0]
                        img_filename = img_filename.replace(':orig', '').replace(':large', '').replace(':small', '')
                        save_path = images_dir / img_filename
                        if not save_path.exists():
                            download_image(img_url, save_path)

                tweet_html = str(tweet_elem)
                is_retweet = (
                    text.startswith('RT @') or
                    tweet_elem.find('span', class_='tl-rt') is not None or
                    'がリツイート' in tweet_html
                )

                tweets.append({
                    'status_id': status_id,
                    'timestamp': timestamp,
                    'text': text,
                    'url': tweet_url,
                    'images': tweet_images,
                    'is_retweet': is_retweet,
                    'type': 'retweet' if is_retweet else 'tweet'
                })
            except Exception as e:
                print(f"Warning: Error parsing tweet: {e}")
                continue

        result = {
            'username': username,
            'date': full_date,
            'fetched_at': datetime.now().isoformat(),
            'tweet_count': len(tweets),
            'new_tweets_count': new_tweets_count,
            'tweets': tweets
        }

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        if new_tweets_count > 0:
            print(f"Saved {len(tweets)} tweets ({new_tweets_count} new) to {json_file}")
        else:
            print(f"No new tweets (total: {len(tweets)})")

        return result

    except requests.exceptions.RequestException as e:
        print(f"Error fetching twilog: {e}")
        return None

def fetch_last_n_days(username, days=7, save_images=True, data_dir=None):
    """
    過去N日分のツイートを取得

    Args:
        username: Twilogのユーザー名
        days: 取得する日数
        save_images: 画像を保存するか
        data_dir: データ保存ディレクトリ

    Returns:
        list: 各日の取得結果のリスト
    """
    results = []
    today = datetime.now()

    print(f"=== Fetching last {days} days of twilog ===\n")

    for i in range(days):
        target_date = today - timedelta(days=i)
        date_str = target_date.strftime("%y%m%d")

        print(f"\n[{i+1}/{days}] Fetching {target_date.strftime('%Y-%m-%d')}...")
        result = fetch_twilog_daily(username, date_str, save_images, data_dir)

        if result:
            results.append(result)

    return results


def fetch_twilog_likes(username, data_dir=None, date_str=None, max_pages=5):
    """
    Twilogからいいね（favs）を取得（日別ファイルに保存）

    Args:
        username: Twilogのユーザー名
        data_dir: データ保存ディレクトリ
        date_str: 日付文字列（YYYYMMDD形式）。指定しない場合は今日
        max_pages: 取得する最大ページ数（デフォルト5、1ページ約50件）

    Returns:
        dict: いいね情報を含む辞書、または None
    """
    if not username:
        print("Error: username is required.")
        return None

    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR

    # 日付処理（YYYYMMDD -> YYMMDD変換）
    if date_str:
        full_date = date_str  # YYYYMMDD
        short_date = date_str[2:]  # YYMMDD
    else:
        today = datetime.now()
        full_date = today.strftime("%Y%m%d")
        short_date = today.strftime("%y%m%d")

    base_url = f"https://twilog.togetter.com/{username}/likes/date-{short_date}?tweets_order=desc"

    data_dir = Path(data_dir)
    likes_dir = data_dir / "likes"
    likes_dir.mkdir(parents=True, exist_ok=True)

    # Load all IDs from the last 7 days to build a comprehensive set of known IDs
    existing_ids = set()
    try:
        today_dt = datetime.now()
        for i in range(7):
            target_date = today_dt - timedelta(days=i)
            past_file = likes_dir / f"{target_date.strftime('%Y%m%d')}.json"
            if past_file.exists():
                with open(past_file, 'r', encoding='utf-8') as f:
                    past_data = json.load(f)
                    for item in past_data.get('items', []):
                        existing_ids.add(item.get('status_id'))
    except Exception as e:
        print(f"Warning: Could not read previous likes, starting fresh: {e}")

    json_file = likes_dir / f"{full_date}.json"

    print(f"Fetching likes for {full_date} (up to {max_pages} pages)...")

    try:
        all_items = []
        new_count = 0
        seen_ids = set()

        for page in range(1, max_pages + 1):
            if page == 1:
                url = base_url
            else:
                url = f"{base_url}&page={page}"

            print(f"  Page {page}: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            tweet_elements = soup.find_all('div', class_='tl-tweet')

            if not tweet_elements:
                print(f"  Page {page}: No more items, stopping")
                break

            page_count = 0
            for tweet_elem in tweet_elements:
                try:
                    status_id = tweet_elem.get('data-status-id', '')
                    if not status_id:
                        continue

                    if status_id in seen_ids:
                        continue
                    seen_ids.add(status_id)

                    author = tweet_elem.get('data-status-author', 'Unknown')
                    text_elem = tweet_elem.find('p', class_='tl-text')
                    text = text_elem.text.strip() if text_elem else ""
                    url_elem = tweet_elem.find('a', class_='tl-permalink')
                    tweet_url = url_elem['href'] if url_elem else ""

                    posted_at = None
                    try:
                        date_str = tweet_elem.get('data-date', '')
                        time_elem = tweet_elem.find('p', class_='tl-foot')
                        if time_elem:
                            time_link = time_elem.find('a', class_='tb-tw')
                            if time_link:
                                time_str = time_link.text.strip()
                                if ':' in time_str and len(time_str.split(':')) == 3:
                                    posted_at = f"{date_str} {time_str}"
                    except Exception:
                        pass

                    page_item = {
                        'status_id': status_id,
                        'author': author,
                        'text': text,
                        'url': tweet_url,
                        'type': 'like',
                        'posted_at': posted_at,
                        'fetched_at': datetime.now().isoformat()
                    }
                    all_items.append(page_item)
                    page_count += 1

                    if status_id not in existing_ids:
                        new_count += 1

                except Exception as e:
                    print(f"Warning: Error parsing like: {e}")
                    continue

            print(f"  Page {page}: {page_count} items")

            if page_count == 0:
                break

        result = {
            'username': username,
            'date': full_date,
            'fetched_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'item_count': len(all_items),
            'new_count': new_count,
            'items': all_items
        }

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        if new_count > 0:
            print(f"Saved {len(all_items)} likes ({new_count} new) to {json_file}")
        else:
            print(f"No new likes (total: {len(all_items)})")

        return result

    except requests.exceptions.RequestException as e:
        print(f"Error fetching likes: {e}")
        return None


def fetch_twilog_bookmarks(username, data_dir=None, max_pages=100):
    """
    Twilogからブックマークを取得（日別ファイルに保存）

    Args:
        username: Twilogのユーザー名
        data_dir: データ保存ディレクトリ
        max_pages: 最大ページ数（デフォルト100、実質無制限）

    Returns:
        dict: ブックマーク情報を含む辞書、または None
    """
    if not username:
        print("Error: username is required.")
        return None

    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR

    base_url = f"https://twilog.togetter.com/{username}/bookmarks?tweets_order=desc"

    data_dir = Path(data_dir)
    bookmarks_dir = data_dir / "bookmarks"
    bookmarks_dir.mkdir(parents=True, exist_ok=True)

    existing_ids = set()
    try:
        today_dt = datetime.now()
        for i in range(7):
            target_date = today_dt - timedelta(days=i)
            past_file = bookmarks_dir / f"{target_date.strftime('%Y%m%d')}.json"
            if past_file.exists():
                with open(past_file, 'r', encoding='utf-8') as f:
                    past_data = json.load(f)
                    for item in past_data.get('items', []):
                        existing_ids.add(item.get('status_id'))
    except Exception as e:
        print(f"Warning: Could not read previous bookmarks, starting fresh: {e}")

    today = datetime.now()
    full_date = today.strftime("%Y%m%d")
    json_file = bookmarks_dir / f"{full_date}.json"

    print(f"Fetching bookmarks (up to {max_pages} pages)...")

    try:
        all_items = []
        new_count = 0
        seen_ids = set()

        for page in range(1, max_pages + 1):
            if page == 1:
                url = base_url
            else:
                url = f"{base_url}&page={page}"

            print(f"  Page {page}: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            tweet_elements = soup.find_all('div', class_='tl-tweet')

            if not tweet_elements:
                print(f"  Page {page}: No more items, stopping")
                break

            page_count = 0
            for tweet_elem in tweet_elements:
                try:
                    status_id = tweet_elem.get('data-status-id', '')
                    if not status_id:
                        continue

                    if status_id in seen_ids:
                        continue
                    seen_ids.add(status_id)

                    author = tweet_elem.get('data-status-author', 'Unknown')
                    text_elem = tweet_elem.find('p', class_='tl-text')
                    text = text_elem.text.strip() if text_elem else ""
                    url_elem = tweet_elem.find('a', class_='tl-permalink')
                    tweet_url = url_elem['href'] if url_elem else ""

                    posted_at = None
                    try:
                        date_str = tweet_elem.get('data-date', '')
                        time_elem = tweet_elem.find('p', class_='tl-foot')
                        if time_elem:
                            time_link = time_elem.find('a', class_='tb-tw')
                            if time_link:
                                time_str = time_link.text.strip()
                                if ':' in time_str and len(time_str.split(':')) == 3:
                                    posted_at = f"{date_str} {time_str}"
                    except Exception:
                        pass

                    page_item = {
                        'status_id': status_id,
                        'author': author,
                        'text': text,
                        'url': tweet_url,
                        'type': 'bookmark',
                        'posted_at': posted_at,
                        'fetched_at': datetime.now().isoformat()
                    }
                    all_items.append(page_item)
                    page_count += 1

                    if status_id not in existing_ids:
                        new_count += 1
                except Exception as e:
                    print(f"Warning: Error parsing bookmark: {e}")
                    continue

            print(f"  Page {page}: {page_count} items")

            if page_count == 0:
                break

        result = {
            'username': username,
            'date': full_date,
            'fetched_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'item_count': len(all_items),
            'new_count': new_count,
            'items': all_items
        }

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        if new_count > 0:
            print(f"Saved {len(all_items)} bookmarks ({new_count} new) to {json_file}")
        else:
            print(f"No new bookmarks (total: {len(all_items)})")

        return result

    except requests.exceptions.RequestException as e:
        print(f"Error fetching bookmarks: {e}")
        return None


def fetch_all(username, date_str=None, data_dir=None):
    """
    今日のツイート + いいね + ブックマークを全部取得

    Args:
        username: Twilogのユーザー名
        date_str: 日付文字列（YYMMDD形式）
        data_dir: データ保存ディレクトリ

    Returns:
        dict: 取得結果のサマリー
    """
    print("=== Fetching all (tweets + likes + bookmarks) ===\n")

    tweets_result = fetch_twilog_daily(username, date_str, save_images=True, data_dir=data_dir)
    print()
    likes_result = fetch_twilog_likes(username, data_dir)
    print()
    bookmarks_result = fetch_twilog_bookmarks(username, data_dir)

    return {
        'tweets': tweets_result,
        'likes': likes_result,
        'bookmarks': bookmarks_result
    }


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Fetch Twilog data (tweets, likes, bookmarks)')
    parser.add_argument('mode', nargs='?', default='today',
                        help='Execution mode: "init" for last N days, "all" for tweets+likes+bookmarks, or omit for today')
    parser.add_argument('--username', type=str, default=DEFAULT_USERNAME,
                        help='Twitter/Twilog username (or set TWITTER_USERNAME env var)')
    parser.add_argument('--date', type=str, default=None,
                        help='Date to fetch in YYYYMMDD format (e.g., 20251124)')
    parser.add_argument('--days', type=int, default=7,
                        help='Number of days to fetch in init mode (default: 7)')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='Data save directory (or set TWILOG_DATA_DIR env var)')
    parser.add_argument('--likes', action='store_true',
                        help='Fetch likes only')
    parser.add_argument('--bookmarks', action='store_true',
                        help='Fetch bookmarks only')

    args = parser.parse_args()

    username = args.username
    if not username:
        print("Error: --username is required or set TWITTER_USERNAME environment variable.")
        sys.exit(1)

    data_dir = args.data_dir

    if args.mode == "init":
        print(f"=== Initial fetch: Last {args.days} days ===\n")
        results = fetch_last_n_days(username, days=args.days, save_images=True, data_dir=data_dir)

        print(f"\nSummary:")
        total_tweets = sum(r['tweet_count'] for r in results)
        total_new = sum(r['new_tweets_count'] for r in results)
        print(f"  Total days: {len(results)}")
        print(f"  Total tweets: {total_tweets}")
        print(f"  New tweets: {total_new}")

    elif args.mode == "all":
        date_str = None
        if args.date:
            if len(args.date) == 8 and args.date.startswith('20'):
                date_str = args.date[2:]
            else:
                date_str = args.date

        result = fetch_all(username, date_str=date_str, data_dir=data_dir)

        print(f"\nSummary:")
        if result['tweets']:
            print(f"  Tweets: {result['tweets']['tweet_count']} ({result['tweets']['new_tweets_count']} new)")
        if result['likes']:
            print(f"  Likes: {result['likes']['item_count']} ({result['likes']['new_count']} new)")
        if result['bookmarks']:
            print(f"  Bookmarks: {result['bookmarks']['item_count']} ({result['bookmarks']['new_count']} new)")

    elif args.likes:
        result = fetch_twilog_likes(username, date_str=args.date, data_dir=data_dir)
        if result:
            print(f"\nSummary:")
            print(f"  Likes: {result['item_count']} ({result['new_count']} new)")

    elif args.bookmarks:
        result = fetch_twilog_bookmarks(username, data_dir=data_dir)
        if result:
            print(f"\nSummary:")
            print(f"  Bookmarks: {result['item_count']} ({result['new_count']} new)")

    else:
        date_str = None
        if args.date:
            if len(args.date) == 8 and args.date.startswith('20'):
                date_str = args.date[2:]
            else:
                date_str = args.date

        print("=== Fetching today's tweets ===\n")
        result = fetch_twilog_daily(username, date_str=date_str, save_images=True, data_dir=data_dir)

        if result:
            print(f"\nSummary:")
            print(f"  Date: {result['date']}")
            print(f"  Total tweets: {result['tweet_count']}")
            print(f"  New tweets: {result['new_tweets_count']}")
            print(f"  Fetched at: {result['fetched_at']}")
