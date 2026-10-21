import io
import unittest
import wave

import numpy as np

from now_playing.recognizer import Recognizer, parse_track, wav_bytes

MATCH = {
    "matches": [{"id": "123"}],
    "track": {
        "key": "123",
        "title": "A song",
        "subtitle": "An artist",
        "images": {"coverarthq": "https://example.com/cover.jpg"},
        "sections": [{"type": "SONG", "metadata": [{"title": "Album", "text": "An album"}]}],
    },
}


class RecognitionTests(unittest.TestCase):
    def test_match_and_optional_fields(self):
        track = parse_track(MATCH)
        self.assertEqual(
            (track.id, track.title, track.artist, track.album, track.artwork_url),
            ("123", "A song", "An artist", "An album", "https://example.com/cover.jpg"),
        )
        self.assertIsNone(parse_track({"track": {"key": "1", "title": "t", "subtitle": "a"}}).album)

    def test_no_match_and_malformed(self):
        for data in (
            {},
            {"matches": []},
            {"track": None},
            {"track": "oops"},
            {"track": {"key": "1"}},
            None,
            {"track": {"title": 3}},
        ):
            with self.subTest(data=data):
                self.assertIsNone(parse_track(data))

    def test_unsafe_or_malformed_artwork(self):
        for url in (
            "javascript:alert(1)",
            "file:///tmp/a",
            "https:///broken",
            "https://user:password@host/a",
            None,
        ):
            track = parse_track(
                {
                    "track": {
                        "key": "1",
                        "title": "t",
                        "subtitle": "a",
                        "images": {"coverarthq": url},
                        "sections": "bad",
                    }
                }
            )
            self.assertIsNone(track.artwork_url)

    def test_wav_in_memory(self):
        data = wav_bytes(np.array([-2, -0.5, 0, 0.5, 2]), 16000)
        with wave.open(io.BytesIO(data)) as audio:
            self.assertEqual(
                (
                    audio.getnchannels(),
                    audio.getsampwidth(),
                    audio.getframerate(),
                    audio.getnframes(),
                ),
                (1, 2, 16000, 5),
            )
            self.assertEqual(
                np.frombuffer(audio.readframes(5), dtype="<i2").tolist(),
                [-32767, -16383, 0, 16383, 32767],
            )


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_bytes_sent_and_provider_closed(self):
        class Provider:
            closed = False

            async def recognize(self, data):
                if not data.startswith(b"RIFF"):
                    raise AssertionError("provider needs encoded audio")
                return MATCH

            async def close(self):
                self.closed = True

        provider = Provider()
        async with Recognizer(provider) as recognizer:
            self.assertEqual((await recognizer.recognize(np.zeros(16000), 16000)).id, "123")
        self.assertTrue(provider.closed)
