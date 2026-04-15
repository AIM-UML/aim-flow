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
        self._pressed_keys: set[object] = set()
        self._option_candidate_active = False
        self._option_used_with_other_key = False
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

    def _trigger_option_hotkey(self) -> None:
        now = time.monotonic()
        if now - self._last_triggered_at < 0.2:
            return
        self._last_triggered_at = now
        logger.debug("Hotkey triggered: solo Option key")
        self._on_hotkey()

    def _on_press(self, key) -> None:
        key = self._canonical_key(key)
        if self._is_option_key(key):
            if not any(self._is_option_key(pressed) for pressed in self._pressed_keys):
                self._option_candidate_active = True
                self._option_used_with_other_key = False
        elif any(self._is_option_key(pressed) for pressed in self._pressed_keys):
            self._option_used_with_other_key = True

        self._pressed_keys.add(key)

    def _on_release(self, key) -> None:
        key = self._canonical_key(key)
        was_option_key = self._is_option_key(key)
        self._pressed_keys.discard(key)

        if not was_option_key:
            return

        option_still_pressed = any(self._is_option_key(pressed) for pressed in self._pressed_keys)
        if (
            self._option_candidate_active
            and not self._option_used_with_other_key
            and not option_still_pressed
            and not self._pressed_keys
        ):
            self._trigger_option_hotkey()

        if not option_still_pressed:
            self._option_candidate_active = False
            self._option_used_with_other_key = False

    def _build_listener(self) -> keyboard.Listener | keyboard.GlobalHotKeys:
        if config.IS_MACOS:
            return keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
        return keyboard.GlobalHotKeys({config.PYNPUT_HOTKEY: self._on_hotkey})

    def start(self) -> None:
        try:
            self._listener = self._build_listener()
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
