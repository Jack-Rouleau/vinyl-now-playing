"""Background album persistence and bounded artwork caching; never record audio."""

import asyncio
import logging
import time

from .albums import AlbumStore
from .artwork import artwork_candidates
from .image_formats import MAX_IMAGE_BYTES, image_suffix

log = logging.getLogger(__name__)


async def download_image(session, url: str) -> bytes:
    async with session.get(url) as response:
        response.raise_for_status()
        if response.content_length and response.content_length > MAX_IMAGE_BYTES:
            raise ValueError("Artwork exceeds 8 MiB")
        chunks, count = [], 0
        async for chunk in response.content.iter_chunked(65536):
            count += len(chunk)
            if count > MAX_IMAGE_BYTES:
                raise ValueError("Artwork exceeds 8 MiB")
            chunks.append(chunk)
        return b"".join(chunks)


class AlbumArchive:
    def __init__(self, store: AlbumStore, fetcher=None):
        self.store, self.fetcher = store, fetcher
        self.event = asyncio.Event()
        self.writes = set()
        self.task = None
        self.session = None
        self.retry_at = {}

    async def record(self, track):
        try:
            key = await asyncio.to_thread(self.store.record, track)
            self.event.set()
            return key
        except Exception:
            log.exception("Could not persist album; live recognition continues")
            return None

    def submit(self, track):
        task = asyncio.create_task(self.record(track))
        self.writes.add(task)
        task.add_done_callback(self.writes.discard)

    def start(self):
        self.task = asyncio.create_task(self.run())

    async def cache_album(self, album):
        last_error = None
        for url in artwork_candidates(album["source_url"]):
            try:
                data = (
                    await self.fetcher(url)
                    if self.fetcher
                    else await download_image(self.session, url)
                )
                suffix = image_suffix(data)
                filename = album["id"] + suffix

                def save():
                    temporary = self.store.cache / (album["id"] + ".tmp")
                    try:
                        temporary.write_bytes(data)
                        temporary.replace(self.store.cache / filename)
                        self.store.set_cached(album["id"], filename)
                    finally:
                        temporary.unlink(missing_ok=True)

                await asyncio.to_thread(save)
                self.retry_at.pop(album["id"], None)
                return
            except asyncio.CancelledError:
                raise
            except Exception as error:
                last_error = error
        self.retry_at[album["id"]] = time.monotonic() + 60
        log.warning("Album artwork unavailable; retrying later (%s)", type(last_error).__name__)

    async def _loop(self):
        while True:
            self.event.clear()
            try:
                pending = await asyncio.to_thread(self.store.pending)
                for album in pending:
                    if time.monotonic() >= self.retry_at.get(album["id"], 0):
                        await self.cache_album(album)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Album cache unavailable; retrying later")
            try:
                await asyncio.wait_for(self.event.wait(), timeout=60)
            except TimeoutError:
                pass

    async def run(self):
        if self.fetcher:
            await self._loop()
        else:
            import aiohttp

            timeout = aiohttp.ClientTimeout(total=12, connect=4, sock_read=4)
            async with aiohttp.ClientSession(timeout=timeout) as self.session:
                await self._loop()

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.writes:
            await asyncio.gather(*self.writes, return_exceptions=True)
