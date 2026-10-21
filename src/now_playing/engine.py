"""Deterministic state machine. The runtime owns I/O and asynchronous work."""

from collections.abc import Callable
from dataclasses import replace

from .config import Config
from .models import DisplayState, Track


class Engine:
    def __init__(self, config: Config, clock: Callable[[], float]):
        self.config, self.clock = config, clock
        self._state = DisplayState()
        self._positive = 0
        self._last_music = None
        self._last_match = None
        self._pending = None
        self._started = 0.0
        self._serial = 0
        self._next_attempt = float("-inf")
        self._failures = 0
        self._capture_error = False
        self._network_error = False

    def _publish(self, status: str, track: Track | None = None):
        if (status, track) != (self._state.status, self._state.track):
            self._state = DisplayState(status, track, self._state.revision + 1)

    def observe(self, music: bool) -> None:
        self._capture_error = False
        if music:
            self._last_music = self.clock()
            self._positive += 1
        else:
            self._positive = 0
        self.tick()

    def tick(self) -> None:
        now = self.clock()
        if self._capture_error:
            return
        if self._pending is not None and now - self._started >= self.config.request_timeout:
            self.complete(self._pending, None, failed=True)
        if self._last_music is None or now - self._last_music >= self.config.silence_seconds:
            self._pending = None
            self._positive = 0
            self._last_match = None
            self._network_error = False
            self._publish("idle")
            return
        track = self._state.track
        if self._last_match is not None and now - self._last_match >= self.config.track_expiry:
            track = None
        if track is not None:
            self._publish("matched", track)
        elif self._network_error:
            self._publish("unavailable")
        elif self._positive >= self.config.positive_windows or self._state.status != "idle":
            self._publish("identifying")

    def begin_recognition(self) -> int | None:
        self.tick()
        if (
            self._capture_error
            or self._pending is not None
            or self._positive < self.config.positive_windows
            or self.clock() < self._next_attempt
        ):
            return None
        self._serial += 1
        self._pending = self._serial
        self._started = self.clock()
        self._next_attempt = self._started + self.config.attempt_interval
        return self._pending

    def complete(self, token: int, track: Track | None, failed: bool = False) -> bool:
        if token is None or token != self._pending:
            return False
        if (
            self._last_music is None
            or self.clock() - self._last_music >= self.config.silence_seconds
        ):
            self._pending = None
            self._positive = 0
            self._last_match = None
            self._publish("idle")
            return False
        if self.clock() - self._started >= self.config.request_timeout:
            track, failed = None, True
        self._pending = None
        if failed:
            self._failures += 1
            delay = min(
                self.config.max_backoff,
                self.config.attempt_interval * 2 ** min(self._failures - 1, 16),
            )
            self._next_attempt = self._started + delay
            self._network_error = True
        else:
            self._failures = 0
            self._network_error = False
            if track is not None:
                self._last_match = self.clock()
                self._publish("matched", track)
        self.tick()
        return not failed and track is not None

    def capture_failed(self) -> None:
        self._capture_error = True
        self._pending = None
        self._positive = 0
        self._last_music = self._last_match = None
        self._publish("unavailable")

    def snapshot(self) -> DisplayState:
        if self._capture_error or self._network_error:
            activity = "paused"
        elif self._pending is not None:
            activity = "identifying"
        elif self._positive:
            activity = "music_detected"
        else:
            activity = "listening"
        return replace(self._state, activity=activity)
