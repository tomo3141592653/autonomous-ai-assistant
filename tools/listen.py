#!/usr/bin/env python3
"""Audio recording and speech-to-text CLI tool (self-contained).

Usage:
    uv run tools/listen.py                            # PC mic, 5 seconds fixed
    uv run tools/listen.py --wait                     # Wait for speech (up to 10s)
    uv run tools/listen.py --wait --timeout 15        # Wait up to 15s
    uv run tools/listen.py --source camera             # Camera mic
    uv run tools/listen.py --duration 10               # Fixed 10 seconds
    uv run tools/listen.py --no-transcribe             # Record only
    uv run tools/listen.py --model small               # Larger Whisper model
    uv run tools/listen.py --raw                       # Transcript text only
    uv run tools/listen.py --on                        # Continuous streaming STT
    uv run tools/listen.py --on --engine cpp           # Use whisper.cpp server (default)
    uv run tools/listen.py --on --engine faster        # Use faster-whisper (GPU)
    uv run tools/listen.py --on --engine whisper       # Use openai-whisper
    uv run tools/listen.py --on --engine smart         # Auto: Moonshine (<3s) or Groq (>=3s)
    uv run tools/listen.py --read                      # Read new transcriptions
    uv run tools/listen.py --off                       # Stop continuous listening

Engine options:
    cpp       - whisper.cpp HTTP server + Silero VAD (recommended, default)
    faster    - faster-whisper + Silero VAD (GPU, heavy)
    whisper   - openai-whisper (original, slower)
    groq      - Groq API (cloud, requires GROQ_API_KEY)
    moonshine - Moonshine Voice (local CPU, fast, ja=non-commercial license)
    smart     - Auto-select: Moonshine for short audio (<3s speech), Groq for longer
"""

from __future__ import annotations

import argparse
import asyncio
import math
import os
import struct
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load .env.local
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_LOCAL = _PROJECT_ROOT / ".env.local"
if _ENV_LOCAL.exists():
    load_dotenv(_ENV_LOCAL)

CAMERA_HOST = os.getenv("CAMERA_HOST", os.getenv("TAPO_CAMERA_HOST", "192.168.1.100"))
CAMERA_USER = os.getenv("CAMERA_USERNAME", os.getenv("TAPO_USERNAME", "admin"))
CAMERA_PASS = os.getenv("CAMERA_PASSWORD", os.getenv("TAPO_PASSWORD", ""))

# Whisper hallucination patterns
_HALLUCINATION_PATTERNS = [
    "ご視聴ありがとうございま", "チャンネル登録", "お願いします",
    "字幕は自動生成", "Thanks for watching", "Thank you for watching",
    "Subscribe", "MBS", "日本語で会話しています",
    "見てくれてありがとう", "お疲れ様でした",
]

# Preloaded whisper model (cached across calls in --wait mode)
_whisper_model = None

# Preloaded faster-whisper model
_faster_model = None

# Preloaded Silero VAD model
_vad_model = None


# ---------------------------------------------------------------------------
# Audio utilities
# ---------------------------------------------------------------------------

def get_wav_duration(audio_path: str) -> float:
    """Return duration of a WAV file in seconds."""
    try:
        with wave.open(audio_path, "rb") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return 0.0


def get_speech_duration_vad(audio_path: str, threshold: float = 0.3) -> float:
    """Estimate speech duration in seconds using Silero VAD."""
    import torch
    import numpy as np

    try:
        with wave.open(audio_path, "rb") as wf:
            sr = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
            sw = wf.getsampwidth()

        if len(frames) < 100:
            return 0.0

        if sw == 2:
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        elif sw == 1:
            samples = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        else:
            return get_wav_duration(audio_path)

        if sr != 16000:
            ratio = 16000 / sr
            new_len = int(len(samples) * ratio)
            indices = np.linspace(0, len(samples) - 1, new_len).astype(int)
            samples = samples[indices]

        audio_tensor = torch.from_numpy(samples)
        model = _get_vad_model()
        window_size = 512  # 32ms at 16kHz
        speech_windows = 0
        for i in range(0, len(audio_tensor) - window_size + 1, window_size):
            chunk = audio_tensor[i:i + window_size]
            prob = model(chunk, 16000).item()
            if prob > threshold:
                speech_windows += 1

        return speech_windows * (window_size / 16000)
    except Exception:
        return get_wav_duration(audio_path)


def compute_rms(audio_path: str) -> float:
    """Compute RMS energy of a WAV file."""
    try:
        with wave.open(audio_path, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            sw = wf.getsampwidth()
            if sw == 2:
                samples = struct.unpack(f"<{len(frames) // 2}h", frames)
            elif sw == 1:
                samples = [s - 128 for s in frames]
            else:
                return 999.0
            if not samples:
                return 0.0
            return math.sqrt(sum(s * s for s in samples) / len(samples))
    except Exception:
        return 999.0


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

async def record_pc(duration: float, output: str) -> None:
    """Record from PC mic via WSLg PulseAudio."""
    env = {**os.environ, "PULSE_SERVER": "unix:/mnt/wslg/PulseServer"}
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "pulse", "-i", "default",
        "-ar", "16000", "-ac", "1", "-t", str(duration), output,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        env=env,
    )
    await asyncio.wait_for(proc.wait(), timeout=duration + 10.0)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed. Is PulseAudio available?")


async def record_camera(duration: float, output: str) -> None:
    """Record from camera mic via RTSP."""
    url = f"rtsp://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_HOST}:554/stream1"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-rtsp_transport", "tcp", "-i", url,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        "-t", str(duration), "-y", output,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await asyncio.wait_for(proc.wait(), timeout=duration + 10.0)


# Windows ffmpeg path (for DirectShow mic access)
# Set WIN_FFMPEG_PATH env var to your Windows ffmpeg.exe path if using WSL
_WIN_FFMPEG = os.getenv("WIN_FFMPEG_PATH", "ffmpeg.exe")
_WIN_MIC = os.getenv("WIN_MIC_DEVICE", "Microphone")
_WIN_TEMP = os.getenv("WIN_TEMP_DIR", "C:\\Windows\\Temp")


async def record_win(duration: float, output: str) -> None:
    """Record from Windows DirectShow mic via Windows ffmpeg."""
    import shutil
    win_out = f"{_WIN_TEMP}\\listen_tmp.wav"
    # Convert Windows path to WSL path for file access
    win_temp_wsl = os.getenv("WIN_TEMP_WSL_PATH", "/mnt/c/Windows/Temp")
    win_wav = f"{win_temp_wsl}/listen_tmp.wav"

    proc = await asyncio.create_subprocess_exec(
        _WIN_FFMPEG, "-y", "-f", "dshow",
        "-i", f"audio={_WIN_MIC}",
        "-ar", "16000", "-ac", "1", "-t", str(duration),
        win_out,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.wait_for(proc.wait(), timeout=duration + 10.0)
    if proc.returncode != 0:
        stderr = await proc.stderr.read()
        raise RuntimeError(f"Windows ffmpeg failed (rc={proc.returncode}): {stderr.decode()[:200]}")
    # Copy from Windows temp to output
    if Path(win_wav).exists() and Path(win_wav).stat().st_size > 1000:
        shutil.copy2(win_wav, output)
    else:
        raise RuntimeError(f"Windows recording failed (file missing or too small: {Path(win_wav).stat().st_size if Path(win_wav).exists() else 'missing'})")


async def record_chunk(source: str, duration: float, output: str) -> None:
    """Record a chunk from specified source."""
    if source == "pc":
        await record_pc(duration, output)
    elif source == "win":
        await record_win(duration, output)
    else:
        await record_camera(duration, output)


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Silero VAD (Voice Activity Detection)
# ---------------------------------------------------------------------------

def _get_vad_model():
    """Load Silero VAD model (cached)."""
    global _vad_model
    if _vad_model is None:
        import torch
        _vad_model, _ = torch.hub.load(
            repo_or_dir='snakers4/silero-vad', model='silero_vad',
            trust_repo=True,
        )
    return _vad_model


def has_speech_vad(audio_path: str, threshold: float = 0.3) -> bool:
    """Check if audio file contains speech using Silero VAD.

    Returns True if speech is detected, False otherwise.
    """
    import torch
    import numpy as np

    try:
        with wave.open(audio_path, "rb") as wf:
            sr = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
            sw = wf.getsampwidth()

        if len(frames) < 100:
            return False

        if sw == 2:
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        elif sw == 1:
            samples = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        else:
            return True  # Unknown format, let Whisper decide

        if len(samples) == 0:
            return False

        # Resample to 16kHz if needed
        if sr != 16000:
            ratio = 16000 / sr
            new_len = int(len(samples) * ratio)
            indices = np.linspace(0, len(samples) - 1, new_len).astype(int)
            samples = samples[indices]

        audio_tensor = torch.from_numpy(samples)

        model = _get_vad_model()
        # Process in 512-sample windows (32ms at 16kHz)
        window_size = 512
        speech_probs = []
        for i in range(0, len(audio_tensor) - window_size + 1, window_size):
            chunk = audio_tensor[i:i + window_size]
            prob = model(chunk, 16000).item()
            speech_probs.append(prob)

        if not speech_probs:
            return False

        # Speech detected if any window exceeds threshold
        max_prob = max(speech_probs)
        return max_prob > threshold
    except Exception:
        return True  # On error, let Whisper decide


# ---------------------------------------------------------------------------
# faster-whisper transcription
# ---------------------------------------------------------------------------

def _get_faster_model(model_name: str = "large-v3-turbo"):
    """Load faster-whisper model (cached)."""
    global _faster_model
    if _faster_model is None:
        from faster_whisper import WhisperModel
        _faster_model = WhisperModel(model_name, device="cuda", compute_type="float16")
    return _faster_model


def transcribe_faster(audio_path: str, model_name: str = "large-v3-turbo") -> str:
    """Transcribe using faster-whisper with Silero VAD pre-filter."""
    # VAD pre-filter: skip if no speech detected
    if not has_speech_vad(audio_path):
        return ""

    model = _get_faster_model(model_name)
    segments, info = model.transcribe(
        audio_path,
        language="ja",
        beam_size=5,
        no_speech_threshold=0.6,
        condition_on_previous_text=False,
    )

    texts = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            # Hallucination filter
            is_hallucination = False
            for pattern in _HALLUCINATION_PATTERNS:
                if pattern in text:
                    is_hallucination = True
                    break
            if not is_hallucination and len(text) > 2:
                texts.append(text)

    return "".join(texts)


# ---------------------------------------------------------------------------
# whisper.cpp HTTP server transcription
# ---------------------------------------------------------------------------

_WHISPER_CPP_URL = os.getenv("WHISPER_CPP_URL", "http://127.0.0.1:2022/v1/audio/transcriptions")


async def transcribe_whisper_cpp(audio_path: str) -> str:
    """Transcribe using whisper.cpp HTTP server with Silero VAD pre-filter."""
    # VAD pre-filter: skip if no speech detected
    if not has_speech_vad(audio_path):
        return ""

    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        with open(audio_path, "rb") as f:
            resp = await client.post(
                _WHISPER_CPP_URL,
                files={"file": (Path(audio_path).name, f, "audio/wav")},
                data={"model": "whisper-1", "language": "ja", "response_format": "json"},
            )
        if resp.status_code == 200:
            text = resp.json().get("text", "").strip()
            if text:
                for pattern in _HALLUCINATION_PATTERNS:
                    if pattern in text:
                        return ""
            if text and len(text) <= 2:
                return ""
            return text
        raise RuntimeError(f"whisper.cpp server error {resp.status_code}: {resp.text[:200]}")


# ---------------------------------------------------------------------------
# Moonshine Voice transcription (local, CPU-only)
# ---------------------------------------------------------------------------

_moonshine_model = None  # Cached (model_path, model_arch)


def _get_moonshine_model(language: str = "ja"):
    """Get or load cached Moonshine model."""
    global _moonshine_model
    if _moonshine_model is None:
        import moonshine_voice
        model_path, model_arch = moonshine_voice.get_model_for_language(language)
        _moonshine_model = (model_path, model_arch)
    return _moonshine_model


def transcribe_moonshine(audio_path: str, language: str = "ja") -> str:
    """Transcribe using Moonshine Voice (local, CPU-only)."""
    import moonshine_voice
    from moonshine_voice.transcriber import Transcriber, LineCompleted

    model_path, model_arch = _get_moonshine_model(language)
    t = Transcriber(model_path=model_path, model_arch=model_arch)
    stream = t.create_stream()

    results = []
    def on_event(event):
        if isinstance(event, LineCompleted):
            text = event.line.text.strip()
            if text:
                results.append(text)

    stream.add_listener(on_event)
    audio_data, sr = moonshine_voice.load_wav_file(audio_path)
    stream.start()
    chunk_size = sr // 10  # 100ms chunks
    for i in range(0, len(audio_data), chunk_size):
        stream.add_audio(audio_data[i:i+chunk_size], sr)
    stream.stop()
    stream.close()

    text = " ".join(results)
    # Filter hallucinations
    for pattern in _HALLUCINATION_PATTERNS:
        if pattern in text:
            return ""
    return text


# ---------------------------------------------------------------------------
# Groq API transcription
# ---------------------------------------------------------------------------

async def transcribe_groq(audio_path: str, api_key: str) -> str:
    """Transcribe using Groq Whisper API."""
    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        with open(audio_path, "rb") as f:
            resp = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (Path(audio_path).name, f, "audio/wav")},
                data={"model": "whisper-large-v3", "language": "ja", "response_format": "text"},
            )
        if resp.status_code == 200:
            return resp.text.strip()
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:200]}")


def _get_whisper_model(model_name: str):
    """Get or load cached Whisper model."""
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model(model_name)
    return _whisper_model


def transcribe_local(audio_path: str, model_name: str = "base") -> str:
    """Transcribe using local OpenAI Whisper."""
    model = _get_whisper_model(model_name)
    result = model.transcribe(
        audio_path, language="ja",
        no_speech_threshold=0.6, condition_on_previous_text=False,
    )
    text = result.get("text", "").strip()
    if text:
        for pattern in _HALLUCINATION_PATTERNS:
            if pattern in text:
                return ""
    if text and len(text) <= 2:
        return ""
    return text


_SMART_THRESHOLD_SECS = 3.0  # Speech shorter than this → Moonshine, longer → Groq


async def transcribe_smart(audio_path: str) -> str:
    """Smart engine: Moonshine for short audio, Groq for longer audio.

    Uses VAD to estimate actual speech duration in the audio chunk.
    Short speech (<= 3s): Moonshine (local, fast, no API cost)
    Long speech (> 3s): Groq Whisper API (cloud GPU, accurate)
    Falls back to Moonshine if Groq is unavailable.
    """
    # Need VAD model loaded to measure speech duration
    speech_secs = await asyncio.to_thread(get_speech_duration_vad, audio_path)

    groq_key = os.getenv("GROQ_API_KEY")

    if speech_secs <= _SMART_THRESHOLD_SECS or not groq_key:
        # Short speech or no Groq key → use Moonshine (local, fast)
        try:
            return await asyncio.to_thread(transcribe_moonshine, audio_path)
        except Exception as e:
            print(f"[smart] Moonshine failed ({e}), falling back to Groq", file=sys.stderr)
            if groq_key:
                return await transcribe_groq(audio_path, groq_key)
            return ""
    else:
        # Long speech → use Groq (cloud GPU, more accurate)
        try:
            return await transcribe_groq(audio_path, groq_key)
        except Exception as e:
            print(f"[smart] Groq failed ({e}), falling back to Moonshine", file=sys.stderr)
            try:
                return await asyncio.to_thread(transcribe_moonshine, audio_path)
            except Exception:
                return ""


async def transcribe(audio_path: str, model_name: str = "base", engine: str = "auto") -> str:
    """Transcribe audio.

    Engine priority:
      - 'cpp': whisper.cpp HTTP server + Silero VAD (default)
      - 'faster': faster-whisper + Silero VAD (GPU)
      - 'whisper': openai-whisper (CPU)
      - 'groq': Groq Whisper API (cloud)
      - 'smart': Auto-select Moonshine (<= 3s speech) or Groq (> 3s)
      - 'auto': cpp > faster > whisper (fallback chain)
    """
    if engine == "smart":
        return await transcribe_smart(audio_path)

    if engine == "moonshine" or engine == "auto":
        try:
            return await asyncio.to_thread(transcribe_moonshine, audio_path)
        except Exception as e:
            if engine == "moonshine":
                raise
            print(f"Moonshine failed ({e}), trying next engine", file=sys.stderr)

    if engine == "cpp" or engine == "auto":
        try:
            return await transcribe_whisper_cpp(audio_path)
        except Exception as e:
            if engine == "cpp":
                raise
            print(f"whisper.cpp failed ({e}), trying next engine", file=sys.stderr)

    if engine == "groq" or engine == "auto":
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                return await transcribe_groq(audio_path, groq_key)
            except Exception as e:
                if engine == "groq":
                    raise
                print(f"Groq failed ({e}), trying next engine", file=sys.stderr)

    if engine == "faster" or engine == "auto":
        try:
            return await asyncio.to_thread(transcribe_faster, audio_path, model_name)
        except Exception as e:
            if engine == "faster":
                raise
            print(f"faster-whisper failed ({e}), falling back to openai-whisper", file=sys.stderr)

    # Fallback: openai-whisper
    return await asyncio.to_thread(transcribe_local, audio_path, model_name)


# ---------------------------------------------------------------------------
# Wait mode: loop short chunks until speech detected
# ---------------------------------------------------------------------------

async def wait_for_speech(
    source: str, timeout: float, chunk_secs: float, model: str, raw: bool,
    engine: str = "cpp",
) -> str | None:
    """Record in short chunks, return transcript when speech is detected."""
    import time
    deadline = time.time() + timeout

    if not raw:
        print(f"👂 Listening... (engine={engine}, timeout {timeout:.0f}s, chunk {chunk_secs:.0f}s)", flush=True)

    # Preload models
    if engine == "moonshine":
        await asyncio.to_thread(_get_moonshine_model)
    elif engine in ("cpp", "faster"):
        # VAD model needed for both cpp and faster
        await asyncio.to_thread(_get_vad_model)
    if engine == "faster":
        fw_model = model if model != "small" else "large-v3-turbo"
        await asyncio.to_thread(_get_faster_model, fw_model)
    elif engine not in ("groq", "cpp", "moonshine"):
        await asyncio.to_thread(_get_whisper_model, model)

    while time.time() < deadline:
        remaining = deadline - time.time()
        if remaining < 1:
            break
        dur = min(chunk_secs, remaining)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        tmp_path = f"/tmp/listen_chunk_{ts}.wav"

        try:
            await record_chunk(source, dur, tmp_path)

            if not Path(tmp_path).exists() or Path(tmp_path).stat().st_size < 1000:
                continue

            if engine == "cpp":
                text = await transcribe_whisper_cpp(tmp_path)
            elif engine == "faster":
                text = await asyncio.to_thread(
                    transcribe_faster, tmp_path,
                    model if model != "small" else "large-v3-turbo",
                )
            else:
                rms = compute_rms(tmp_path)
                if rms < 350:
                    continue
                if not raw:
                    print(f"🔊 Speech detected (RMS: {rms:.0f}), transcribing...", flush=True)
                text = await transcribe(tmp_path, model, engine=engine)

            if text:
                return text
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    return None


_HEARING_DIR = _PROJECT_ROOT / "memory" / "hearing"
_HEARING_DIR.mkdir(parents=True, exist_ok=True)

# Fixed path: always the latest transcriptions (for fast access)
HEARING_LATEST = str(_HEARING_DIR / "latest.txt")


def _hearing_log_path() -> str:
    """Return today's hearing log path (memory/hearing/YYYY-MM-DD.txt)."""
    return str(_HEARING_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.txt")


PID_FILE = "/tmp/ayumu_listen.pid"


# ---------------------------------------------------------------------------
# OpenWakeWord: "Hey Jarvis" 検出スレッド
# ---------------------------------------------------------------------------
# 「OKアユム」(Whisper STT + テキストマッチ)は精度が悪いため、
# OpenWakeWord による "Hey Jarvis" 検出を並行して動かす。
# 将来的に「OKアユム」は廃止し、Hey Jarvis に一本化する予定。

_OWW_THRESHOLD = 0.1
_OWW_CHUNK = 1280  # 80ms at 16kHz
_OWW_COOLDOWN = 30  # 検出後のクールダウン（秒）。VoiceMode起動に時間がかかるため長めに。


def _openwakeword_thread(raw: bool = False) -> None:
    """OpenWakeWord でウェイクワード "Hey Jarvis" を検出するスレッド。

    ffmpegで直接マイクからPCMストリームを取得し、80msフレーム単位で
    OpenWakeWordに送る。閾値を超えたらlatest.txtに🎯マーカーを書き込む。
    """
    import threading

    import numpy as np
    from openwakeword.model import Model as OWWModel

    import warnings
    warnings.filterwarnings("ignore")

    if not raw:
        print("   [OWW] Loading OpenWakeWord model...", flush=True)
    oww_model = OWWModel()
    model_names = list(oww_model.models.keys())
    if not raw:
        print(f"   [OWW] Models: {model_names}", flush=True)
        print(f"   [OWW] Threshold: {_OWW_THRESHOLD}, cooldown: {_OWW_COOLDOWN}s", flush=True)

    # ffmpegでマイク入力をPCMパイプ（スリープ復帰で自動再接続）
    import subprocess

    cmd = [
        _WIN_FFMPEG,
        "-f", "dshow",
        "-i", f"audio={_WIN_MIC}",
        "-ar", "16000",
        "-ac", "1",
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-",
    ]

    last_trigger = 0.0
    while True:  # スリープ復帰時の自動リトライループ
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if not raw:
            print("   [OWW] Listening for 'Hey Jarvis'...", flush=True)

        try:
            while True:
                data = proc.stdout.read(_OWW_CHUNK * 2)  # 16bit = 2 bytes/sample
                if not data:
                    break  # ffmpeg死亡（スリープ等）→ 外側ループでリトライ

                # Skip while Ayumu is speaking or voice session active
                if Path("/tmp/ayumu_speaking").exists():
                    continue
                if Path("/tmp/ayumu_voice_session.lock").exists():
                    continue

                audio = np.frombuffer(data, dtype=np.int16)
                prediction = oww_model.predict(audio)

                for name, score in prediction.items():
                    if score > _OWW_THRESHOLD:
                        now = time.time()
                        if now - last_trigger < _OWW_COOLDOWN:
                            continue
                        last_trigger = now

                        timestamp = datetime.now().strftime("%H:%M:%S")
                        line = f"[{timestamp}] 🎯 Hey Jarvis (oww:{score:.3f})"
                        # latest.txt と日付ログの両方に書き込み
                        with open(HEARING_LATEST, "a") as f:
                            f.write(line + "\n")
                        with open(_hearing_log_path(), "a") as f:
                            f.write(line + "\n")
                        if not raw:
                            print(f"🎯 {line}", flush=True)
        except Exception as e:
            if not raw:
                print(f"   [OWW] Error: {e}", flush=True)
        finally:
            proc.terminate()

        # マイク切断 → 5秒待って再接続
        if not raw:
            print("   [OWW] Mic disconnected, retrying in 5s...", flush=True)
        time.sleep(5)


def log_ayumu_speech(text: str) -> None:
    """Ayumuの発言をhearing logに記録する（🤖プレフィックス付き）。

    talk.pyやVoiceModeから呼ぶことで、latest.txtにAyumuの発言も残る。
    voice_source.pyは🤖行をスキップするので無限ループしない。
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] 🤖 {text}"
    with open(HEARING_LATEST, "a") as f:
        f.write(line + "\n")
    with open(_hearing_log_path(), "a") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------------------
# Continuous listening (listen_on / listen_off / read_hearing)
# ---------------------------------------------------------------------------

async def continuous_listen(source: str, chunk_secs: float, model: str, raw: bool, engine: str = "cpp") -> None:
    """Run continuous listening loop. Writes transcripts to hearing log.

    With engine='cpp', uses Silero VAD + whisper.cpp HTTP server.
    With engine='faster', uses Silero VAD + faster-whisper (GPU heavy).
    VAD pre-filters silence to prevent hallucinations.
    """
    import signal

    # Write PID so --off can stop us
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Clear latest.txt on start (fresh session)
    with open(HEARING_LATEST, "w") as f:
        f.write("")

    if not raw:
        print(f"👂 Continuous listening started (engine={engine}, chunk={chunk_secs}s, source={source})")
        print(f"   Latest: {HEARING_LATEST}")
        print(f"   Stop: uv run tools/listen.py --off")

    # Preload models based on engine
    if engine in ("moonshine", "smart"):
        if not raw:
            print("   Loading Moonshine model...", flush=True)
        await asyncio.to_thread(_get_moonshine_model)
    if engine in ("cpp", "faster", "smart"):
        if not raw:
            print("   Loading VAD model...", flush=True)
        await asyncio.to_thread(_get_vad_model)
    if engine == "faster":
        if not raw:
            print("   Loading faster-whisper model...", flush=True)
        await asyncio.to_thread(_get_faster_model, model if model != "small" else "large-v3-turbo")
    elif engine not in ("groq", "cpp", "moonshine", "smart"):
        await asyncio.to_thread(_get_whisper_model, model)

    # Start OpenWakeWord detection thread (Hey Jarvis)
    import threading as _threading
    oww_t = _threading.Thread(target=_openwakeword_thread, args=(raw,), daemon=True)
    oww_t.start()

    if not raw:
        print("   Ready. Listening...", flush=True)

    def handle_signal(sig, frame):
        if not raw:
            print("\n👂 Listening stopped.")
        Path(PID_FILE).unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    while True:
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        tmp_path = f"/tmp/listen_cont_{ts_str}.wav"
        try:
            await record_chunk(source, chunk_secs, tmp_path)

            if not Path(tmp_path).exists() or Path(tmp_path).stat().st_size < 1000:
                continue

            # Skip while Ayumu is speaking (prevent self-transcription)
            if Path("/tmp/ayumu_speaking").exists():
                continue

            if engine == "smart":
                # Auto: Moonshine for short speech, Groq for longer speech
                text = await transcribe_smart(tmp_path)
            elif engine == "moonshine":
                # Moonshine Voice (local, CPU-only, no external VAD needed)
                text = await asyncio.to_thread(transcribe_moonshine, tmp_path)
            elif engine == "cpp":
                # VAD + whisper.cpp HTTP server
                text = await transcribe_whisper_cpp(tmp_path)
            elif engine == "faster":
                # VAD + faster-whisper (no RMS check needed, VAD handles it)
                text = await asyncio.to_thread(transcribe_faster, tmp_path, model if model != "small" else "large-v3-turbo")
            else:
                # Legacy: RMS check + openai-whisper/groq
                rms = compute_rms(tmp_path)
                if rms < 350:
                    continue
                text = await transcribe(tmp_path, model, engine=engine)

            if text:
                timestamp = datetime.now().strftime("%H:%M:%S")
                line = f"[{timestamp}] {text}"
                # Write to both: latest (fixed path) and date log (archive)
                with open(HEARING_LATEST, "a") as f:
                    f.write(line + "\n")
                with open(_hearing_log_path(), "a") as f:
                    f.write(line + "\n")
                if not raw:
                    print(line, flush=True)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            await asyncio.sleep(1)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


def stop_continuous() -> None:
    """Stop continuous listening by sending SIGTERM to the PID."""
    import signal
    if not Path(PID_FILE).exists():
        print("Not listening.")
        return
    try:
        pid = int(Path(PID_FILE).read_text().strip())
        os.kill(pid, signal.SIGTERM)
        Path(PID_FILE).unlink(missing_ok=True)
        print(f"Stopped listener (pid={pid})")
    except ProcessLookupError:
        Path(PID_FILE).unlink(missing_ok=True)
        print("Listener already stopped.")
    except Exception as e:
        print(f"Error stopping: {e}", file=sys.stderr)


def read_hearing(raw: bool) -> None:
    """Read new entries from hearing log since last read."""
    pos_file = "/tmp/ayumu_hearing_pos.txt"
    pos = 0
    if Path(pos_file).exists():
        try:
            pos = int(Path(pos_file).read_text().strip())
        except ValueError:
            pos = 0

    if not Path(HEARING_LATEST).exists():
        if raw:
            print("")
        else:
            print("(not listening - use --on first)")
        return

    with open(HEARING_LATEST, "r") as f:
        f.seek(pos)
        new_text = f.read()
        new_pos = f.tell()

    Path(pos_file).write_text(str(new_pos))

    if new_text.strip():
        if raw:
            print(new_text.strip())
        else:
            print(f"--- Heard ---\n{new_text.strip()}")
    else:
        if raw:
            print("")
        else:
            print("(nothing new)")


# ---------------------------------------------------------------------------
# File change detection (importable from other scripts)
# ---------------------------------------------------------------------------

def wait_for_new_text(
    path: str | None = None,
    timeout: float = 60.0,
    poll_interval: float = 0.3,
) -> str | None:
    """Wait for new text to appear in the hearing log file.

    Tracks the last-read position and returns only new content.
    Returns None on timeout.

    Usage from other scripts:
        from tools.listen import wait_for_new_text
        text = wait_for_new_text(timeout=10)
        if text:
            print(f"Heard: {text}")
    """
    import time

    if path is None:
        path = HEARING_LATEST
    pos_file = f"{path}.pos"
    pos = 0
    if Path(pos_file).exists():
        try:
            pos = int(Path(pos_file).read_text().strip())
        except (ValueError, OSError):
            pos = 0

    deadline = time.time() + timeout
    while time.time() < deadline:
        if Path(path).exists():
            try:
                size = Path(path).stat().st_size
                if size > pos:
                    with open(path, "r") as f:
                        f.seek(pos)
                        new_text = f.read()
                        new_pos = f.tell()
                    if new_text.strip():
                        Path(pos_file).write_text(str(new_pos))
                        return new_text.strip()
            except OSError:
                pass
        time.sleep(poll_interval)

    return None


def wait_for_speech_text(timeout: float = 60.0) -> str | None:
    """Convenience: wait for new speech in the hearing log.

    Assumes --on mode is running in another process.
    Returns the raw transcript text (without timestamps).
    """
    raw = wait_for_new_text(timeout=timeout)
    if raw is None:
        return None
    # Strip timestamps like "[HH:MM:SS] "
    lines = []
    for line in raw.strip().split("\n"):
        if line.startswith("[") and "] " in line:
            lines.append(line.split("] ", 1)[1])
        else:
            lines.append(line)
    return " ".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(description="Record audio and transcribe")
    parser.add_argument("--source", choices=["pc", "win", "camera"], default="win",
                        help="Audio source: win (Windows mic), pc (WSLg), camera (RTSP). Default: win")
    parser.add_argument("--duration", type=float, default=5.0,
                        help="Fixed recording duration in seconds (default: 5.0)")
    parser.add_argument("--wait", action="store_true",
                        help="Wait mode: listen until speech detected")
    parser.add_argument("--timeout", type=float, default=10.0,
                        help="Timeout for --wait mode in seconds (default: 10)")
    parser.add_argument("--chunk", type=float, default=3.0,
                        help="Chunk size for --wait mode in seconds (default: 3)")
    parser.add_argument("--on", action="store_true",
                        help="Start continuous listening (writes to memory/hearing/)")
    parser.add_argument("--off", action="store_true",
                        help="Stop continuous listening")
    parser.add_argument("--read", action="store_true",
                        help="Read new entries from hearing log")
    parser.add_argument("--poll", type=float, default=None, metavar="SECS",
                        help="Wait for new speech (uses --on background process). Returns transcript text.")
    parser.add_argument("--no-transcribe", action="store_true",
                        help="Record only, skip STT")
    parser.add_argument("--model", default="small",
                        help="Whisper model size (default: small)")
    parser.add_argument("--engine", choices=["cpp", "faster", "whisper", "groq", "moonshine", "smart", "auto"],
                        default="cpp",
                        help="STT engine: cpp (whisper.cpp server+VAD, default), faster (faster-whisper+VAD), whisper (openai-whisper), groq (API), moonshine (local CPU), smart (auto Moonshine/Groq by speech length), auto")
    parser.add_argument("--raw", action="store_true",
                        help="Print only transcript text")
    parser.add_argument("--output", type=str, default=None,
                        help="Save WAV to specific path")
    args = parser.parse_args()

    # --on mode (continuous listening, writes to hearing log)
    if args.on:
        await continuous_listen(args.source, args.chunk, args.model, args.raw, engine=args.engine)
        return

    # --off mode
    if args.off:
        stop_continuous()
        return

    # --read mode
    if args.read:
        read_hearing(args.raw)
        return

    # --poll mode: wait for new speech from background --on process
    if args.poll is not None:
        text = wait_for_speech_text(timeout=args.poll)
        if text:
            print(text)
        else:
            print("")
        return

    # --wait mode
    if args.wait:
        text = await wait_for_speech(
            args.source, args.timeout, args.chunk, args.model, args.raw,
            engine=args.engine,
        )
        if text:
            if args.raw:
                print(text)
            else:
                print(f"📝 {text}")
        else:
            if args.raw:
                print("")
            else:
                print("📝 (timeout, no speech detected)")
        return

    # Fixed duration mode
    if args.output:
        output = args.output
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"/tmp/listen_{ts}.wav"

    src = "PC mic" if args.source == "pc" else "camera mic"
    if not args.raw:
        print(f"🎤 Recording from {src} ({args.duration}s)...")

    await record_chunk(args.source, args.duration, output)

    if not Path(output).exists() or Path(output).stat().st_size < 1000:
        print("Recording failed (file too small)", file=sys.stderr)
        sys.exit(1)

    rms = compute_rms(output)
    if not args.raw:
        print(f"📊 RMS: {rms:.1f}")

    if args.no_transcribe:
        if not args.raw:
            print(f"💾 Saved: {output}")
        return

    if rms < 200:
        if args.raw:
            print("")
        else:
            print("📝 (silence)")
        return

    text = await transcribe(output, args.model, engine=args.engine)
    if text:
        if args.raw:
            print(text)
        else:
            print(f"📝 {text}")
    else:
        if args.raw:
            print("")
        else:
            print("📝 (no speech)")

    if not args.output:
        Path(output).unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
