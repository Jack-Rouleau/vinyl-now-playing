"""Deterministic state machine. The runtime owns I/O and asynchronous work."""

from collections.abc import Callable
from dataclasses import replace

from .config import Config
from .models import DisplayState, Track
from .tracklist import same_song, song_index


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
        self._tracks = ()
        self._album_start = None
        self._accepted_token = None
        self._recognized_track = None
        self._recognized_start = None
        self._confirmed_index = None

    def _publish(self, status: str, track: Track | None = None, next_track=None, inferred=False):
        if (status, track, next_track, inferred) != (
            self._state.status,
            self._state.track,
            self._state.next_track,
            self._state.inferred,
        ):
            self._state = DisplayState(
                status, track, self._state.revision + 1, next_track=next_track, inferred=inferred
            )

    def _clear_timeline(self):
        self._tracks = ()
        self._album_start = None
        self._accepted_token = None
        self._recognized_track = None
        self._recognized_start = None
        self._confirmed_index = None

    def set_tracklist(self, token, tracks):
        self.tick()
        if token != self._accepted_token or self._recognized_track is None or not tracks:
            return False
        index = song_index(self._recognized_track, tracks)
        if index is None or any(entry.duration <= 0 for entry in tracks):
            return False
        position = self._recognized_track.position_seconds
        if position is not None and position >= tracks[index].duration:
            return False
        self._tracks = tuple(tracks)
        self._confirmed_index = index
        self._album_start = self._recognized_start - sum(t.duration for t in tracks[:index])
        self.tick()
        return True

    def _follow_album(self, now):
        if not self._tracks or self._album_start is None:
            return False
        elapsed = now - self._album_start
        for index, entry in enumerate(self._tracks):
            if elapsed < entry.duration:
                inferred = index != self._confirmed_index
                track = entry.track if inferred else self._recognized_track
                # Carry the recognized cover through metadata cache reuse.
                track = replace(track, artwork_url=self._recognized_track.artwork_url)
                following = self._tracks[index + 1].track if index + 1 < len(self._tracks) else None
                self._publish("matched", track, following, inferred)
                return True
            elapsed -= entry.duration
        self._clear_timeline()
        self._last_match = None
        self._publish("identifying")
        return True

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
            self._clear_timeline()
            self._publish("idle")
            return
        if self._follow_album(now):
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

    def complete(
        self,
        token: int,
        track: Track | None,
        failed: bool = False,
        captured_at: float | None = None,
    ) -> bool:
        if token is None or token != self._pending:
            return False
        if (
            self._last_music is None
            or self.clock() - self._last_music >= self.config.silence_seconds
        ):
            self._pending = None
            self._positive = 0
            self._last_match = None
            self._clear_timeline()
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
                index = song_index(track, self._tracks)
                position = track.position_seconds
                if position is not None:
                    start = (captured_at if captured_at is not None else self.clock()) - position
                elif self._state.track is not None and same_song(track, self._state.track):
                    if index is not None and self._album_start is not None:
                        start = self._album_start + sum(t.duration for t in self._tracks[:index])
                    else:
                        start = self._recognized_start
                else:
                    start = self.clock()
                if start is None:
                    start = self.clock()
                if index is None or (
                    position is not None and position >= self._tracks[index].duration
                ):
                    self._clear_timeline()
                self._recognized_track = track
                self._recognized_start = start
                self._accepted_token = token
                if self._tracks:
                    self._album_start = start - sum(t.duration for t in self._tracks[:index])
                    self._confirmed_index = index
                self._last_match = self.clock()
                self._publish("matched", track)
        self.tick()
        return not failed and track is not None

    def capture_failed(self) -> None:
        self._capture_error = True
        self._pending = None
        self._positive = 0
        self._last_music = self._last_match = None
        self._clear_timeline()
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
