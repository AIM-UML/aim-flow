"""Audio capture utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import threading
from typing import List

import numpy as np
import pyaudio

from . import config

logger = logging.getLogger(__name__)


def list_input_devices() -> list[dict]:
    """Enumerate available audio input devices."""
    audio = pyaudio.PyAudio()
    devices: list[dict] = []
    default_index = None

    try:
        try:
            default_input = audio.get_default_input_device_info()
            default_index = int(default_input.get("index"))
        except Exception:
            default_index = None

        for index in range(audio.get_device_count()):
            try:
                info = audio.get_device_info_by_index(index)
                if info.get("maxInputChannels", 0) <= 0:
                    continue

                devices.append(
                    {
                        "index": index,
                        "name": info.get("name", f"Device {index}"),
                        "channels": info.get("maxInputChannels", 1),
                        "sample_rate": int(info.get("defaultSampleRate", config.SAMPLE_RATE)),
                        "is_default": index == default_index,
                    }
                )
            except Exception as exc:
                logger.warning("Could not query device %s: %s", index, exc)
    finally:
        audio.terminate()

    return devices


def get_device_name(device_index: int) -> str:
    """Return a friendly device name for the given index."""
    audio = pyaudio.PyAudio()
    try:
        info = audio.get_device_info_by_index(device_index)
        return info.get("name", f"Device {device_index}")
    except Exception:
        return f"Device {device_index}"
    finally:
        audio.terminate()


@dataclass
class RecordingResult:
    frames: List[bytes]
    sample_width: int


@dataclass
class AudioRecorder:
    """Records microphone audio and keeps track of a live audio level."""

    _audio: pyaudio.PyAudio | None = field(default=None, init=False)
    _stream: pyaudio.Stream | None = field(default=None, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _frames: list[bytes] = field(default_factory=list, init=False)
    _level: float = field(default=0.0, init=False)
    _sample_width: int = field(default=2, init=False)
    _recording: bool = field(default=False, init=False)
    device_index: int | None = field(default=None)

    def start(self) -> None:
        with self._lock:
            if self._recording:
                return

            self._audio = pyaudio.PyAudio()
            self._sample_width = self._audio.get_sample_size(pyaudio.paInt16)
            stream_kwargs = {
                "format": pyaudio.paInt16,
                "channels": config.CHANNELS,
                "rate": config.SAMPLE_RATE,
                "input": True,
                "frames_per_buffer": config.CHUNK_SIZE,
            }
            if self.device_index is not None:
                stream_kwargs["input_device_index"] = self.device_index

            self._stream = self._audio.open(**stream_kwargs)
            self._frames = []
            self._level = 0.0
            self._stop_event.clear()
            self._recording = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()

    def stop(self) -> RecordingResult:
        with self._lock:
            if not self._recording:
                return RecordingResult(frames=[], sample_width=self._sample_width)

            self._recording = False
            self._stop_event.set()
            thread = self._thread
            stream = self._stream
            audio = self._audio

        if thread is not None:
            thread.join(timeout=1.5)

        if stream is not None:
            try:
                stream.stop_stream()
            finally:
                stream.close()

        if audio is not None:
            audio.terminate()

        with self._lock:
            self._thread = None
            self._stream = None
            self._audio = None
            self._level = 0.0
            return RecordingResult(frames=list(self._frames), sample_width=self._sample_width)

    def _capture_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                assert self._stream is not None
                data = self._stream.read(config.CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                with self._lock:
                    self._recording = False
                    self._stop_event.set()
                return

            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(np.square(samples)))) if len(samples) else 0.0
            normalized = min(rms / 6000.0, 1.0)

            with self._lock:
                self._frames.append(data)
                self._level = normalized

    @property
    def level(self) -> float:
        with self._lock:
            return self._level

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording
