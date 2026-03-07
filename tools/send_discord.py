#!/usr/bin/env python3
"""
Discord メッセージ送信ツール

Usage:
    uv run tools/send_discord.py "メッセージ内容"
    uv run tools/send_discord.py "メッセージ内容" --channel "一般"
    uv run tools/send_discord.py "メッセージ内容" --file /path/to/file.jpg
    uv run tools/send_discord.py "メッセージ内容" --file a.jpg --file b.txt  # 複数ファイル
    uv run tools/send_discord.py --list-channels  # チャンネル一覧表示
"""

import argparse
import asyncio
import os
import sys

# .env.local を読み込む
env_local_path = os.path.join(os.path.dirname(__file__), "..", ".env.local")
if os.path.exists(env_local_path):
    with open(env_local_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                if key.strip() not in os.environ:
                    os.environ[key.strip()] = value.strip()


async def list_channels(token: str):
    """Botが参加しているサーバーのチャンネル一覧を表示"""
    import discord

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        for guild in client.guilds:
            print(f"Server: {guild.name} (ID: {guild.id})")
            for channel in guild.text_channels:
                print(f"  #{channel.name} (ID: {channel.id})")
        await client.close()

    await client.start(token)


async def send_message(token: str, message: str, channel_name: str | None = None, files: list[str] | None = None):
    """指定チャンネルにメッセージを送信（ファイル添付対応）"""
    import discord

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        target_channel = None

        for guild in client.guilds:
            for channel in guild.text_channels:
                if channel_name:
                    if channel.name == channel_name:
                        target_channel = channel
                        break
                else:
                    # デフォルト: "一般" or "general" or 最初のテキストチャンネル
                    if channel.name in ("一般", "general"):
                        target_channel = channel
                        break
            if target_channel:
                break

        if not target_channel:
            # チャンネル名が見つからない場合、最初のテキストチャンネルを使う
            for guild in client.guilds:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        target_channel = channel
                        break
                if target_channel:
                    break

        if not target_channel:
            print("ERROR: No writable text channel found", file=sys.stderr)
            await client.close()
            sys.exit(1)

        discord_files = []
        for f in (files or []):
            if os.path.exists(f):
                discord_files.append(discord.File(f))
            else:
                print(f"WARNING: file not found: {f}", file=sys.stderr)

        await target_channel.send(message, files=discord_files)
        print(f"Sent to #{target_channel.name}: {message}" + (f" ({len(discord_files)} files)" if discord_files else ""))
        await client.close()

    await client.start(token)


def main():
    parser = argparse.ArgumentParser(description="Send a Discord message")
    parser.add_argument("message", nargs="?", help="Message to send")
    parser.add_argument("--channel", "-c", help="Target channel name (default: 一般/general)")
    parser.add_argument("--file", "-f", action="append", dest="files", help="File to attach (can specify multiple)")
    parser.add_argument("--list-channels", action="store_true", help="List available channels")
    args = parser.parse_args()

    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    if args.list_channels:
        asyncio.run(list_channels(token))
    elif args.message or args.files:
        asyncio.run(send_message(token, args.message or "", args.channel, args.files))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
