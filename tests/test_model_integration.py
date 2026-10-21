"""Run against the real model when live dependencies and local assets exist."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models/yamnet"


@unittest.skipUnless(
    importlib.util.find_spec("tensorflow") and (MODEL / "saved_model.pb").is_file(),
    "local YAMNet and TensorFlow required",
)
class ModelIntegrationTests(unittest.TestCase):
    def test_local_saved_model_loads_and_classifies_silence(self):
        import numpy as np

        from now_playing.config import Config
        from now_playing.detector import MusicDetector

        detector = MusicDetector(Config(model_path=str(MODEL)))
        self.assertEqual(len(detector.labels), 521)
        scores = detector._inference(np.zeros(16000, dtype=np.float32))
        self.assertEqual(scores.shape[1], 521)
        self.assertTrue(np.isfinite(scores).all())
        self.assertFalse(detector.is_music(np.zeros(16000, dtype=np.float32)))
