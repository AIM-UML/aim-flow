"""Global hotkey support via pynput."""

from __future__ import annotations

import logging
import time
from typing import Callable

from pynput import keyboard

from . import config

logger = logging.getLogger(__name__)


class HotkeyManager:
    def __init__(self, callback: Callable[[], None]) -> None:
        self._callback = callback
        self._listener: keyboard.Listener | keyboard.GlobalHotKeys | None = None
        self._option_pressed = False
        self._command_pressed = False
        self._combo_active = False
        self._last_triggered_at = 0.0

    def _on_hotkey(self) -> None:
        logger.debug("Hotkey triggered: %s", config.DEFAULT_HOTKEY)
        try:
            self._callback()
        except Exception as exc:
            logger.error("Hotkey callback raised an exception: %s", exc, exc_info=True)

    def _canonical_key(self, key):
        if self._listener is not None and hasattr(self._listener, "canonical"):
            try:
                key = self._listener.canonical(key)
            except Exception:
                pass
        return key

    def _is_option_key(self, key) -> bool:
        return key in {keyboard.Key.alt, keyboard.Key.alt_r}

    def _is_command_key(self, key) -> bool:
        return key in {keyboard.Key.cmd, keyboard.Key.cmd_r}

    def _trigger_once(self) -> None:
        now = time.monotonic()
        if now - self._last_triggered_at < 0.2:
            return
        self._last_triggered_at = now
        self._on_hotkey()

    def _on_press(self, key) -> None:
        key = self._canonical_key(key)
        if self._is_option_key(key):
            self._option_pressed = True
        elif self._is_command_key(key):
            self._command_pressed = True

        if self._option_pressed and self._command_pressed and not self._combo_active:
            self._combo_active = True
            self._trigger_once()

    def _on_release(self, key) -> None:
        key = self._canonical_key(key)
        if self._is_option_key(key):
            self._option_pressed = False
        elif self._is_command_key(key):
            self._command_pressed = False

        if not (self._option_pressed and self._command_pressed):
            self._combo_active = False

    def start(self) -> None:
        try:
            if config.IS_MACOS:
                self._listener = keyboard.Listener(
                    on_press=self._on_press,
                    on_release=self._on_release,
                )
            else:
                self._listener = keyboard.GlobalHotKeys(
                    {config.PYNPUT_HOTKEY: self._on_hotkey}
                )
            self._listener.start()
            logger.info(
                "Hotkey listener started (%s). "
                "If the hotkey does not respond, grant Accessibility and "
                "Input Monitoring permissions in System Settings, then restart.",
                config.DEFAULT_HOTKEY,
            )
        except Exception as exc:
            logger.error(
                "Failed to start hotkey listener: %s. "
                "Check Accessibility permissions in System Settings.",
                exc,
            )

    def stop(self) -> None:
        try:
            if self._listener is not None:
                self._listener.stop()
        except Exception as exc:
            logger.warning("Error stopping hotkey listener: %s", exc)
