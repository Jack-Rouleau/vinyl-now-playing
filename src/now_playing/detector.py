"""YAMNet adapter. Importing this module does not load TensorFlow."""

import csv
from pathlib import Path

import numpy as np

from .config import Config

# YAMNet's contiguous Music subtree (AudioSet class map positions 132..276).
# Includes singing, instruments, genres, and music moods without speech.
MUSIC_LABELS = {"Music", "Singing", "Choir", "Humming", "Whistling"}


def music_score(scores, labels) -> float:
    labels = list(labels)
    if "Music" not in labels:
        raise ValueError("YAMNet class map does not contain Music")
    if "Musical instrument" in labels and "Speech" in labels and len(labels) == 521:
        start = labels.index("Music")
        end = labels.index("Wind")
        indices = list(range(start, end)) + [
            i for i, label in enumerate(labels[:start]) if label in MUSIC_LABELS
        ]
    else:
        indices = [i for i, label in enumerate(labels) if label in MUSIC_LABELS]
    return float(np.asarray(scores).mean(axis=0)[list(indices)].max())


class MusicDetector:
    def __init__(self, config: Config, inference=None, labels=None):
        self.config = config
        if inference is not None:
            self._inference, self.labels = inference, labels
            return
        path = Path(config.model_path).expanduser()
        if not (path / "saved_model.pb").is_file():
            raise RuntimeError(f"YAMNet model missing at {path}; follow README model setup")
        try:
            import tensorflow as tf

            self._model = tf.saved_model.load(str(path))
            class_map = self._model.class_map_path().numpy().decode()
            with open(class_map, newline="") as source:
                self.labels = [row["display_name"] for row in csv.DictReader(source)]
            self._inference = lambda audio: self._model(audio)[0].numpy()
        except Exception as error:
            raise RuntimeError(
                f"Cannot load YAMNet at {path}: {type(error).__name__}: {error}"
            ) from error

    def is_music(self, window) -> bool:
        window = np.asarray(window, dtype=np.float32)
        rms = float(np.sqrt(np.mean(window**2)))
        if rms <= 10 ** (self.config.silence_db / 20):
            return False
        return music_score(self._inference(window), self.labels) >= self.config.music_threshold
