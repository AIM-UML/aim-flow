"""Whisper transcription helpers."""

from __future__ import annotations

# Maps wake word (lowercase) → service key
_WAKE_WORDS: dict[str, str] = {
    "hey claude": "claude",
    "hey open": "chatgpt",
    "hey x": "grok",
    "hey google": "gemini",
}


def process_transcription(text: str) -> tuple[str, str | None]:
    """Check if transcription starts with a known wake word.

    Returns:
        tuple: (processed_text, service_key)
            - processed_text: text with wake word stripped (if present)
            - service_key: one of 'claude', 'chatgpt', 'grok', 'gemini', or None
    """
    text = text.strip()
    text_lower = text.lower()
    for wake_word, service in _WAKE_WORDS.items():
        if text_lower.startswith(wake_word):
            remaining = text[len(wake_word):].lstrip(" ,")
            return (remaining, service)
    return (text, None)

import os
from pathlib import Path
import shutil
import tempfile
import threading
import wave

import whisper

from . import config


class WhisperEngine:
    """Lazily loads the Whisper model on first use."""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()
        self._configure_ffmpeg_path()

    def transcribe_frames(self, frames: list[bytes], sample_width: int) -> str:
        if not frames:
            return ""

        model = self._load_model()
        temp_path = self._write_temp_wav(frames, sample_width)
        try:
            result = model.transcribe(
                str(temp_path),
                fp16=False,
                language=config.TRANSCRIPTION_LANGUAGE,
            )
            return result.get("text", "").strip()
        finally:
            temp_path.unlink(missing_ok=True)

    def _load_model(self):
        with self._lock:
            if self._model is None:
                # "small" is a better default than "base" for dictation quality
                # while still remaining practical on modern Macs.
                self._model = whisper.load_model(config.MODEL_SIZE)
            return self._model

    def _configure_ffmpeg_path(self) -> None:
        current_path = os.environ.get("PATH", "")
        search_paths = [current_path, config.SYSTEM_PATH_FALLBACK]
        for path_value in search_paths:
            if path_value:
                os.environ["PATH"] = path_value
                if shutil.which("ffmpeg"):
                    return

        for candidate in config.FFMPEG_CANDIDATE_PATHS:
            if Path(candidate).exists():
                os.environ["PATH"] = f"{Path(candidate).parent}:{config.SYSTEM_PATH_FALLBACK}"
                return

    def ffmpeg_available(self) -> bool:
        return shutil.which("ffmpeg") is not None

    def _write_temp_wav(self, frames: list[bytes], sample_width: int) -> Path:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            path = Path(handle.name)

        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(config.CHANNELS)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(config.SAMPLE_RATE)
            wav_file.writeframes(b"".join(frames))

        return path
