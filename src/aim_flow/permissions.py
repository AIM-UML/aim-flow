"""macOS permission checks and user guidance.

AIM Flow needs two permissions:
  - Accessibility   : required for global hotkeys (pynput) and auto-paste
                      (osascript System Events keystroke).
  - Microphone      : required for PyAudio to capture audio input.

Microphone access is typically requested automatically by macOS when PyAudio
first opens the audio stream, so we focus on proactively checking and
explaining Accessibility here.
"""

from __future__ import annotations

import ctypes
import logging
import subprocess

import rumps

from . import config

logger = logging.getLogger(__name__)


def is_accessibility_trusted() -> bool:
    """Return True if this process has been granted Accessibility permission.

    Uses AXIsProcessTrusted() from the ApplicationServices framework via
    ctypes so no extra pyobjc package is required.
    """
    try:
        lib = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        return bool(lib.AXIsProcessTrusted())
    except Exception as exc:
        logger.warning("Could not check accessibility permission: %s", exc)
        return False


def open_accessibility_settings() -> None:
    """Open the Accessibility section of System Settings / System Preferences."""
    subprocess.run(
        [
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        ],
        check=False,
    )


def open_microphone_settings() -> None:
    """Open the Microphone section of System Settings / System Preferences."""
    subprocess.run(
        [
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
        ],
        check=False,
    )


def check_and_prompt() -> None:
    """Check Accessibility permission and show a dialog if it is not granted.

    Called once approximately 1.5 seconds after the app starts (from a rumps
    Timer, which runs on the main thread).  Blocking is acceptable here since
    this is a first-launch workflow.
    """
    if is_accessibility_trusted():
        logger.info("Accessibility permission granted")
        return

    logger.warning(
        "Accessibility permission not granted for this process. "
        "The global hotkey and auto-paste will not work until it is enabled."
    )

    response = rumps.alert(
        title="Accessibility Permission Required",
        message=(
            "AIM Flow needs Accessibility access to:\n\n"
            f"  - Detect the global hotkey ({config.DEFAULT_HOTKEY})\n"
            "  - Paste transcribed text into the active field\n\n"
            "To grant access:\n"
            "  System Settings > Privacy & Security > Accessibility\n\n"
            "Enable the toggle for Terminal (or AIM Flow if running as an app).\n"
            "Then restart AIM Flow."
        ),
        ok="Open Settings",
        cancel="Later",
    )

    if response:
        open_accessibility_settings()
