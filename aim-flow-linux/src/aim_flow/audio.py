"""Audio capture utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import List

import numpy as np
import pyaudio

from . import config


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

    def start(self) -> None:
        with self._lock:
            if self._recording:
                return

            self._audio = pyaudio.PyAudio()
            self._sample_width = self._audio.get_sample_size(pyaudio.paInt16)
            self._stream = self._audio.open(
                format=pyaudio.paInt16,
                channels=config.CHANNELS,
                rate=config.SAMPLE_RATE,
                input=True,
                frames_per_buffer=config.CHUNK_SIZE,
            )
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
