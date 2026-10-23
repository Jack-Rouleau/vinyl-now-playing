"""Compose the display, persistence, and live pipeline; own their lifetimes."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .demo import Demo
from .engine import Engine
from .platforms import shutdown_signals
from .server import Server

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunOptions:
    demo: bool = False
    demo_state: str | None = None
    open_browser: bool = False


def demo_albums() -> dict:
    return {
        "revision": 1,
        "albums": [
            {
                "id": "demo-cover",
                "album": "Demo album",
                "artist": "Demo artist",
                "artwork_url": "/demo-artwork.svg",
            }
        ],
    }


async def run_application(
    config: Config, options: RunOptions, *, stop: asyncio.Event | None = None
) -> None:
    source = Demo(fixed=options.demo_state) if options.demo else Engine(config, time.monotonic)
    stop = stop if stop is not None else asyncio.Event()
    archive = store = None
    if not options.demo:
        source.capture_failed()
        from .album_cache import AlbumArchive
        from .albums import AlbumStore

        try:
            store = AlbumStore(Path(config.state_dir))
            archive = AlbumArchive(store)
            archive.start()
        except (OSError, sqlite3.Error):
            log.exception("Album persistence unavailable; live recognition will continue")
    albums = demo_albums if options.demo else store.snapshot if store else None
    artwork = store.artwork if store else None
    try:
        with shutdown_signals(asyncio.get_running_loop(), stop):
            with Server(source.snapshot, config.host, config.port, albums=albums, artwork=artwork):
                browser_host = "127.0.0.1" if config.host == "0.0.0.0" else config.host
                url = f"http://{browser_host}:{config.port}"
                log.info(
                    "Now Playing at %s (%s)", url, "demo: no microphone" if options.demo else "live"
                )
                if options.open_browser:
                    await asyncio.to_thread(webbrowser.open, url)
                if options.demo:
                    await stop.wait()
                else:
                    await _run_until_stopped(config, source, archive, stop)
    finally:
        if archive:
            await archive.close()


async def _run_until_stopped(config: Config, engine: Engine, archive, stop: asyncio.Event) -> None:
    from .runtime import run_live

    worker = asyncio.create_task(run_live(config, engine, archive=archive))
    stopped = asyncio.create_task(stop.wait())
    try:
        done, _ = await asyncio.wait((worker, stopped), return_when=asyncio.FIRST_COMPLETED)
        if worker in done:
            await worker
    finally:
        worker.cancel()
        stopped.cancel()
        await asyncio.gather(worker, stopped, return_exceptions=True)
