import unittest

import numpy as np

from now_playing.audio import AudioBuffer, AudioCapture, WindowQueue, normalize_audio
from now_playing.config import Config


class AudioTests(unittest.TestCase):
    def test_downmix_and_resampling(self):
        source = np.column_stack((np.ones(48000), np.zeros(48000)))
        result = normalize_audio(source, 48000)
        self.assertEqual(result.shape, (16000,))
        np.testing.assert_allclose(result[20:-20], 0.5, atol=0.001)

    def test_buffer_full_and_bounded(self):
        buffer = AudioBuffer(10)
        for _ in range(9):
            buffer.append(np.ones(16000, dtype=np.float32))
        self.assertIsNone(buffer.sample())
        buffer.append(np.zeros(16000, dtype=np.float32))
        self.assertEqual(len(buffer.sample()), 160000)
        buffer.append(np.full(16000, 2, dtype=np.float32))
        self.assertEqual(len(buffer.sample()), 160000)
        self.assertEqual(buffer.sample()[-1], 2)
        buffer.clear()
        self.assertIsNone(buffer.sample())

    def test_queue_drops_old_data_and_reports_gap(self):
        queue = WindowQueue(2)
        queue.push(np.zeros(2))
        queue.push(np.ones(2))
        queue.push(np.full(2, 2))
        window, gap = queue.pop(0.1)
        self.assertTrue(gap)
        self.assertEqual(window.tolist(), [1, 1])
        _, gap = queue.pop(0.1)
        self.assertFalse(gap)

    def test_queue_marks_portaudio_overflow(self):
        queue = WindowQueue(2)
        queue.push(np.zeros(2), gap=True)
        self.assertTrue(queue.pop(0.1)[1])


class CaptureTests(unittest.IsolatedAsyncioTestCase):
    async def test_bad_device_is_actionable(self):
        class SD:
            @staticmethod
            def check_input_settings(**kwargs):
                raise ValueError("invalid sample rate")

        with self.assertRaisesRegex(RuntimeError, "input device.*capture_rate"):
            async with AudioCapture(Config(capture_rate=48000), backend=SD()):
                pass

    async def test_disconnect_is_reported_and_stream_closed(self):
        class Stream:
            closed = False
            active = False

            def start(self):
                pass

            def stop(self):
                pass

            def close(self):
                self.closed = True

        stream = Stream()

        class SD:
            @staticmethod
            def check_input_settings(**kwargs):
                pass

            @staticmethod
            def InputStream(**kwargs):
                return stream

        with self.assertRaisesRegex(RuntimeError, "stopped"):
            async with AudioCapture(Config(capture_rate=48000), backend=SD()) as capture:
                await anext(capture.windows())
        self.assertTrue(stream.closed)
