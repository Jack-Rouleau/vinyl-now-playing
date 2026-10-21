import tempfile
import unittest
from pathlib import Path

from now_playing.config import Config, load_config
from now_playing.models import DisplayState, Track


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        c = load_config(None)
        self.assertEqual(
            (c.host, c.port, c.sample_seconds, c.attempt_interval), ("127.0.0.1", 8080, 10, 20)
        )
        self.assertEqual(
            (c.music_threshold, c.positive_windows, c.silence_seconds, c.track_expiry),
            (0.5, 2, 30, 90),
        )

    def test_invalid_config(self):
        for values in [
            {"port": 0},
            {"music_threshold": 2},
            {"attempt_interval": 0},
            {"capture_rate": -1},
            {"request_timeout": float("nan")},
            {"positive_windows": 1.5},
        ]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                Config(**values)

    def test_toml(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text('device = "USB"\nport = 8123\n')
            self.assertEqual(load_config(path).device, "USB")
            self.assertEqual(load_config(path).port, 8123)
            path.write_text("unknown = 2")
            with self.assertRaises(ValueError):
                load_config(path)

    def test_state_json(self):
        state = DisplayState("matched", Track("a", "Title", "Artist", None, None), 1)
        self.assertEqual(
            state.to_dict(),
            {
                "status": "matched",
                "track": {
                    "id": "a",
                    "title": "Title",
                    "artist": "Artist",
                    "album": None,
                    "artwork_url": None,
                },
                "revision": 1,
                "activity": "listening",
            },
        )

    def test_paths_are_relative_to_config_not_working_directory(self):
        with tempfile.TemporaryDirectory(prefix="now playing ") as directory:
            config_file = Path(directory) / "settings.toml"
            config_file.write_text('model_path = "models/yamnet"\nstate_dir = "albums"\n')
            config = load_config(config_file)
            self.assertEqual(Path(config.model_path), Path(directory).resolve() / "models/yamnet")
            self.assertEqual(Path(config.state_dir), Path(directory).resolve() / "albums")
