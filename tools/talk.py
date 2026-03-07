#!/usr/bin/env python3
"""Edge TTS / piper-plus text-to-speech CLI tool.

Usage:
    uv run tools/talk.py "こんにちは"
    uv run tools/talk.py "こんにちは" --engine piper          # Use piper-plus (tsukuyomi)
    uv run tools/talk.py "こんにちは" --voice ja-JP-KeitaNeural
    uv run tools/talk.py "こんにちは" --rate "+20%"
    uv run tools/talk.py "こんにちは" --speaker camera   # Camera speaker via go2rtc
    uv run tools/talk.py "こんにちは" --speaker both     # PC + camera
    uv run tools/talk.py "こんにちは" --no-play          # Save only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

# Load .env.local
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_LOCAL = _PROJECT_ROOT / ".env.local"
if _ENV_LOCAL.exists():
    load_dotenv(_ENV_LOCAL)

CAMERA_HOST = os.getenv("CAMERA_HOST", os.getenv("TAPO_CAMERA_HOST", "192.168.1.100"))
CAMERA_USER = os.getenv("CAMERA_USERNAME", os.getenv("TAPO_USERNAME", "admin"))
CAMERA_PASS = os.getenv("CAMERA_PASSWORD", os.getenv("TAPO_PASSWORD", ""))
GO2RTC_URL = os.getenv("GO2RTC_URL", "http://localhost:1984")
GO2RTC_FFMPEG = os.getenv("GO2RTC_FFMPEG", "ffmpeg")


# ---------------------------------------------------------------------------
# piper-plus synthesis
# ---------------------------------------------------------------------------

# Default paths for piper-plus (relative to project root)
_PIPER_BIN = _PROJECT_ROOT / "tmp/piper/bin/piper"
_PIPER_LIB = _PROJECT_ROOT / "tmp/piper/lib"
_PIPER_MODEL = _PROJECT_ROOT / "tmp/tsukuyomi-wavlm-300epoch.onnx"
_PIPER_ESPEAK = _PROJECT_ROOT / "tmp/piper/share/espeak-ng-data"
_PIPER_PHONEMIZER = _PROJECT_ROOT / "tmp/piper/bin/open_jtalk_phonemizer"


def synthesize_piper(text: str, output_path: str) -> None:
    """Synthesize text with piper-plus and save as WAV."""
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(_PIPER_LIB) + ":" + env.get("LD_LIBRARY_PATH", "")
    env["ESPEAK_DATA_PATH"] = str(_PIPER_ESPEAK)
    env["OPENJTALK_PHONEMIZER_PATH"] = str(_PIPER_PHONEMIZER)

    result = subprocess.run(
        [str(_PIPER_BIN), "--model", str(_PIPER_MODEL), "--output_file", output_path],
        input=text.encode("utf-8"),
        capture_output=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"piper failed: {result.stderr.decode()}")


# ---------------------------------------------------------------------------
# Edge TTS synthesis
# ---------------------------------------------------------------------------

async def synthesize(text: str, voice: str, rate: str) -> bytes:
    """Synthesize text and return mp3 bytes."""
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=rate)
    chunks: list[bytes] = []
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------

def play_local(file_path: str) -> str:
    """Play audio on local PC. Tries mpv → ffplay → paplay."""
    pulse_server = "unix:/mnt/wslg/PulseServer"
    env = {**os.environ, "PULSE_SERVER": pulse_server}

    # Try ffplay first (best WSLg compatibility)
    if shutil.which("ffplay"):
        r = subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", file_path],
            check=False, capture_output=True, env=env,
        )
        if r.returncode == 0:
            return "played via ffplay"

    # Try mpv
    if shutil.which("mpv"):
        r = subprocess.run(
            ["mpv", "--no-video", "--no-terminal", file_path],
            check=False, capture_output=True, env=env,
        )
        if r.returncode == 0:
            return "played via mpv"

    # Try paplay (needs WAV conversion)
    if shutil.which("paplay") and shutil.which("ffmpeg"):
        wav_path = file_path.rsplit(".", 1)[0] + ".wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", file_path, wav_path],
            check=False, capture_output=True,
        )
        r = subprocess.run(
            ["paplay", wav_path], check=False, capture_output=True, env=env,
        )
        Path(wav_path).unlink(missing_ok=True)
        if r.returncode == 0:
            return "played via paplay"

    return "no player available"


def play_camera(file_path: str) -> str:
    """Play audio through camera speaker via go2rtc backchannel."""
    try:
        abs_path = os.path.abspath(file_path)
        src = f"ffmpeg:{abs_path}#audio=pcma#input=file"
        stream_name = "tapo"
        url = (
            f"{GO2RTC_URL}/api/streams"
            f"?dst={quote(stream_name, safe='')}"
            f"&src={quote(src, safe='')}"
        )
        req = urllib.request.Request(url, method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())

        # Wait for playback to finish
        ffmpeg_id = None
        for p in body.get("producers", []):
            if "ffmpeg" in p.get("source", ""):
                ffmpeg_id = p.get("id")
                break

        if ffmpeg_id:
            for _ in range(60):
                time.sleep(0.5)
                try:
                    with urllib.request.urlopen(f"{GO2RTC_URL}/api/streams", timeout=5) as r:
                        streams = json.loads(r.read())
                    stream = streams.get(stream_name, {})
                    still = any(p.get("id") == ffmpeg_id for p in stream.get("producers", []))
                    if not still:
                        break
                except Exception:
                    break

        return f"played via go2rtc → {stream_name}"
    except Exception as e:
        return f"camera failed: {e}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Edge TTS / piper-plus text-to-speech")
    parser.add_argument("text", help="Text to speak")
    parser.add_argument("--engine", choices=["edge", "piper"], default="edge",
                        help="TTS engine: edge (Edge TTS) or piper (piper-plus/tsukuyomi)")
    parser.add_argument("--voice", default="ja-JP-NanamiNeural",
                        help="Voice for Edge TTS (default: ja-JP-NanamiNeural)")
    parser.add_argument("--rate", default="+0%",
                        help="Speech rate for Edge TTS (e.g. '+20%%', '-10%%')")
    parser.add_argument("--speaker", choices=["local", "camera", "both"], default="local",
                        help="Where to play (default: local)")
    parser.add_argument("--no-play", action="store_true", help="Save only")
    parser.add_argument("--output", help="Output file path")
    args = parser.parse_args()

    # Determine output path
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.engine == "piper":
        # piper-plus synthesis → WAV
        path = args.output if args.output else f"/tmp/talk_{ts}.wav"
        synthesize_piper(args.text, path)
    else:
        # Edge TTS synthesis → MP3
        audio = asyncio.run(synthesize(args.text, args.voice, args.rate))
        path = args.output if args.output else f"/tmp/talk_{ts}.mp3"
        with open(path, "wb") as f:
            f.write(audio)

    if args.no_play:
        print(path)
        return

    # Log Ayumu's speech to hearing log
    try:
        from listen import log_ayumu_speech
        log_ayumu_speech(args.text)
    except Exception:
        pass  # listen.py not available

    # Mute ears during playback (prevent self-transcription)
    speaking_flag = "/tmp/ayumu_speaking"
    Path(speaking_flag).write_text(str(os.getpid()))

    # Play
    local_status = camera_status = "skipped"
    try:
        if args.speaker in ("local", "both"):
            local_status = play_local(path)

        if args.speaker in ("camera", "both"):
            camera_status = play_camera(path)
    finally:
        Path(speaking_flag).unlink(missing_ok=True)

    print(f"{path} | local: {local_status} | camera: {camera_status}")


if __name__ == "__main__":
    main()
