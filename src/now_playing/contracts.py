"""Only the replaceable boundaries used by live orchestration."""

from __future__ import annotations

from typing import Any, Protocol

from .models import Track


class Classifier(Protocol):
    async def classify(self, window: Any) -> bool: ...


class SongRecognizer(Protocol):
    async def recognize(self, samples: Any, sample_rate: int) -> Track | None: ...


class AlbumSink(Protocol):
    def submit(self, track: Track) -> None: ...
