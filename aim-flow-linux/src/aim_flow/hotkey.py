"""Global hotkey support via pynput.

pynput requires Accessibility and Input Monitoring permissions on macOS.
If those permissions are not granted the listener will start but will never
fire.  A warning is logged so the user can see it in the terminal output.
"""

from __future__ import annotations

import logging
from typing import Callable

from pynput import keyboard

from . import config

logger = logging.getLogger(__name__)


class HotkeyManager:
    def __init__(self, callback: Callable[[], None]) -> None:
        self._callback = callback
        self._listener = keyboard.GlobalHotKeys(
            {config.PYNPUT_HOTKEY: self._on_hotkey}
        )

    def _on_hotkey(self) -> None:
        logger.debug("Hotkey triggered: %s", config.PYNPUT_HOTKEY)
        try:
            self._callback()
        except Exception as exc:
            logger.error("Hotkey callback raised an exception: %s", exc, exc_info=True)

    def start(self) -> None:
        try:
            self._listener.start()
            logger.info(
                "Hotkey listener started (%s). "
                "If the hotkey does not respond, grant Accessibility and "
                "Input Monitoring permissions in System Settings, then restart.",
                config.PYNPUT_HOTKEY,
            )
        except Exception as exc:
            logger.error(
                "Failed to start hotkey listener: %s. "
                "Check Accessibility permissions in System Settings.",
                exc,
            )

    def stop(self) -> None:
        try:
            self._listener.stop()
        except Exception as exc:
            logger.warning("Error stopping hotkey listener: %s", exc)
