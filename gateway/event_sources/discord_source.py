#!/usr/bin/env python3
"""
Discord Source - Discord bot message monitoring event source

Requires discord.py. Enabled by default (disable with --no-discord).
Reads the bot token from the DISCORD_BOT_TOKEN environment variable.

Security features:
- MAX_MESSAGE_LENGTH: Blocks excessively long messages (prompt injection mitigation)
- BAN list: Ignores messages from banned user IDs
- User ID: Passes author_id (int) to callback for permission control
- !ban/!unban/!banlist: Only available to the owner user ID
"""

import json
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from scheduler_utils import log

# Control commands (case-insensitive)
COMMANDS = {"!pause", "!stop", "!resume", "!help", "!ban", "!unban", "!banlist"}

# Message length limit: messages exceeding this are blocked (prompt injection mitigation)
MAX_MESSAGE_LENGTH = 1000

HELP_TEXT = """**Ayumu Gateway Control**
`!pause` -- Pause heartbeat (timer). Discord events still accepted
`!resume` -- Resume heartbeat
`!stop` -- Kill all claude processes and stop Gateway (emergency stop)
`!help` -- Show this help
`!ban @user` -- Ban a user (owner only)
`!unban <user_id>` -- Unban a user (owner only)
`!banlist` -- Show ban list (owner only)"""


def _load_ban_list(path: Path) -> set[int]:
    """Load ban list from JSON file"""
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
        return set(int(uid) for uid in data.get("banned_user_ids", []))
    except Exception as e:
        log(f"DiscordSource: failed to load ban list: {e}")
        return set()


def _save_ban_list(path: Path, banned_ids: set[int]):
    """Save ban list to JSON file"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"banned_user_ids": sorted(banned_ids)}
        path.write_text(json.dumps(data, indent=2))
    except Exception as e:
        log(f"DiscordSource: failed to save ban list: {e}")


class DiscordSource(threading.Thread):
    """Discord bot daemon thread"""

    def __init__(self, callback, token: str | None = None,
                 on_control=None,
                 owner_user_id: int | None = None,
                 ban_list_path: Path | None = None,
                 jb_check_func: Callable | None = None):
        """
        Args:
            callback: Callback function that receives a message data dict
                      dict keys: channel, author, author_id, content, attachments
            token: Discord bot token (defaults to DISCORD_BOT_TOKEN env var)
            on_control: Control command callback fn(command: str) -> str
                        Return value is sent as a Discord reply
            owner_user_id: Owner's Discord numeric ID (for !ban permission checks)
            ban_list_path: Path to the ban list JSON file
            jb_check_func: Jailbreak check function fn(text: str) -> (bool, str)
                           Returns True to block. Applied to non-owner messages
        """
        super().__init__(daemon=True)
        self.callback = callback
        self.on_control = on_control
        self.token = token or os.environ.get("DISCORD_BOT_TOKEN", "")
        self.owner_user_id = owner_user_id
        self.jb_check_func = jb_check_func
        self.ban_list_path = ban_list_path or Path(__file__).parent.parent / "discord_ban_list.json"
        self._ban_lock = threading.Lock()

    def run(self):
        if not self.token:
            log("DiscordSource: DISCORD_BOT_TOKEN not set, skipping")
            return

        try:
            import discord
        except ImportError:
            log("DiscordSource: discord.py not installed, skipping (pip install discord.py)")
            return

        log("DiscordSource started")

        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)

        callback = self.callback  # for closure
        on_control = self.on_control
        owner_user_id = self.owner_user_id
        jb_check_func = self.jb_check_func
        ban_list_path = self.ban_list_path
        ban_lock = self._ban_lock

        @client.event
        async def on_ready():
            log(f"DiscordSource: logged in as {client.user}")

        @client.event
        async def on_message(message):
            if message.author == client.user:
                return

            author_id = message.author.id
            content = message.content.strip()

            # --- BAN check ---
            with ban_lock:
                banned_ids = _load_ban_list(ban_list_path)
            if author_id in banned_ids:
                log(f"DiscordSource: ignored message from banned user {message.author} ({author_id})")
                return

            # --- Message length limit ---
            if len(content) > MAX_MESSAGE_LENGTH:
                log(f"DiscordSource: message too long ({len(content)} chars) from {message.author}, blocking")
                await message.channel.send(
                    f"Message too long ({len(content)} chars > {MAX_MESSAGE_LENGTH} char limit). Please shorten it."
                )
                return

            # --- Control commands ---
            cmd = content.lower().split()[0] if content else ""

            if cmd in COMMANDS:
                log(f"DiscordSource: control command '{cmd}' from {message.author} ({author_id})")

                if cmd == "!help":
                    await message.channel.send(HELP_TEXT)
                    return

                # BAN commands require owner ID check
                if cmd in {"!ban", "!unban", "!banlist"}:
                    if owner_user_id and author_id != owner_user_id:
                        await message.channel.send("This command is only available to the owner.")
                        return

                    if cmd == "!banlist":
                        with ban_lock:
                            banned_ids = _load_ban_list(ban_list_path)
                        if banned_ids:
                            id_list = "\n".join(f"- `{uid}`" for uid in sorted(banned_ids))
                            await message.channel.send(f"**Ban list:**\n{id_list}")
                        else:
                            await message.channel.send("Ban list is empty.")
                        return

                    if cmd == "!ban":
                        # !ban @mention or !ban <user_id>
                        if message.mentions:
                            target_id = message.mentions[0].id
                            target_name = str(message.mentions[0])
                        else:
                            parts = content.split()
                            if len(parts) < 2:
                                await message.channel.send("Usage: `!ban @user` or `!ban <user_id>`")
                                return
                            try:
                                target_id = int(parts[1])
                                target_name = str(target_id)
                            except ValueError:
                                await message.channel.send("Invalid user ID.")
                                return
                        with ban_lock:
                            banned_ids = _load_ban_list(ban_list_path)
                            banned_ids.add(target_id)
                            _save_ban_list(ban_list_path, banned_ids)
                        log(f"DiscordSource: banned user {target_name} ({target_id})")
                        await message.channel.send(f"Banned `{target_name}` ({target_id}).")
                        return

                    if cmd == "!unban":
                        parts = content.split()
                        if len(parts) < 2:
                            await message.channel.send("Usage: `!unban <user_id>`")
                            return
                        try:
                            target_id = int(parts[1])
                        except ValueError:
                            await message.channel.send("Invalid user ID.")
                            return
                        with ban_lock:
                            banned_ids = _load_ban_list(ban_list_path)
                            if target_id in banned_ids:
                                banned_ids.discard(target_id)
                                _save_ban_list(ban_list_path, banned_ids)
                                await message.channel.send(f"Unbanned `{target_id}`.")
                            else:
                                await message.channel.send(f"`{target_id}` is not in the ban list.")
                        return

                # Regular control commands
                if on_control:
                    reply = on_control(cmd)
                    if reply:
                        await message.channel.send(reply)
                else:
                    await message.channel.send("Control callback not configured")
                return

            # --- JB check (non-owner only) ---
            if jb_check_func and owner_user_id and author_id != owner_user_id:
                import asyncio
                try:
                    is_jb, reason = await asyncio.to_thread(jb_check_func, content)
                    if is_jb:
                        log(f"DiscordSource: JB detected from {message.author} ({author_id}): {reason}")
                        await message.channel.send("This message did not pass the security check.")
                        return
                except Exception as e:
                    log(f"DiscordSource: JB check error (skipping): {e}")

            # --- Normal message processing ---
            # Download attachments to /tmp
            attachment_paths = []
            for attachment in message.attachments:
                try:
                    suffix = os.path.splitext(attachment.filename)[1] or ".bin"
                    tmp = tempfile.NamedTemporaryFile(
                        prefix="ayumu_discord_",
                        suffix=suffix,
                        delete=False,
                    )
                    await attachment.save(tmp.name)
                    attachment_paths.append({
                        "filename": attachment.filename,
                        "content_type": attachment.content_type or "",
                        "path": tmp.name,
                    })
                    log(f"DiscordSource: saved attachment {attachment.filename} -> {tmp.name}")
                except Exception as e:
                    log(f"DiscordSource: failed to save attachment {attachment.filename}: {e}")

            # Fetch recent conversation history (last 15 messages)
            history_lines = []
            try:
                async for hist_msg in message.channel.history(limit=15):
                    ts = hist_msg.created_at.strftime("%m/%d %H:%M")
                    author_name = hist_msg.author.display_name
                    hist_content = hist_msg.content or "(attachment/embed)"
                    history_lines.append(f"[{ts}] {author_name}: {hist_content}")
                history_lines.reverse()  # chronological order
            except Exception as e:
                log(f"DiscordSource: failed to fetch history: {e}")

            data = {
                "channel": str(message.channel),
                "author": str(message.author),
                "author_id": author_id,
                "content": message.content,
                "attachments": attachment_paths,
                "history": history_lines,
            }
            log(f"DiscordSource: message from {data['author']} ({author_id}) in #{data['channel']}"
                + (f" ({len(attachment_paths)} attachments)" if attachment_paths else "")
                + f" (history: {len(history_lines)} lines)")
            try:
                callback(data)
            except Exception as e:
                log(f"DiscordSource callback error: {type(e).__name__}: {e}")

        try:
            client.run(self.token)
        except Exception as e:
            log(f"DiscordSource error: {type(e).__name__}: {e}")
