import tempfile
import unittest

import numpy as np

from now_playing.config import Config
from now_playing.detector import MusicDetector, music_score


class DetectorTests(unittest.TestCase):
    def test_music_classes_not_speech(self):
        self.assertEqual(
            music_score(
                np.array([[0.9, 0.1, 0.2], [0.8, 0.3, 0.6]]), ["Speech", "Music", "Singing"]
            ),
            0.4,
        )

    def test_silence_skips_inference(self):
        def fail(_):
            self.fail("silence must skip inference")

        detector = MusicDetector(Config(), inference=fail, labels=["Music"])
        self.assertFalse(detector.is_music(np.zeros(16000)))

    def test_threshold_and_speech_only(self):
        detector = MusicDetector(
            Config(), inference=lambda _: np.array([[0.9, 0.5]]), labels=["Speech", "Music"]
        )
        self.assertTrue(detector.is_music(np.full(16000, 0.1)))
        detector = MusicDetector(
            Config(), inference=lambda _: np.array([[0.9, 0.49]]), labels=["Speech", "Music"]
        )
        self.assertFalse(detector.is_music(np.full(16000, 0.1)))

    def test_yamnet_nature_sounds_are_not_music(self):
        labels = [f"class {i}" for i in range(521)]
        for index, name in {
            0: "Speech",
            24: "Singing",
            132: "Music",
            133: "Musical instrument",
            276: "Scary music",
            277: "Wind",
            500: "Sonar",
        }.items():
            labels[index] = name
        scores = np.zeros((1, 521))
        scores[0, 277] = 0.9
        self.assertEqual(music_score(scores, labels), 0)
        scores[0, 24] = 0.8
        self.assertEqual(music_score(scores, labels), 0.8)

    def test_missing_model_is_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "YAMNet"):
                MusicDetector(Config(model_path=directory + "/absent"))
