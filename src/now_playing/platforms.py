"""Small operating-system boundaries; no audio/ML imports."""

from __future__ import annotations

import os
import signal
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path


def user_data_directory(
    platform: str | None = None,
    environment: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    platform = platform or sys.platform
    environment = os.environ if environment is None else environment
    home = home or Path.home()
    if platform == "win32":
        return (
            Path(
                environment.get("LOCALAPPDATA")
                or environment.get("APPDATA")
                or home / "AppData/Local"
            )
            / "NowPlaying"
        )
    if platform == "darwin":
        return home / "Library/Application Support/NowPlaying"
    return Path(environment.get("XDG_DATA_HOME") or home / ".local/share") / "now-playing"


@contextmanager
def shutdown_signals(loop, stop) -> Iterator[None]:
    """Use asyncio signals on Unix, normal console signals on Windows."""
    asynchronous, synchronous = [], []
    try:
        for number in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(number, stop.set)
                asynchronous.append(number)
            except (NotImplementedError, RuntimeError):
                previous = signal.getsignal(number)
                signal.signal(number, lambda *_: loop.call_soon_threadsafe(stop.set))
                synchronous.append((number, previous))
        yield
    finally:
        for number in asynchronous:
            loop.remove_signal_handler(number)
        for number, previous in synchronous:
            signal.signal(number, previous)
