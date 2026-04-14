"""Clipboard and paste helpers for macOS.

Paste is done via pynput's keyboard controller (Cmd+V), which only requires
Accessibility permission — no Automation / System Events needed.
"""

from __future__ import annotations

import logging
import subprocess
import time

from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)

_keyboard = Controller()


def copy_to_clipboard(text: str) -> None:
    subprocess.run(["pbcopy"], input=text, text=True, check=True)
    logger.debug("Copied %d characters to clipboard", len(text))


def paste_active_field() -> None:
    # Small delay so the clipboard write settles before the keystroke fires.
    time.sleep(0.05)
    with _keyboard.pressed(Key.cmd):
        _keyboard.press("v")
        _keyboard.release("v")
    logger.debug("Paste keystroke sent via pynput (Cmd+V)")


def copy_and_paste(text: str) -> None:
    copy_to_clipboard(text)
    paste_active_field()


_SERVICE_URLS: dict[str, str] = {
    "claude": "https://claude.ai/new",
    "chatgpt": "https://chatgpt.com/",
    "grok": "https://grok.com/",
    "gemini": "https://gemini.google.com/",
}


def open_ai_service(service: str, query: str) -> None:
    """Open an AI service in the default browser.

    The query is copied to the clipboard so the user can paste it if the
    service does not support a URL query parameter.

    Args:
        service: One of 'claude', 'chatgpt', 'grok', 'gemini'.
        query: The text to send. May be empty.
    """
    import webbrowser
    from urllib.parse import quote

    base_url = _SERVICE_URLS.get(service, "https://claude.ai/new")

    if query:
        copy_to_clipboard(query)

    if service == "claude" and query:
        webbrowser.open(f"{base_url}?q={quote(query)}")
    else:
        webbrowser.open(base_url)

    logger.debug("Opened %s with query (%d chars)", service, len(query))
