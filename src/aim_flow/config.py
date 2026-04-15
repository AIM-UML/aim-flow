"""Application configuration."""

import os
from pathlib import Path
import platform

APP_NAME = "AIM Flow"


def resource_path(name: str) -> Path:
    """Return the absolute path to a bundled resource file.

    Checks the NSBundle resource directory first (correct for .app bundles
    and PyInstaller builds), then falls back to the project root (correct
    for running from source).
    """
    try:
        from AppKit import NSBundle  # type: ignore
        bundle_resource_path = NSBundle.mainBundle().resourcePath()
        if bundle_resource_path:
            candidate = Path(str(bundle_resource_path)) / name
            if candidate.exists():
                return candidate
    except Exception:
        pass
    return PROJECT_ROOT / name

IS_MACOS = platform.system() == "Darwin"
MODEL_SIZE = os.environ.get("AIM_FLOW_MODEL", "small")

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024

DEFAULT_HOTKEY = "Option+Space" if IS_MACOS else "Ctrl+Shift+Space"
PYNPUT_HOTKEY = "<alt>+<space>" if IS_MACOS else "<ctrl>+<shift>+<space>"

TRANSCRIPTION_LANGUAGE = None

STATUS_LOGO_NAME = "status_logo.png"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

STATUS_ICON_HEIGHT = 18.0
STATUS_ICON_WIDTH = 18.0
STATUS_WAVE_WIDTH = 24.0
STATUS_ITEM_SPACING = 4.0
WAVE_BAR_COUNT = 4
WAVE_BAR_WIDTH = 4.0
WAVE_BAR_GAP = 2.0
WAVE_MIN_HEIGHT = 2.0
WAVE_MAX_HEIGHT = 17.0

FFMPEG_CANDIDATE_PATHS = [
    "/opt/homebrew/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/usr/bin/ffmpeg",
]
SYSTEM_PATH_FALLBACK = ":".join(
    [
        *dict.fromkeys(
            [os.environ.get("PATH", ""), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
        )
    ]
)
