"""Live orchestration; recognition never blocks capture or state expiry."""

import asyncio
import logging
import time

from .audio import AudioBuffer, AudioCapture
from .config import Config
from .contracts import AlbumSink, Classifier, SongRecognizer
from .engine import Engine

log = logging.getLogger(__name__)


class LiveRuntime:
    def __init__(
        self,
        config: Config,
        engine: Engine,
        detector: Classifier | None,
        recognizer: SongRecognizer,
        archive: AlbumSink | None = None,
    ):
        self.config, self.engine = config, engine
        self.archive = archive
        self.detector, self.recognizer = detector, recognizer
        self.request = None
        self.last_window = time.monotonic()
        self.generation = 0

    def start_request(self, samples):
        if self.request is not None and not self.request.done():
            return
        token = self.engine.begin_recognition()
        if token is not None:
            self.request = asyncio.create_task(self._recognize(token, samples))

    async def _recognize(self, token, samples):
        try:
            log.info("Identifying the last %s seconds of music…", self.config.sample_seconds)
            async with asyncio.timeout(self.config.request_timeout):
                track = await self.recognizer.recognize(samples, 16000)
            accepted = self.engine.complete(token, track)
            if accepted and self.archive:
                self.archive.submit(track)
            if track is not None:
                log.info("Recognition result: %s — %s", track.artist, track.title)
            else:
                log.info("No song match this time; listening continues")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            log.warning("Recognition unavailable (%s); retrying with backoff", type(error).__name__)
            self.engine.complete(token, None, failed=True)

    async def consume(self, capture):
        buffer = AudioBuffer(self.config.sample_seconds)
        previous_music = None
        async for window in capture.windows():
            self.last_window = time.monotonic()
            if capture.discontinuity:
                buffer.clear()
                # Break consecutive positives and invalidate results from the old clip.
                self.engine.capture_failed()
            buffer.append(window)
            generation = self.generation
            music = await self.detector.classify(window)
            if generation != self.generation:
                buffer.clear()
                continue
            self.engine.observe(music)
            if music != previous_music:
                log.info(
                    "Music detected" if music else "Listening; no music detected in this window"
                )
                previous_music = music
            # Do not retain earlier music through a sustained speech/quiet interval.
            if self.engine.snapshot().status == "idle" and not music:
                buffer.clear()
            sample = buffer.sample()
            if sample is not None:
                self.start_request(sample)

    async def tick(self):
        while True:
            if time.monotonic() - self.last_window > self.config.inference_timeout + 2:
                self.generation += 1
                self.engine.capture_failed()
            self.engine.tick()
            await asyncio.sleep(0.25)

    async def close(self):
        if self.request is not None:
            self.request.cancel()
            await asyncio.gather(self.request, return_exceptions=True)


async def run_live(config: Config, engine: Engine, archive=None):
    from .detector_process import ProcessDetector
    from .recognizer import Recognizer

    async with ProcessDetector(config) as detector, Recognizer() as recognizer:
        runtime = LiveRuntime(config, engine, detector, recognizer, archive=archive)
        ticker = asyncio.create_task(runtime.tick())
        try:
            while True:
                try:
                    async with AudioCapture(config) as capture:
                        runtime.last_window = time.monotonic()
                        await runtime.consume(capture)
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    engine.capture_failed()
                    await runtime.close()
                    log.error("Audio unavailable: %s; retrying in five seconds", error)
                    await asyncio.sleep(5)
        finally:
            ticker.cancel()
            await asyncio.gather(ticker, return_exceptions=True)
            await runtime.close()
