"""Clipboard and paste helpers — macOS + Linux.

macOS path (platform.system() == "Darwin"):
  - Clipboard:  pbcopy
  - Paste:      Cmd+V via pynput

Linux path (platform.system() == "Linux"):
  - Clipboard:  xclip → xsel → wl-copy (tried in order)
  - Paste keystroke:
      * X11:     Ctrl+V via pynput
      * Wayland: ydotool key ctrl+v → pynput fallback

Any changes to the macOS logic are intentionally wrapped so the Apple-side
behavior remains untouched when this module is imported on Darwin.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import time

from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)

_keyboard = Controller()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def copy_to_clipboard(text: str) -> None:
    if platform.system() == "Linux":
        _copy_to_clipboard_linux(text)
    else:
        # macOS — original implementation, untouched.
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
    logger.debug("Copied %d characters to clipboard", len(text))


def paste_active_field() -> None:
    # Small delay so the clipboard write settles before the keystroke fires.
    time.sleep(0.05)
    if platform.system() == "Linux":
        _paste_linux()
    else:
        # macOS — original implementation, untouched.
        with _keyboard.pressed(Key.cmd):
            _keyboard.press("v")
            _keyboard.release("v")
        logger.debug("Paste keystroke sent via pynput (Cmd+V)")


def copy_and_paste(text: str) -> None:
    copy_to_clipboard(text)
    paste_active_field()


# ---------------------------------------------------------------------------
# Linux clipboard helpers
# ---------------------------------------------------------------------------

def _copy_to_clipboard_linux(text: str) -> None:
    """Write *text* to the system clipboard using the first available tool."""
    if _is_wayland():
        _try_clipboard_tools(
            text,
            candidates=[
                (["wl-copy"], {}),
                (["xclip", "-selection", "clipboard"], {}),
                (["xsel", "--clipboard", "--input"], {}),
            ],
            error_hint="Install wl-clipboard (wl-copy), xclip, or xsel.",
        )
    else:
        _try_clipboard_tools(
            text,
            candidates=[
                (["xclip", "-selection", "clipboard"], {}),
                (["xsel", "--clipboard", "--input"], {}),
                (["wl-copy"], {}),
            ],
            error_hint="Install xclip or xsel (sudo apt-get install xclip).",
        )


def _try_clipboard_tools(
    text: str,
    candidates: list[tuple[list[str], dict]],
    error_hint: str,
) -> None:
    for cmd, kwargs in candidates:
        try:
            subprocess.run(cmd, input=text, text=True, check=True, timeout=5, **kwargs)
            logger.debug("Clipboard written via %s", cmd[0])
            return
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError as exc:
            logger.warning("Clipboard tool %s failed: %s", cmd[0], exc)
            continue
    raise RuntimeError(
        f"No clipboard tool succeeded. {error_hint}"
    )


# ---------------------------------------------------------------------------
# Linux paste helpers
# ---------------------------------------------------------------------------

def _paste_linux() -> None:
    """Send Ctrl+V using the best available method for the running session."""
    if _is_wayland():
        _paste_wayland()
    else:
        _paste_x11()


def _paste_x11() -> None:
    """Send Ctrl+V on X11 via pynput."""
    with _keyboard.pressed(Key.ctrl):
        _keyboard.press("v")
        _keyboard.release("v")
    logger.debug("Paste keystroke sent via pynput (Ctrl+V, X11)")


def _paste_wayland() -> None:
    """Send Ctrl+V on Wayland.

    Tries ydotool first (works on pure Wayland without XWayland), then falls
    back to pynput which works when XWayland is present.
    """
    try:
        subprocess.run(
            ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
            check=True,
            timeout=3,
        )
        logger.debug("Paste keystroke sent via ydotool (Wayland)")
        return
    except FileNotFoundError:
        logger.debug("ydotool not found, falling back to pynput for Wayland paste")
    except subprocess.CalledProcessError as exc:
        logger.warning("ydotool failed (%s), falling back to pynput", exc)

    # pynput fallback — works when XWayland is available.
    with _keyboard.pressed(Key.ctrl):
        _keyboard.press("v")
        _keyboard.release("v")
    logger.debug("Paste keystroke sent via pynput (Ctrl+V, Wayland/XWayland)")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _is_wayland() -> bool:
    """Return True when running under a Wayland compositor."""
    return bool(os.environ.get("WAYLAND_DISPLAY"))
