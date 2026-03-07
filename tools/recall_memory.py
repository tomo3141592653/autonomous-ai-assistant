#!/usr/bin/env python3
"""
記憶蘇生ツール - Gemini File Searchを使った自動記憶想起

Usage:
    uv run tools/recall_memory.py --query "検索クエリ"
    uv run tools/recall_memory.py --source ayumu --query "最初の経験"
    uv run tools/recall_memory.py --source tomo --query "2015年の旅行"
    uv run tools/recall_memory.py --source tomo --force-reindex  # tomoのstoreを再構築
    uv run tools/recall_memory.py --source ayumu --force-reindex  # ayumuのstoreを再構築
    uv run tools/recall_memory.py --upload-only "twitter_2011,twitter_2013" --source tomo
    uv run tools/recall_memory.py --delete-store tomo  # storeを削除
    uv run tools/recall_memory.py --list-stores  # store一覧表示
"""

from google import genai
from google.genai import types
import hashlib
import json
import os
import argparse
import time
from pathlib import Path
from dotenv import load_dotenv

# .envファイルから環境変数を読み込み
load_dotenv()


class MemoryRecallSystem:
    """2つのFile Search Storeを管理するシステム"""

    STORE_CONFIGS = {
        "ayumu": {
            "display_name": "ayumu-memory-store",
            "description": "アユムの記憶（experiences, diary, knowledge）"
        },
        "tomo": {
            "display_name": "tomo-memory-store",
            "description": "パートナーの記憶（Twitter Archive）"
        }
    }

    def __init__(self, force_reindex=False, source="all", upload_only=None):
        self.base_path = Path(__file__).parent.parent / "memory"
        self.force_reindex = force_reindex
        self.source = source
        self.upload_only = upload_only

        # Store管理ファイル（source別）
        self.store_files = {
            "ayumu": self.base_path / ".file_search_store_ayumu.txt",
            "tomo": self.base_path / ".file_search_store_tomo.txt"
        }
        self.cache_files = {
            "ayumu": self.base_path / ".file_hashes_ayumu.json",
            "tomo": self.base_path / ".file_hashes_tomo.json"
        }

        # Gemini API設定
        api_key = None
        for key_name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_AI_API_KEY"):
            val = os.environ.get(key_name, "")
            if val and not val.startswith("encrypted:"):
                api_key = val
                break
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY environment variable not found. "
                "Please set it in .env file or system environment."
            )
        self.client = genai.Client(api_key=api_key)

        # 既存のStoreを読み込み
        self.stores = {}
        self._load_stores()

    def _load_stores(self):
        """既存のStoreを読み込み"""
        for source_name, store_file in self.store_files.items():
            if store_file.exists():
                with open(store_file) as f:
                    store_name = f.read().strip()
                try:
                    store = self.client.file_search_stores.get(name=store_name)
                    self.stores[source_name] = store
                    print(f"♻️  Loaded {source_name} store: {store_name}", flush=True)
                except Exception as e:
                    print(f"⚠️  {source_name} store not found: {e}", flush=True)

    def get_file_hash(self, filepath):
        """ファイルのMD5ハッシュを取得"""
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def get_files_for_source(self, source_name):
        """指定ソースのファイル一覧を取得"""
        files = {}

        if source_name == "ayumu":
            files = {
                "experiences": self.base_path / "experiences.jsonl",
                "diary": self.base_path / "diary.json",
                "knowledge": self.base_path / "knowledge.json"
            }
        elif source_name == "tomo":
            twitter_by_year = Path(__file__).parent / "data" / "twitter-archive" / "by_year"
            if twitter_by_year.exists():
                for year_file in sorted(twitter_by_year.glob("tweets_*.json")):
                    year = year_file.stem.replace("tweets_", "")
                    files[f"twitter_{year}"] = year_file

        return files

    def detect_changes(self, source_name):
        """指定ソースのファイル変更を検知"""
        files = self.get_files_for_source(source_name)
        cache_file = self.cache_files[source_name]

        # 前回のハッシュ読み込み
        if cache_file.exists() and not self.force_reindex:
            with open(cache_file) as f:
                last_hashes = json.load(f)
        else:
            last_hashes = {}

        # 変更検知
        changed = {}
        current_hashes = {}

        for name, filepath in files.items():
            if not filepath.exists():
                print(f"⚠️  Warning: {filepath} not found, skipping")
                continue

            current_hash = self.get_file_hash(filepath)
            current_hashes[name] = current_hash

            if last_hashes.get(name) != current_hash or self.force_reindex:
                changed[name] = filepath

        # ハッシュ保存
        with open(cache_file, 'w') as f:
            json.dump(current_hashes, f, indent=2)

        # --upload-onlyが指定された場合、指定ファイルのみに絞る
        if self.upload_only:
            target_names = [n.strip() for n in self.upload_only.split(",")]
            filtered = {}
            for name in target_names:
                if name in files:
                    filtered[name] = files[name]
                else:
                    print(f"⚠️  Warning: {name} not found in {source_name} files")
            return filtered

        return changed

    def create_store(self, source_name):
        """新しいStoreを作成"""
        config = self.STORE_CONFIGS[source_name]
        print(f"📦 Creating new store: {config['display_name']}...", flush=True)

        store = self.client.file_search_stores.create(
            config={'display_name': config['display_name']}
        )
        print(f"   ✅ Created: {store.name}", flush=True)

        # Store名を保存
        with open(self.store_files[source_name], 'w') as f:
            f.write(store.name)

        self.stores[source_name] = store
        return store

    def upload_to_store(self, source_name, files):
        """指定Storeにファイルをアップロード"""
        store = self.stores.get(source_name)
        if not store:
            store = self.create_store(source_name)

        total = len(files)
        for idx, (name, filepath) in enumerate(files.items(), 1):
            file_size = filepath.stat().st_size / 1024 / 1024
            print(f"📤 [{idx}/{total}] Uploading {name} ({file_size:.1f}MB)...", flush=True)
            try:
                mime_type = 'text/plain' if filepath.suffix == '.jsonl' else None
                config = {'display_name': name}
                if mime_type:
                    config['mime_type'] = mime_type

                operation = self.client.file_search_stores.upload_to_file_search_store(
                    file_search_store_name=store.name,
                    file=str(filepath),
                    config=config
                )

                # アップロード完了待ち（10分タイムアウト）
                wait_count = 0
                timeout_seconds = 600
                while not operation.done:
                    time.sleep(2)
                    operation = self.client.operations.get(operation)
                    wait_count += 1
                    elapsed = wait_count * 2
                    if wait_count % 5 == 0:
                        print(f"   ⏳ Still uploading... ({elapsed}s)", flush=True)
                    if elapsed >= timeout_seconds:
                        print(f"   ⚠️ Upload timeout ({timeout_seconds}s), skipping {name}", flush=True)
                        break

                if operation.done:
                    print(f"   ✅ Upload completed: {name}", flush=True)
                else:
                    print(f"   ⚠️ Upload did not complete: {name}", flush=True)
            except Exception as e:
                print(f"   ❌ Failed to upload {name}: {e}", flush=True)

        return store

    def delete_store(self, source_name):
        """Storeを削除"""
        store = self.stores.get(source_name)
        if not store:
            print(f"❌ {source_name} store not found")
            return False

        try:
            print(f"🗑️  Deleting {source_name} store: {store.name}...", flush=True)
            self.client.file_search_stores.delete(name=store.name, config={'force': True})
            print(f"   ✅ Deleted successfully", flush=True)

            # ローカルファイルも削除
            if self.store_files[source_name].exists():
                self.store_files[source_name].unlink()
            if self.cache_files[source_name].exists():
                self.cache_files[source_name].unlink()

            del self.stores[source_name]
            return True
        except Exception as e:
            print(f"   ❌ Failed to delete: {e}", flush=True)
            return False

    def list_stores(self):
        """Store一覧を表示"""
        print("\n📋 File Search Stores:", flush=True)
        print("=" * 60, flush=True)

        for source_name, config in self.STORE_CONFIGS.items():
            store = self.stores.get(source_name)
            if store:
                print(f"✅ {source_name}: {store.name}", flush=True)
                print(f"   {config['description']}", flush=True)
            else:
                print(f"❌ {source_name}: (not created)", flush=True)
                print(f"   {config['description']}", flush=True)
        print("=" * 60, flush=True)

    def search(self, query, source_name=None):
        """指定ソースで検索（source_name=Noneなら両方）"""
        if source_name:
            store_names = [source_name]
        else:
            store_names = ["ayumu", "tomo"]

        # 使用するstoreを収集
        stores_to_use = []
        for name in store_names:
            if name in self.stores:
                stores_to_use.append(self.stores[name].name)
            else:
                print(f"⚠️  {name} store not found, skipping", flush=True)

        if not stores_to_use:
            print("❌ No stores available for search")
            return None

        # ソース別の検索指示
        if source_name == "ayumu":
            print("\n🔍 アユムの記憶から検索中...", flush=True)
        elif source_name == "tomo":
            print("\n🔍 パートナーの記憶（Twitter）から検索中...", flush=True)
        else:
            print("\n🔍 全記憶から検索中...", flush=True)

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=query,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=stores_to_use
                            )
                        )
                    ]
                )
            )
            return response.text
        except Exception as e:
            print(f"❌ Error during search: {e}")
            import traceback
            traceback.print_exc()
            return None

    def run(self, custom_query=None):
        """メインフロー"""
        print("🧠 記憶蘇生システム起動\n", flush=True)
        print("=" * 60, flush=True)

        # sourceに応じて処理するstore
        if self.source == "all":
            sources_to_process = ["ayumu", "tomo"]
        else:
            sources_to_process = [self.source]

        # 各sourceの変更検知・アップロード
        for source_name in sources_to_process:
            print(f"\n📁 Processing {source_name}...", flush=True)
            changed = self.detect_changes(source_name)

            if changed:
                print(f"   変更検出: {', '.join(changed.keys())}", flush=True)
                self.upload_to_store(source_name, changed)
            else:
                print(f"   変更なし（前回のインデックスを使用）", flush=True)

        # クエリ実行
        if custom_query:
            print(f"\n🔎 クエリ: {custom_query[:100]}...", flush=True)

            search_source = None if self.source == "all" else self.source
            result = self.search(custom_query, search_source)

            if result:
                print("\n" + "=" * 60, flush=True)
                print("✨ 想起された記憶:", flush=True)
                print("=" * 60, flush=True)
                print(result, flush=True)
                print("=" * 60, flush=True)
            else:
                print("\n❌ 記憶想起に失敗しました", flush=True)

            return result
        else:
            print("\n✅ インデックス更新完了（クエリなし）", flush=True)
            return None


def main():
    parser = argparse.ArgumentParser(
        description="記憶蘇生システム - Gemini File Searchで過去の記憶を想起"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="検索クエリ"
    )
    parser.add_argument(
        "--force-reindex",
        action="store_true",
        help="強制的に全ファイルを再インデックス"
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["all", "ayumu", "tomo"],
        default="all",
        help="検索/更新対象: all=全て, ayumu=AIの記憶, tomo=パートナーのTwitter"
    )
    parser.add_argument(
        "--upload-only",
        type=str,
        help="指定ファイルのみアップロード（カンマ区切り）"
    )
    parser.add_argument(
        "--delete-store",
        type=str,
        choices=["ayumu", "tomo"],
        help="指定Storeを削除"
    )
    parser.add_argument(
        "--list-stores",
        action="store_true",
        help="Store一覧を表示"
    )

    args = parser.parse_args()

    try:
        system = MemoryRecallSystem(
            force_reindex=args.force_reindex,
            source=args.source,
            upload_only=args.upload_only
        )

        if args.list_stores:
            system.list_stores()
        elif args.delete_store:
            system.delete_store(args.delete_store)
        else:
            system.run(custom_query=args.query)

    except ValueError as e:
        print(f"❌ Error: {e}")
        print("\n💡 Hint: Set GOOGLE_API_KEY in .env file or system environment")
        exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
