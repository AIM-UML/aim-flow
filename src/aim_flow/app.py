"""Menu bar application."""

from __future__ import annotations

import logging
import math
import os
import subprocess
import threading
import time

import rumps

from . import config
from .audio import AudioRecorder, get_device_name, list_input_devices
from .automation import copy_and_paste, open_ai_service
from .hotkey import HotkeyManager
from .meeting import MeetingRecorder
from .meeting_history import open_history_viewer
from .zoom_import import parse_srt_transcript, parse_vtt_transcript
from .transcription import process_transcription
from .transcription import WhisperEngine
from .visuals import StatusIconRenderer

logger = logging.getLogger(__name__)


class AIMFlowApp(rumps.App):
    def __init__(self) -> None:
        # Pass the logo as the initial icon so rumps' initializeStatusBar()
        # uses it, preventing the fallback "AIM Flow" text from appearing.
        logo_path = str(config.resource_path(config.STATUS_LOGO_NAME))
        super().__init__(config.APP_NAME, icon=logo_path, title="", quit_button=None)
        logger.debug("Initializing AIMFlowApp, logo=%s", logo_path)

        self.recorder = AudioRecorder()
        self.whisper = WhisperEngine()
        self.hotkey = HotkeyManager(self.request_toggle)
        self.renderer = StatusIconRenderer()
        self.meeting_recorder = MeetingRecorder()
        self.selected_mic_index = config.load_mic_preference()

        self.state = "idle"
        self.last_transcript = "No transcript yet."
        self.status_text = "Ready"
        self.meeting_in_progress = False
        self.meeting_processing = False
        self.processing_counter = 0
        self.wave_levels = [0.15] * config.WAVE_BAR_COUNT
        self._state_lock = threading.Lock()
        self._toggle_requested = threading.Event()

        self.toggle_item = rumps.MenuItem(
            f"Toggle Recording ({config.DEFAULT_HOTKEY})", self._menu_toggle
        )
        self.meeting_item = rumps.MenuItem("Start Meeting Recording", self._toggle_meeting)
        self.mic_item = rumps.MenuItem("Select Microphone...", self._select_microphone)
        self.import_audio_item = rumps.MenuItem("Import Audio File...", self._import_audio)
        self.import_transcript_item = rumps.MenuItem("Import Transcript...", self._import_transcript)
        self.history_item = rumps.MenuItem("Meeting History", self._show_history)
        self.last_text_item = rumps.MenuItem("Last Transcript: No transcript yet.")
        self.permissions_item = rumps.MenuItem(
            "Check Permissions", self._open_accessibility_settings
        )
        self.quit_item = rumps.MenuItem("Quit", self.quit_app)
        self.menu = [
            self.toggle_item,
            self.last_text_item,
            None,  # separator
            self.meeting_item,
            self.mic_item,
            self.import_audio_item,
            self.import_transcript_item,
            self.history_item,
            None,  # separator
            self.permissions_item,
            self.quit_item,
        ]

        self.timer = rumps.Timer(self._update_ui, 0.12)
        self.timer.start()
        self.hotkey.start()

        # Check permissions once, shortly after the run loop starts.
        self._perm_timer = rumps.Timer(self._check_permissions_once, 1.5)
        self._perm_timer.start()

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def _menu_toggle(self, _sender) -> None:
        self.toggle_recording()

    def request_toggle(self) -> None:
        self._toggle_requested.set()

    def _open_accessibility_settings(self, _sender) -> None:
        from .permissions import open_accessibility_settings
        open_accessibility_settings()

    def _select_microphone(self, _sender) -> None:
        devices = list_input_devices()
        choices = ["Use System Default"] + [device["name"] for device in devices]
        choice_list = "\", \"".join(choices)
        script = f'''
        set choiceItems to {{"{choice_list}"}}
        set selectedItem to choose from list choiceItems with prompt "Select a recording microphone:" with title "AIM Flow"
        if selectedItem is false then
            return "CANCELLED"
        else
            return item 1 of selectedItem
        end if
        '''
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            return

        selected = result.stdout.strip()
        if not selected or selected == "CANCELLED":
            return

        if selected == "Use System Default":
            self.selected_mic_index = None
            config.save_mic_preference(None)
            rumps.notification(config.APP_NAME, "Microphone changed", "Using system default microphone")
            return

        for device in devices:
            if device["name"] == selected:
                self.selected_mic_index = device["index"]
                config.save_mic_preference(device["index"])
                rumps.notification(
                    config.APP_NAME,
                    "Microphone changed",
                    f"Now using: {get_device_name(device['index'])}",
                )
                return

    def _show_history(self, _sender) -> None:
        open_history_viewer()

    def _import_audio(self, _sender) -> None:
        script = 'POSIX path of (choose file of type {"public.audio"} with prompt "Select audio file")'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            return

        audio_path = result.stdout.strip()
        if not audio_path:
            return

        self.title = "⏳ Processing Import..."

        def process() -> None:
            summary_path = self.meeting_recorder.process_audio_file(audio_path)
            if summary_path:
                rumps.notification(config.APP_NAME, "Import complete", f"Saved {os.path.basename(summary_path)}")
                subprocess.run(["open", summary_path], check=False)
            else:
                rumps.notification(config.APP_NAME, "Import failed", "Could not process audio file")
            self.title = "AIM Flow"

        threading.Thread(target=process, daemon=True).start()

    def _import_transcript(self, _sender) -> None:
        script = 'POSIX path of (choose file of type {"public.text", "vtt", "srt"} with prompt "Select transcript file")'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            return

        transcript_path = result.stdout.strip()
        if not transcript_path:
            return

        if transcript_path.lower().endswith(".vtt"):
            transcript = parse_vtt_transcript(transcript_path)
        elif transcript_path.lower().endswith(".srt"):
            transcript = parse_srt_transcript(transcript_path)
        else:
            with open(transcript_path, "r", encoding="utf-8") as handle:
                transcript = handle.read().strip()

        if not transcript:
            rumps.alert("Import Failed", "Could not parse transcript file")
            return

        self.title = "⏳ Generating Summary..."

        def process() -> None:
            summary_path = self.meeting_recorder.process_transcript_text(transcript)
            if summary_path:
                rumps.notification(config.APP_NAME, "Summary ready", f"Saved {os.path.basename(summary_path)}")
                subprocess.run(["open", summary_path], check=False)
            else:
                rumps.notification(config.APP_NAME, "Summary failed", "Could not generate summary")
            self.title = "AIM Flow"

        threading.Thread(target=process, daemon=True).start()

    # ------------------------------------------------------------------
    # Recording control
    # ------------------------------------------------------------------

    def toggle_recording(self) -> None:
        if self.meeting_in_progress or self.meeting_processing:
            rumps.notification(
                config.APP_NAME,
                "Meeting recording in progress",
                "Stop meeting recording before using dictation.",
            )
            return

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
            rumps.notification(config.APP_NAME, "Audio error", str(exc))
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
                    "ffmpeg not found. Install it with: brew install ffmpeg"
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
                rumps.notification(
                    config.APP_NAME,
                    "No speech detected",
                    "Try speaking a bit closer to the mic.",
                )
        except Exception as exc:
            logger.error("Transcription/paste error: %s", exc, exc_info=True)
            self.last_transcript = f"Error: {exc}"
            self.status_text = "Error"
            rumps.notification(config.APP_NAME, "Transcription error", str(exc))
        finally:
            self._set_state("idle")

    # ------------------------------------------------------------------
    # Meeting recorder control
    # ------------------------------------------------------------------

    def _toggle_meeting(self, _sender) -> None:
        with self._state_lock:
            dictation_busy = self.state in {"recording", "processing"}

        if dictation_busy:
            rumps.notification(
                config.APP_NAME,
                "Dictation active",
                "Stop dictation before starting meeting recording.",
            )
            return

        if self.meeting_processing:
            return

        if not self.meeting_in_progress:
            self._start_meeting_recording()
        else:
            self._stop_meeting_recording()

    def _start_meeting_recording(self) -> None:
        response = rumps.alert(
            title="Recording Meeting",
            message=(
                "For best transcription quality:\n\n"
                "• Place Mac within 6 feet of speaker\n"
                "• Or use an external microphone\n"
                "• Avoid noisy environments\n\n"
                "Continue recording?"
            ),
            ok="Start Recording",
            cancel="Cancel",
        )
        if response != 1:
            return

        if not self.meeting_recorder.start_recording(
            device_index=self.selected_mic_index,
            capture_note="Recorded from distance - accuracy may be lower.",
        ):
            rumps.alert("Recording failed", "Could not start meeting recording.")
            return

        self.meeting_in_progress = True
        self.meeting_item.title = "Stop Meeting Recording"
        rumps.notification(
            config.APP_NAME,
            "Meeting recording started",
            "Use Stop Meeting Recording when done.",
        )

    def _stop_meeting_recording(self) -> None:
        self.meeting_processing = True
        self.meeting_item.title = "Processing meeting..."
        recording = self.meeting_recorder.stop_recording()

        if recording is None:
            self.meeting_in_progress = False
            self.meeting_processing = False
            self.meeting_item.title = "Start Meeting Recording"
            rumps.alert("Recording failed", "Could not capture meeting audio.")
            return

        worker = threading.Thread(
            target=self._process_meeting_background,
            args=(recording,),
            daemon=True,
        )
        worker.start()

    def _process_meeting_background(self, recording) -> None:
        summary_path = self.meeting_recorder.process_meeting(recording)
        warning = self.meeting_recorder.last_warning
        if summary_path:
            subtitle = "Meeting output ready"
            message = f"Saved {os.path.basename(summary_path)}"
            if warning:
                subtitle = "Meeting output saved with warning"
                message = warning
            rumps.notification(config.APP_NAME, subtitle, message)
            subprocess.run(["open", summary_path], check=False)
        else:
            rumps.notification(
                config.APP_NAME,
                "Meeting processing failed",
                "No summary file was generated.",
            )

        self.meeting_in_progress = False
        self.meeting_processing = False
        self.meeting_item.title = "Start Meeting Recording"

    # ------------------------------------------------------------------
    # UI update timer
    # ------------------------------------------------------------------

    def _update_ui(self, _sender) -> None:
        if self._toggle_requested.is_set():
            self._toggle_requested.clear()
            self.toggle_recording()

        with self._state_lock:
            state = self.state

        self.last_text_item.title = f"Last Transcript: {self._truncate(self.last_transcript)}"
        self.toggle_item.title = (
            f"Stop Recording ({config.DEFAULT_HOTKEY})"
            if state == "recording"
            else f"Toggle Recording ({config.DEFAULT_HOTKEY})"
        )

        if state == "recording":
            levels = self._animated_wave_levels(self.recorder.level)
            self._apply_status_image(self.renderer.recording_image(levels))
        elif state == "processing":
            phase = self.processing_counter * 0.7
            self.processing_counter += 1
            self._apply_status_image(self.renderer.processing_image(phase))
        else:
            self.wave_levels = [0.15] * config.WAVE_BAR_COUNT
            self._apply_status_image(self.renderer.idle_image())

    # ------------------------------------------------------------------
    # Permission check (fires once, 1.5 s after startup)
    # ------------------------------------------------------------------

    def _check_permissions_once(self, _sender) -> None:
        self._perm_timer.stop()
        self._perm_timer = None
        try:
            from .permissions import check_and_prompt
            check_and_prompt()
        except Exception as exc:
            logger.warning("Permission check failed: %s", exc)

    # ------------------------------------------------------------------
    # Helpers
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
        speeds = (6.0, 8.5, 7.2, 9.8)
        smoothed: list[float] = []

        for index in range(config.WAVE_BAR_COUNT):
            wobble = 0.22 * math.sin(now * speeds[index] + phases[index])
            target = 0.12 + level * weights[index] + wobble * (0.7 + level)
            target = max(0.05, min(1.0, target))
            current = self.wave_levels[index]
            updated = current + (target - current) * 0.55
            smoothed.append(updated)

        self.wave_levels = smoothed
        return smoothed

    def _apply_status_image(self, image) -> None:
        """Push a rendered NSImage onto the live NSStatusItem.

        rumps stores the NSStatusItem on self._nsapp.nsstatusitem (set during
        initializeStatusBar() inside run()).  We bypass rumps' icon property
        here so we can supply dynamically-rendered NSImages without round-
        tripping through a file on disk.
        """
        nsapp = getattr(self, "_nsapp", None)
        if nsapp is None:
            return
        status_item = getattr(nsapp, "nsstatusitem", None)
        if status_item is None:
            return
        self.renderer.apply_to_status_item(status_item, image)

    def quit_app(self, _sender) -> None:
        logger.info("Quitting AIM Flow")
        try:
            if self.recorder.is_recording:
                self.recorder.stop()
        finally:
            self.hotkey.stop()
            rumps.quit_application()
