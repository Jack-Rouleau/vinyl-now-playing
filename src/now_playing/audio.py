"""Bounded audio capture. Raw audio exists only in memory."""

import asyncio
import threading
from collections import deque

import numpy as np

from .config import Config


class AudioBuffer:
    def __init__(self, seconds: int):
        self.limit = seconds * 16000
        self._data = np.empty(0, dtype=np.float32)

    def append(self, window):
        self._data = np.concatenate((self._data, window))[-self.limit :]

    def sample(self):
        return self._data.copy() if len(self._data) == self.limit else None

    def clear(self):
        self._data = np.empty(0, dtype=np.float32)


def normalize_audio(data, source_rate: int):
    """Downmix and resample with an anti-alias FIR before downsampling."""
    mono = np.asarray(data, dtype=np.float32)
    if mono.ndim == 2:
        mono = mono.mean(axis=1)
    if mono.ndim != 1 or not len(mono) or source_rate <= 0 or not np.isfinite(mono).all():
        raise ValueError("Audio must be finite nonempty mono/stereo samples at a positive rate")
    if source_rate == 16000:
        return mono.copy()
    if source_rate > 16000:
        # 127-tap windowed-sinc filter keeps frequencies below output Nyquist.
        cutoff = 0.47 * 16000 / source_rate
        x = np.arange(127) - 63
        kernel = 2 * cutoff * np.sinc(2 * cutoff * x) * np.hamming(127)
        kernel /= kernel.sum()
        mono = np.convolve(np.pad(mono, (63, 63), mode="reflect"), kernel, mode="valid")
    length = round(len(mono) * 16000 / source_rate)
    return np.interp(np.arange(length) * source_rate / 16000, np.arange(len(mono)), mono).astype(
        np.float32
    )


class WindowQueue:
    """Callback-safe bounded queue. A dropped block invalidates the rolling clip."""

    def __init__(self, capacity: int = 5):
        self._items = deque()
        self._capacity = capacity
        self._condition = threading.Condition()
        self._dropped = False

    def push(self, data, gap=False):
        with self._condition:
            if len(self._items) >= self._capacity:
                self._items.popleft()
                self._dropped = True
            self._items.append((data, gap))
            self._condition.notify()

    def pop(self, timeout):
        with self._condition:
            if not self._condition.wait_for(lambda: bool(self._items), timeout):
                raise TimeoutError("No microphone audio received")
            data, gap = self._items.popleft()
            gap = gap or self._dropped
            self._dropped = False
            return data, gap


def list_devices() -> list[dict]:
    import sounddevice as sd

    return [
        dict(index=i, **dict(device))
        for i, device in enumerate(sd.query_devices())
        if device["max_input_channels"] > 0
    ]


class AudioCapture:
    def __init__(self, config: Config, backend=None):
        self.config = config
        self.backend = backend
        self.stream = None
        self.queue = WindowQueue()
        self.discontinuity = False

    async def __aenter__(self):
        if self.backend is None:
            import sounddevice

            self.backend = sounddevice
        try:
            self.capture_rate = self.config.capture_rate or int(
                self.backend.query_devices(self.config.device, "input")["default_samplerate"]
            )
            self.backend.check_input_settings(
                device=self.config.device,
                samplerate=self.capture_rate,
                channels=self.config.channels,
                dtype="float32",
            )
            self.stream = self.backend.InputStream(
                device=self.config.device,
                samplerate=self.capture_rate,
                channels=self.config.channels,
                dtype="float32",
                blocksize=self.capture_rate,
                callback=self._callback,
            )
            self.stream.start()
        except Exception as error:
            if self.stream is not None:
                self.stream.close()
            raise RuntimeError(
                "Cannot open input device; check --list-devices, capture_rate and channels"
            ) from error
        return self

    def _callback(self, data, frames, timing, status):
        self.queue.push(data.copy(), gap=bool(status) or frames != self.capture_rate)

    async def windows(self):
        missed = 0
        while True:
            if not self.stream.active:
                raise RuntimeError("Microphone stream stopped; check device connection")
            try:
                data, self.discontinuity = await asyncio.to_thread(self.queue.pop, 0.5)
                missed = 0
            except TimeoutError:
                missed += 1
                if missed >= 10:
                    raise RuntimeError("No microphone audio for five seconds")
                continue
            yield await asyncio.to_thread(normalize_audio, data, self.capture_rate)

    async def __aexit__(self, *args):
        if self.stream is not None:
            try:
                self.stream.stop()
            finally:
                self.stream.close()
