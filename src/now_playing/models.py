"""Immutable snapshots shared by live mode, demo, and HTTP."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Track:
    id: str
    title: str
    artist: str
    album: str | None = None
    artwork_url: str | None = None


@dataclass(frozen=True)
class DisplayState:
    status: str = "idle"
    track: Track | None = None
    revision: int = 0
    activity: str = "listening"

    def to_dict(self) -> dict:
        return asdict(self)
