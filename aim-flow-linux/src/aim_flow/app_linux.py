"""System-tray application for Linux.

Replicates the functionality of app.py (macOS/rumps) using:
  - pystray   — cross-platform system-tray icon
  - PIL       — icon image rendering (via visuals_linux.py)
  - notify-send — desktop notifications (best-effort)

State machine:
  idle → recording → processing → idle

Threading model:
  Main thread   — pystray event loop (icon.run() blocks here)
  _update_thread — 0.12 s timer loop that refreshes the tray icon
  hotkey thread  — daemon thread managed by HotkeyManager (pynput)
  transcription  — one-shot daemon thread spawned per recording

NOTE: This file must NOT import anything from app.py, visuals.py, or any
macOS-specific module.  All Apple-side code remains untouched in its own files.
"""

from __future__ import annotations

import logging
import math
import subprocess
import threading
import time

import pystray

from . import config
from .audio import AudioRecorder
from .automation import copy_and_paste, open_ai_service
from .hotkey import HotkeyManager
from .transcription import WhisperEngine
from .transcription import process_transcription
from .meeting import MeetingRecorder
from .visuals_linux import StatusIconRenderer

logger = logging.getLogger(__name__)


class AIMFlowLinuxApp:
    """Linux system-tray application."""

    def __init__(self) -> None:
        logger.debug("Initializing AIMFlowLinuxApp")

        # Core components (identical roles to the macOS version).
        self.recorder = AudioRecorder()
        self.whisper = WhisperEngine()
        self.hotkey = HotkeyManager(self.toggle_recording)
        self.renderer = StatusIconRenderer()
        self.meeting_recorder = MeetingRecorder()

        # Application state.
        self.state = "idle"
        self.last_transcript = "No transcript yet."
        self.status_text = "Ready"
        self.processing_counter = 0
        self.wave_levels = [0.15] * config.WAVE_BAR_COUNT
        self._state_lock = threading.Lock()

        # Background UI update thread control.
        self._stop_update = threading.Event()
        self._update_thread: threading.Thread | None = None

        # pystray Icon — menu items use callables so labels stay dynamic.
        self._icon = pystray.Icon(
            config.APP_NAME,
            icon=self.renderer.idle_image(),
            title=config.APP_NAME,
            menu=self._build_menu(),
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the hotkey listener, UI update thread, then the tray loop."""
        self.hotkey.start()

        self._update_thread = threading.Thread(
            target=self._update_loop, name="aim-flow-ui-update", daemon=True
        )
        self._update_thread.start()

        # icon.run() blocks the main thread (required by GTK / AppIndicator).
        logger.info("Starting pystray tray icon")
        self._icon.run()

    # ------------------------------------------------------------------
    # Menu construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> pystray.Menu:
        """Return a pystray.Menu whose text labels are evaluated lazily."""
        return pystray.Menu(
            pystray.MenuItem(self._toggle_label, self._menu_toggle),
            pystray.MenuItem(self._transcript_label, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self._meeting_label, self._menu_meeting_toggle),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit_app),
        )

    def _toggle_label(self, _item=None) -> str:
        with self._state_lock:
            state = self.state
        if state == "recording":
            return f"Stop Recording  ({config.DEFAULT_HOTKEY})"
        return f"Toggle Recording  ({config.DEFAULT_HOTKEY})"

    def _transcript_label(self, _item=None) -> str:
        return f"Last Transcript: {self._truncate(self.last_transcript)}"

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def _menu_toggle(self, _icon=None, _item=None) -> None:
        self.toggle_recording()

    def _meeting_label(self, _item=None) -> str:
        if self.meeting_recorder.is_recording:
            return "Stop Meeting Recording"
        return "Start Meeting Recording"

    def _menu_meeting_toggle(self, _icon=None, _item=None) -> None:
        if self.meeting_recorder.is_recording:
            threading.Thread(
                target=self._finish_meeting, name="aim-flow-meeting-finish", daemon=True
            ).start()
        else:
            self._notify("Meeting recording started")
            self.meeting_recorder.start_recording()

    def _finish_meeting(self) -> None:
        self._notify("Meeting stopped. Transcribing and summarizing...")
        recording = self.meeting_recorder.stop_recording()
        if recording is None:
            self._notify("Meeting recording failed.")
            return
        output_path = self.meeting_recorder.process_meeting(recording)
        warning = self.meeting_recorder.last_warning
        if output_path:
            msg = f"Meeting saved: {output_path}"
            if warning:
                msg = f"{warning} Saved to {output_path}"
            self._notify(msg)
            try:
                subprocess.Popen(["xdg-open", output_path])
            except Exception as exc:
                logger.warning("Could not open meeting output: %s", exc)
        else:
            self._notify("Meeting processing failed; see logs.")

    def _notify(self, message: str) -> None:
        logger.info(message)
        try:
            subprocess.Popen(["notify-send", "AIM Flow", message])
        except Exception:
            pass

    def _quit_app(self, _icon=None, _item=None) -> None:
        logger.info("Quitting AIM Flow")
        self._stop_update.set()
        try:
            if self.recorder.is_recording:
                self.recorder.stop()
        finally:
            self.hotkey.stop()
            self._icon.stop()

    # ------------------------------------------------------------------
    # Recording control  (identical state machine as macOS version)
    # ------------------------------------------------------------------

    def toggle_recording(self) -> None:
        with self._state_lock:
            if self.state == "processing":
                return
            is_starting = self.state == "idle"

        if is_starting:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self) -> None:
        logger.info("Starting recording")
        try:
            self.recorder.start()
        except Exception as exc:
            logger.error("Audio error: %s", exc)
            self._set_state("idle")
            self.status_text = f"Audio error ({exc})"
            self._notify(config.APP_NAME, "Audio error", str(exc))
            return

        self.status_text = "Recording"
        self._set_state("recording")

    def _stop_recording(self) -> None:
        logger.info("Stopping recording, starting transcription")
        self.status_text = "Transcribing locally"
        self._set_state("processing")
        recording = self.recorder.stop()
        worker = threading.Thread(
            target=self._transcribe_and_paste,
            args=(recording.frames, recording.sample_width),
            daemon=True,
        )
        worker.start()

    def _transcribe_and_paste(self, frames: list[bytes], sample_width: int) -> None:
        if not frames:
            logger.warning("No audio frames captured")
            self.last_transcript = "No audio captured."
            self.status_text = "Ready"
            self._set_state("idle")
            return

        try:
            if not self.whisper.ffmpeg_available():
                raise FileNotFoundError(
                    "ffmpeg not found. Install it with: sudo apt-get install ffmpeg"
                )
            logger.debug("Transcribing %d frames", len(frames))
            text = self.whisper.transcribe_frames(frames, sample_width)
            if text:
                logger.info("Transcription: %s", text[:80])
                processed_text, service = process_transcription(text)
                if service:
                    logger.info("Wake word detected, opening %s", service)
                    open_ai_service(service, processed_text)
                else:
                    copy_and_paste(processed_text)
                self.last_transcript = text
                self.status_text = "Ready"
            else:
                logger.info("No speech detected in audio")
                self.last_transcript = "No speech detected."
                self.status_text = "Ready"
                self._notify(
                    config.APP_NAME,
                    "No speech detected",
                    "Try speaking a bit closer to the mic.",
                )
        except Exception as exc:
            logger.error("Transcription/paste error: %s", exc, exc_info=True)
            self.last_transcript = f"Error: {exc}"
            self.status_text = "Error"
            self._notify(config.APP_NAME, "Transcription error", str(exc))
        finally:
            self._set_state("idle")

    # ------------------------------------------------------------------
    # UI update loop (runs in a daemon thread at ~8 fps)
    # ------------------------------------------------------------------

    def _update_loop(self) -> None:
        while not self._stop_update.is_set():
            try:
                self._update_ui()
            except Exception as exc:
                logger.debug("UI update error: %s", exc)
            self._stop_update.wait(0.12)

    def _update_ui(self) -> None:
        with self._state_lock:
            state = self.state

        if state == "recording":
            # Static icon on Linux — AppIndicator can't repaint smoothly
            # enough for the macOS-style live waveform.
            if getattr(self, "_last_drawn_state", None) != "recording":
                levels = [0.6] * config.WAVE_BAR_COUNT
                self._icon.icon = self.renderer.recording_image(levels)
                self._last_drawn_state = "recording"
            return
        elif state == "processing":
            # Same reasoning — show a single processing frame, no spinner.
            if getattr(self, "_last_drawn_state", None) != "processing":
                self._icon.icon = self.renderer.processing_image(0.0)
                self._last_drawn_state = "processing"
            return
        else:
            # Idle: only redraw on state transition to avoid AppIndicator flicker.
            if getattr(self, "_last_drawn_state", None) != "idle":
                self.wave_levels = [0.15] * config.WAVE_BAR_COUNT
                self._icon.icon = self.renderer.idle_image()
                self._last_drawn_state = "idle"
            return  # nothing to refresh while idle

        # Refresh menu text (pystray re-evaluates callables on open,
        # but calling update_menu() keeps the tooltip/title current).
        try:
            self._icon.update_menu()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers  (identical to macOS version)
    # ------------------------------------------------------------------

    def _set_state(self, state: str) -> None:
        with self._state_lock:
            self.state = state
            if state != "processing":
                self.processing_counter = 0

    def _truncate(self, text: str, limit: int = 60) -> str:
        return text if len(text) <= limit else text[: limit - 3] + "..."

    def _animated_wave_levels(self, level: float) -> list[float]:
        now = time.monotonic()
        weights = (0.72, 1.0, 0.86, 0.64)
        phases = (0.0, 0.9, 1.8, 2.7)
        speeds = (3.6, 4.8, 4.2, 5.3)
        smoothed: list[float] = []

        for index in range(config.WAVE_BAR_COUNT):
            wobble = 0.08 * math.sin(now * speeds[index] + phases[index])
            target = 0.12 + level * weights[index] + wobble * (0.35 + level)
            target = max(0.08, min(1.0, target))
            current = self.wave_levels[index]
            updated = current + (target - current) * 0.35
            smoothed.append(updated)

        self.wave_levels = smoothed
        return smoothed

    # ------------------------------------------------------------------
    # Desktop notifications
    # ------------------------------------------------------------------

    @staticmethod
    def _notify(app: str, title: str, body: str = "") -> None:
        """Send a desktop notification via notify-send (best-effort)."""
        try:
            args = ["notify-send", f"{app}: {title}"]
            if body:
                args.append(body)
            subprocess.run(args, check=False, timeout=3)
        except FileNotFoundError:
            logger.debug("notify-send not available; skipping notification")
        except Exception as exc:
            logger.debug("Notification failed: %s", exc)
