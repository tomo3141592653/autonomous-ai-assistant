#!/usr/bin/env python3
"""ONVIF/RTSP PTZ camera CLI tool (self-contained, no MCP dependency).

Configure via environment variables or .env.local:
    CAMERA_HOST      - Camera IP address (default: 192.168.1.100)
    CAMERA_USERNAME  - Camera username
    CAMERA_PASSWORD  - Camera password
    CAMERA_ONVIF_PORT - ONVIF port (default: 2020)
    CAPTURE_DIR      - Directory for captured images (default: /tmp/wifi-cam-mcp)

Usage:
    uv run tools/camera.py see                    # Capture image, print file path
    uv run tools/camera.py look-left [degrees]    # Pan left (default 30)
    uv run tools/camera.py look-right [degrees]   # Pan right (default 30)
    uv run tools/camera.py look-up [degrees]      # Tilt up (default 20)
    uv run tools/camera.py look-down [degrees]    # Tilt down (default 20)
    uv run tools/camera.py look-around            # 4-direction scan
    uv run tools/camera.py info                   # Device info
    uv run tools/camera.py presets                # List presets
    uv run tools/camera.py goto-preset <id>       # Go to preset
    uv run tools/camera.py position               # Get current position
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

# Load .env.local
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_LOCAL = _PROJECT_ROOT / ".env.local"
if _ENV_LOCAL.exists():
    load_dotenv(_ENV_LOCAL)

# Camera settings (configure via environment variables or .env.local)
CAMERA_HOST = os.getenv("CAMERA_HOST", os.getenv("TAPO_CAMERA_HOST", "192.168.1.100"))
CAMERA_USER = os.getenv("CAMERA_USERNAME", os.getenv("TAPO_USERNAME", "admin"))
CAMERA_PASS = os.getenv("CAMERA_PASSWORD", os.getenv("TAPO_PASSWORD", ""))
ONVIF_PORT = int(os.getenv("CAMERA_ONVIF_PORT", os.getenv("TAPO_ONVIF_PORT", "2020")))
CAPTURE_DIR = Path(os.getenv("CAPTURE_DIR", "/tmp/wifi-cam-mcp"))

# Suppress noisy logs
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

PAN_RANGE_DEG = 180.0
TILT_RANGE_DEG = 90.0


class Direction(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


# ---------------------------------------------------------------------------
# ONVIF Camera
# ---------------------------------------------------------------------------

class Camera:
    """ONVIF PTZ camera controller (self-contained)."""

    def __init__(self):
        self._cam = None
        self._media = None
        self._ptz = None
        self._devmgmt = None
        self._profile_token: str | None = None
        self._connected = False

    async def connect(self):
        if self._connected:
            return
        import onvif as onvif_pkg
        from onvif import ONVIFCamera

        wsdl_dir = os.path.join(os.path.dirname(onvif_pkg.__file__), "wsdl")
        if not os.path.isdir(wsdl_dir):
            wsdl_dir = os.path.join(os.path.dirname(os.path.dirname(onvif_pkg.__file__)), "wsdl")

        self._cam = ONVIFCamera(CAMERA_HOST, ONVIF_PORT, CAMERA_USER, CAMERA_PASS, wsdl_dir=wsdl_dir, adjust_time=True)
        await self._cam.update_xaddrs()
        self._media = await self._cam.create_media_service()
        self._ptz = await self._cam.create_ptz_service()
        self._devmgmt = await self._cam.create_devicemgmt_service()
        profiles = await self._media.GetProfiles()
        if not profiles:
            raise RuntimeError("No media profiles found")
        self._profile_token = profiles[0].token
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        self._connected = True

    async def disconnect(self):
        if self._cam:
            try:
                await self._cam.close()
            except Exception:
                pass
        self._connected = False

    # -- Capture --

    async def capture_image(self) -> str:
        """Capture image, save to file, return file path."""
        image_data = None
        try:
            image_data = await self._cam.get_snapshot(self._profile_token)
        except Exception:
            pass

        if not image_data:
            image_data = await self._capture_rtsp()

        image = Image.open(io.BytesIO(image_data))
        if image.width > 1920 or image.height > 1080:
            image.thumbnail((1920, 1080), Image.LANCZOS)

        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=85)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fpath = str(CAPTURE_DIR / f"capture_{ts}.jpg")
        with open(fpath, "wb") as f:
            f.write(buf.getvalue())
        return fpath

    async def _capture_rtsp(self) -> bytes:
        url = f"rtsp://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_HOST}:554/stream1"
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-rtsp_transport", "tcp", "-i", url,
                "-frames:v", "1", "-f", "image2", "-y", tmp_path,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            if proc.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {stderr.decode(errors='replace')[-300:]}")
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # -- PTZ --

    async def move(self, direction: Direction, degrees: int = 30) -> str:
        degrees = max(1, min(degrees, 90))
        pan_d = tilt_d = 0.0
        match direction:
            case Direction.LEFT:
                pan_d = min(1.0, degrees / PAN_RANGE_DEG)
            case Direction.RIGHT:
                pan_d = -min(1.0, degrees / PAN_RANGE_DEG)
            case Direction.UP:
                tilt_d = min(1.0, degrees / TILT_RANGE_DEG)
            case Direction.DOWN:
                tilt_d = -min(1.0, degrees / TILT_RANGE_DEG)

        await self._ptz.RelativeMove({
            "ProfileToken": self._profile_token,
            "Translation": {"PanTilt": {"x": pan_d, "y": tilt_d}},
        })
        await asyncio.sleep(0.5)
        return f"Moved {direction.value} by {degrees} degrees"

    async def look_around(self) -> list[str]:
        """Capture 4 angles, return file paths."""
        paths = []
        paths.append(await self.capture_image())  # center
        await self.move(Direction.LEFT, 45)
        paths.append(await self.capture_image())   # left
        await self.move(Direction.RIGHT, 90)
        paths.append(await self.capture_image())   # right
        await self.move(Direction.LEFT, 45)
        await self.move(Direction.UP, 20)
        paths.append(await self.capture_image())   # up
        await self.move(Direction.DOWN, 20)
        return paths

    # -- Info --

    async def get_device_info(self) -> dict:
        import zeep.helpers
        info = await self._devmgmt.GetDeviceInformation()
        return zeep.helpers.serialize_object(info, dict)

    async def get_presets(self) -> list[dict]:
        result = await self._ptz.GetPresets({"ProfileToken": self._profile_token})
        return [{"token": p.token, "name": getattr(p, "Name", None) or p.token} for p in (result or [])]

    async def go_to_preset(self, preset_id: str) -> str:
        await self._ptz.GotoPreset({"ProfileToken": self._profile_token, "PresetToken": preset_id})
        await asyncio.sleep(1)
        return f"Moved to preset {preset_id}"

    async def get_position(self) -> dict:
        try:
            status = await self._ptz.GetStatus({"ProfileToken": self._profile_token})
            if status.Position and status.Position.PanTilt:
                return {"pan": status.Position.PanTilt.x, "tilt": status.Position.PanTilt.y}
        except Exception:
            pass
        return {"pan": None, "tilt": None}

    # -- Audio (for listen.py) --

    async def record_audio(self, duration: float = 5.0) -> str:
        """Record audio from camera mic via RTSP. Returns file path."""
        url = f"rtsp://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_HOST}:554/stream1"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fpath = str(CAPTURE_DIR / f"audio_{ts}.wav")
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-rtsp_transport", "tcp", "-i", url,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            "-t", str(duration), "-y", fpath,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=duration + 10.0)
        return fpath


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> None:
    cam = Camera()
    try:
        await cam.connect()
        match args.command:
            case "see":
                print(await cam.capture_image())
            case "look-left" | "look-right" | "look-up" | "look-down":
                d = {"look-left": Direction.LEFT, "look-right": Direction.RIGHT,
                     "look-up": Direction.UP, "look-down": Direction.DOWN}[args.command]
                print(await cam.move(d, args.degrees))
            case "look-around":
                for p in await cam.look_around():
                    print(p)
            case "info":
                print(json.dumps(await cam.get_device_info(), indent=2, default=str))
            case "presets":
                presets = await cam.get_presets()
                for p in presets:
                    print(f"{p['token']}: {p['name']}")
                if not presets:
                    print("No presets found.")
            case "goto-preset":
                print(await cam.go_to_preset(args.preset_id))
            case "position":
                pos = await cam.get_position()
                print(f"pan={pos['pan']}, tilt={pos['tilt']}")
    finally:
        await cam.disconnect()


def main():
    parser = argparse.ArgumentParser(description="ONVIF PTZ camera CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("see", help="Capture image")

    for cmd, default_deg in [("look-left", 30), ("look-right", 30), ("look-up", 20), ("look-down", 20)]:
        p = sub.add_parser(cmd, help=f"Move camera {cmd.split('-')[1]}")
        p.add_argument("degrees", nargs="?", type=int, default=default_deg)

    sub.add_parser("look-around", help="4-direction scan")
    sub.add_parser("info", help="Device info")
    sub.add_parser("presets", help="List presets")

    p_goto = sub.add_parser("goto-preset", help="Go to preset")
    p_goto.add_argument("preset_id")

    sub.add_parser("position", help="Current position")

    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
