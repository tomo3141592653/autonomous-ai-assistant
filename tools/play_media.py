#!/usr/bin/env python3
"""
Media Playback Tool (WSL Environment)

Play audio and video files from WSL environment.

Usage:
    # Play audio with text-to-speech
    python tools/play_media.py --tts "Hello, world!"
    python tools/play_media.py --tts "こんにちは" --voice ja-JP-NanamiNeural

    # Play video with Windows Media Player
    python tools/play_media.py --video "C:\\Users\\user\\Videos\\video.mp4"

    # Play audio file
    python tools/play_media.py --audio /path/to/audio.mp3

Requirements:
    - edge-tts (pip install edge-tts)
    - mpv for audio playback (sudo apt install mpv)
    - Windows Media Player for video (WSL only)
"""

import subprocess
import argparse
import sys
import shutil
from pathlib import Path


def check_command(cmd):
    """Check if command exists"""
    return shutil.which(cmd) is not None


def play_tts(text, voice="en-US-AriaNeural", rate="+0%"):
    """Play text-to-speech using edge-tts"""
    if not check_command("edge-playback"):
        print("Error: edge-tts not installed. Run: pip install edge-tts", file=sys.stderr)
        sys.exit(1)

    cmd = [
        "edge-playback",
        "--voice", voice,
        "--rate", rate,
        "--text", text
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Played TTS: {text[:50]}...")
    except subprocess.CalledProcessError as e:
        print(f"Error: TTS playback failed: {e}", file=sys.stderr)
        sys.exit(1)


def play_video(path):
    """Play video using Windows Media Player (WSL)"""
    # Convert to Windows path if needed
    if path.startswith("/mnt/"):
        # /mnt/c/... -> C:\...
        parts = path.split("/")
        drive = parts[2].upper()
        win_path = f"{drive}:\\" + "\\".join(parts[3:])
    else:
        win_path = path

    cmd = ["cmd.exe", "/c", "start", "wmplayer", win_path]

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Playing video: {win_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error: Video playback failed: {e}", file=sys.stderr)
        sys.exit(1)


def play_audio(path):
    """Play audio file using mpv"""
    if not check_command("mpv"):
        print("Error: mpv not installed. Run: sudo apt install mpv", file=sys.stderr)
        sys.exit(1)

    cmd = ["mpv", "--no-video", path]

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Played audio: {path}")
    except subprocess.CalledProcessError as e:
        print(f"Error: Audio playback failed: {e}", file=sys.stderr)
        sys.exit(1)


def list_voices():
    """List available TTS voices"""
    if not check_command("edge-tts"):
        print("Error: edge-tts not installed. Run: pip install edge-tts", file=sys.stderr)
        sys.exit(1)

    subprocess.run(["edge-tts", "--list-voices"])


def main():
    parser = argparse.ArgumentParser(description="Play media files (audio, video, TTS)")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tts", help="Text to speak")
    group.add_argument("--video", help="Video file path (Windows path for WSL)")
    group.add_argument("--audio", help="Audio file path")
    group.add_argument("--list-voices", action="store_true", help="List available TTS voices")

    parser.add_argument("--voice", default="en-US-AriaNeural",
                       help="TTS voice (default: en-US-AriaNeural). Use ja-JP-NanamiNeural for Japanese")
    parser.add_argument("--rate", default="+0%",
                       help="TTS speech rate (e.g., +30%%, -20%%)")

    args = parser.parse_args()

    if args.list_voices:
        list_voices()
    elif args.tts:
        play_tts(args.tts, args.voice, args.rate)
    elif args.video:
        play_video(args.video)
    elif args.audio:
        play_audio(args.audio)


if __name__ == "__main__":
    main()
