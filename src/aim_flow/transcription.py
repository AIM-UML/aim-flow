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

import numpy as np
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

    def transcribe_file(self, audio_path: str) -> str:
        """Transcribe an existing audio file path."""
        model = self._load_model()
        result = model.transcribe(
            audio_path,
            fp16=False,
            language=config.TRANSCRIPTION_LANGUAGE,
        )
        return result.get("text", "").strip()

    def _load_model(self):
        with self._lock:
            if self._model is None:
                # "base" keeps first-run latency and download size lower, which
                # makes dictation feel more reliable out of the box on macOS.
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
        audio_bytes = b"".join(frames)
        if config.VOICE_ISOLATION_ENABLED:
            audio_bytes = self._preprocess_audio(audio_bytes, sample_width)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            path = Path(handle.name)

        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(config.CHANNELS)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(config.SAMPLE_RATE)
            wav_file.writeframes(audio_bytes)

        return path

    def _preprocess_audio(self, audio_bytes: bytes, sample_width: int) -> bytes:
        if sample_width != 2 or not audio_bytes:
            return audio_bytes

        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.size == 0:
            return audio_bytes

        # Remove low-frequency rumble and steady-state background with a simple
        # pre-emphasis stage that favors the vocal range for Whisper.
        emphasized = np.empty_like(samples)
        emphasized[0] = samples[0]
        emphasized[1:] = samples[1:] - 0.97 * samples[:-1]

        window = max(1, int(config.SAMPLE_RATE * 0.03))
        envelope = self._window_rms(emphasized, window)
        noise_floor = max(
            config.VOICE_GATE_FLOOR,
            float(np.percentile(envelope, 20)) if envelope.size else config.VOICE_GATE_FLOOR,
        )
        gate_threshold = noise_floor * config.VOICE_GATE_RATIO

        cleaned = emphasized.copy()
        attenuated = envelope < gate_threshold
        cleaned[attenuated] *= 0.18

        trimmed = self._trim_to_voice_region(cleaned, envelope, gate_threshold)
        peak = float(np.max(np.abs(trimmed))) if trimmed.size else 0.0
        if peak > 1e-4:
            trimmed *= min(config.VOICE_TARGET_PEAK / peak, 6.0)

        trimmed = np.clip(trimmed, -1.0, 1.0)
        return (trimmed * 32767.0).astype(np.int16).tobytes()

    def _window_rms(self, samples: np.ndarray, window: int) -> np.ndarray:
        squared = np.square(samples, dtype=np.float32)
        kernel = np.ones(window, dtype=np.float32) / float(window)
        return np.sqrt(np.convolve(squared, kernel, mode="same"))

    def _trim_to_voice_region(
        self,
        samples: np.ndarray,
        envelope: np.ndarray,
        gate_threshold: float,
    ) -> np.ndarray:
        active = np.flatnonzero(envelope >= max(gate_threshold, config.SILENCE_TRIM_THRESHOLD))
        if active.size == 0:
            return samples

        margin = int(config.SAMPLE_RATE * (config.SILENCE_TRIM_MARGIN_MS / 1000.0))
        start = max(0, int(active[0]) - margin)
        end = min(samples.size, int(active[-1]) + margin)
        return samples[start:end]
