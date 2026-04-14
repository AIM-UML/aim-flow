"""Whisper transcription helpers."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
import threading
import wave

import whisper
import noisereduce as nr
import numpy as py

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

        import numpy as np
        import noisereduce as nr

        model = self._load_model()

        # Noise reduction
        raw = b"".join(frames)
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        cleaned = nr.reduce_noise(y=samples, sr=config.SAMPLE_RATE, stationary=True, prop_decrease=0.75)
        cleaned_int16 = (cleaned * 32768.0).clip(-32768, 32767).astype(np.int16)
        cleaned_frames = [cleaned_int16.tobytes()]

        temp_path = self._write_temp_wav(cleaned_frames, sample_width)
        try:
            result = model.transcribe(
                str(temp_path),
                fp16=False,
                language=config.TRANSCRIPTION_LANGUAGE,
                initial_prompt="Hey Claude, Hey Google, Hey Open, Hey X",
            )
            return result.get("text", "").strip()
        finally:
            temp_path.unlink(missing_ok=True)

    def _load_model(self):
        with self._lock:
            if self._model is None:
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


_WAKE_WORDS: dict[str, str] = {
    "hey claude": "claude",
    "hey open": "chatgpt",
    "hey x": "grok",
    "hey google": "gemini",
}


def process_transcription(text: str) -> tuple[str, str | None]:
    text = text.strip()
    text_lower = text.lower()
    for wake_word, service in _WAKE_WORDS.items():
        if text_lower.startswith(wake_word):
            remaining = text[len(wake_word):].lstrip(" ,")
            return (remaining, service)
    return (text, None)
