import asyncio
import unittest

import numpy as np

from now_playing.config import Config
from now_playing.engine import Engine
from now_playing.models import Track
from now_playing.runtime import LiveRuntime


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_recognition_does_not_block_capture(self):
        now = [0.0]
        count = [0]
        started = asyncio.Event()
        release = asyncio.Event()

        class Capture:
            discontinuity = False

            async def windows(self):
                for _ in range(40):
                    count[0] += 1
                    yield np.ones(16000, dtype=np.float32)
                    await asyncio.sleep(0.002)

        class Detector:
            def is_music(self, _):
                return True

            async def classify(self, window):
                return self.is_music(window)

        class Provider:
            calls = 0

            async def recognize(self, samples, rate):
                self.calls += 1
                started.set()
                await release.wait()
                return Track("1", "Song", "Artist")

        provider = Provider()
        runtime = LiveRuntime(Config(), Engine(Config(), lambda: now[0]), Detector(), provider)
        task = asyncio.create_task(runtime.consume(Capture()))
        await asyncio.wait_for(started.wait(), 2)
        await task
        self.assertEqual(count[0], 40)
        self.assertEqual(provider.calls, 1)
        release.set()
        await runtime.close()

    async def test_timeout_cancels_and_ticks_continue_without_audio(self):
        cancelled = asyncio.Event()

        class Provider:
            async def recognize(self, *_):
                try:
                    await asyncio.sleep(5)
                finally:
                    cancelled.set()

        config = Config(request_timeout=0.02)
        engine = Engine(config, __import__("time").monotonic)
        engine.observe(True)
        engine.observe(True)
        runtime = LiveRuntime(config, engine, None, Provider())
        runtime.start_request(np.zeros(160000))
        await asyncio.wait_for(cancelled.wait(), 1)
        await asyncio.sleep(0.01)
        self.assertEqual(engine.snapshot().status, "unavailable")
        await runtime.close()

    async def test_observation_after_watchdog_failure_is_ignored(self):
        import threading

        release = threading.Event()
        entered = threading.Event()

        class Detector:
            def is_music(self, _):
                entered.set()
                release.wait(2)
                return True

            async def classify(self, window):
                return await asyncio.to_thread(self.is_music, window)

        class Capture:
            discontinuity = False

            async def windows(self):
                yield np.ones(16000)

        config = Config()
        engine = Engine(config, __import__("time").monotonic)
        runtime = LiveRuntime(config, engine, Detector(), None)
        task = asyncio.create_task(runtime.consume(Capture()))
        await asyncio.wait_for(asyncio.to_thread(entered.wait, 1), 2)
        runtime.last_window = __import__("time").monotonic() - 20
        ticker = asyncio.create_task(runtime.tick())
        await asyncio.sleep(0.01)
        self.assertEqual(engine.snapshot().status, "unavailable")
        release.set()
        await task
        self.assertEqual(engine.snapshot().status, "unavailable")
        ticker.cancel()
        await asyncio.gather(ticker, return_exceptions=True)
        await runtime.close()

    async def test_only_accepted_matches_reach_album_archive(self):
        now = [0.0]

        class Provider:
            async def recognize(self, *_):
                return Track("album-song", "Song", "Artist", "Album")

        class Archive:
            tracks = []

            def submit(self, track):
                self.tracks.append(track)

        engine = Engine(Config(), lambda: now[0])
        engine.observe(True)
        engine.observe(True)
        archive = Archive()
        runtime = LiveRuntime(Config(), engine, None, Provider(), archive=archive)
        token = engine.begin_recognition()
        await runtime._recognize(token, np.zeros(160000))
        self.assertEqual([track.id for track in archive.tracks], ["album-song"])
        now[0] = 20
        engine.observe(True)
        token = engine.begin_recognition()
        engine.capture_failed()
        await runtime._recognize(token, np.zeros(160000))
        self.assertEqual(len(archive.tracks), 1)
        await runtime.close()
