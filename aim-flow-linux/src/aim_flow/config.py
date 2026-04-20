"""Application configuration (Linux-compatible)."""

import os
from pathlib import Path

APP_NAME = "AIM Flow"

# PROJECT_ROOT resolves to aim-flow-linux/ (two levels above this file).
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resource_path(name: str) -> Path:
    """Return the absolute path to a bundled resource file.

    Checks the Linux project root first, then falls back one directory level
    to support co-located installs where the macOS project holds shared assets
    (e.g. status_logo.png lives in the parent aim-flow/ directory).
    """
    candidate = PROJECT_ROOT / name
    if candidate.exists():
        return candidate
    # Fallback: look in the parent directory (co-located macOS project)
    parent_candidate = PROJECT_ROOT.parent / name
    if parent_candidate.exists():
        return parent_candidate
    # Return the primary candidate even if missing; let the caller handle it.
    return candidate


MODEL_SIZE = "small"

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024

DEFAULT_HOTKEY = "ctrl+shift+space"
PYNPUT_HOTKEY = "<ctrl>+<shift>+<space>"

TRANSCRIPTION_LANGUAGE = "en"

STATUS_LOGO_NAME = "status_logo.png"

# Visual constants (kept metric-compatible with the macOS version).
STATUS_ICON_HEIGHT = 18.0
STATUS_ICON_WIDTH = 18.0
STATUS_WAVE_WIDTH = 24.0
STATUS_ITEM_SPACING = 4.0
WAVE_BAR_COUNT = 4
WAVE_BAR_WIDTH = 4.0
WAVE_BAR_GAP = 2.0
WAVE_MIN_HEIGHT = 5.0
WAVE_MAX_HEIGHT = 16.0

# Tray icon pixel size for Linux (rendered by PIL at this resolution).
TRAY_ICON_SIZE = 64

# ffmpeg candidate paths — Linux paths listed first, Homebrew paths kept as
# a convenience fallback for developers running on macOS alongside this copy.
FFMPEG_CANDIDATE_PATHS = [
    "/usr/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/snap/bin/ffmpeg",
    "/opt/homebrew/bin/ffmpeg",  # macOS fallback
]

SYSTEM_PATH_FALLBACK = ":".join(
    dict.fromkeys(
        filter(
            None,
            [
                os.environ.get("PATH", ""),
                "/usr/bin",
                "/usr/local/bin",
                "/snap/bin",
                "/bin",
                "/opt/homebrew/bin",
            ],
        )
    )
)

# Meeting recorder settings
MEETING_OUTPUT_DIR = os.path.expanduser("~/Documents/AIM_Flow_Meetings")
MEETING_HOTKEY = "<ctrl>+<shift>+m"
OLLAMA_INSTALL_URL = "https://ollama.com/download"

# Audio input settings
SELECTED_MIC_INDEX: int | None = None
MIC_PREFERENCE_FILE = os.path.expanduser("~/.aim_flow_mic_preference")


def load_mic_preference() -> int | None:
    """Load the user's saved microphone preference."""
    if not os.path.exists(MIC_PREFERENCE_FILE):
        return None
    try:
        with open(MIC_PREFERENCE_FILE, "r", encoding="utf-8") as handle:
            value = handle.read().strip()
        if not value:
            return None
        return int(value)
    except Exception:
        return None


def save_mic_preference(device_index: int | None) -> None:
    """Persist the selected microphone index."""
    with open(MIC_PREFERENCE_FILE, "w", encoding="utf-8") as handle:
        handle.write(str(device_index) if device_index is not None else "")
