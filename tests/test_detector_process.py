import asyncio
import unittest

from now_playing.config import Config
from now_playing.detector_process import ProcessDetector


def worker(connection, config):
    import time

    if config.model_path == "startup-hang":
        time.sleep(30)
    connection.send(("ready", None))
    while True:
        value = connection.recv()
        if value == "hang":
            time.sleep(30)
        connection.send(("result", value == "music"))


class ProcessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().slow_callback_duration = 2

    async def test_classifies_and_cleans_up_worker(self):
        detector = ProcessDetector(Config(), worker=worker)
        async with detector:
            self.assertTrue(await detector.classify("music"))
            self.assertFalse(await detector.classify("speech"))
        self.assertFalse(detector.process.is_alive())

    async def test_hung_inference_is_terminated_and_can_restart(self):
        detector = ProcessDetector(Config(inference_timeout=0.05), worker=worker)
        async with detector:
            with self.assertRaisesRegex(RuntimeError, "deadline"):
                await detector.classify("hang")
            self.assertTrue(await detector.classify("music"))
        self.assertFalse(detector.process.is_alive())
        async with ProcessDetector(Config(), worker=worker) as recovered:
            self.assertTrue(await recovered.classify("music"))

    async def test_hung_startup_is_terminated(self):
        detector = ProcessDetector(
            Config(model_path="startup-hang", model_startup_timeout=0.1), worker=worker
        )
        with self.assertRaisesRegex(RuntimeError, "deadline"):
            async with detector:
                pass
        self.assertFalse(detector.process.is_alive())
