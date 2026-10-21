"""Validated configuration; no hardware imports."""

import math
import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path

from .platforms import user_data_directory


@dataclass(frozen=True)
class Config:
    host: str = "127.0.0.1"
    port: int = 8080
    device: str | int | None = None
    capture_rate: int | None = None
    channels: int = 1
    model_path: str = "models/yamnet"
    music_threshold: float = 0.5
    silence_db: float = -50.0
    positive_windows: int = 2
    sample_seconds: int = 10
    attempt_interval: float = 20
    silence_seconds: float = 30
    track_expiry: float = 90
    request_timeout: float = 15
    max_backoff: float = 120
    inference_timeout: float = 10
    model_startup_timeout: float = 120
    state_dir: str = "data"

    def __post_init__(self):
        integer_fields = ("port", "channels", "positive_windows", "sample_seconds")
        for name in integer_fields:
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.capture_rate is not None and (
            type(self.capture_rate) is not int or self.capture_rate <= 0
        ):
            raise ValueError(
                "capture_rate must be a positive integer or omitted for auto detection"
            )
        if self.port > 65535 or self.channels > 32:
            raise ValueError("port must be <= 65535 and channels <= 32")
        for name in (
            "attempt_interval",
            "silence_seconds",
            "track_expiry",
            "request_timeout",
            "max_backoff",
            "inference_timeout",
            "model_startup_timeout",
            "music_threshold",
            "silence_db",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (float, int))
                or not math.isfinite(value)
            ):
                raise ValueError(f"{name} must be finite")
        for name in (
            "attempt_interval",
            "silence_seconds",
            "track_expiry",
            "request_timeout",
            "max_backoff",
            "inference_timeout",
            "model_startup_timeout",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not 0 <= self.music_threshold <= 1 or self.silence_db > 0:
            raise ValueError("music_threshold must be in [0, 1]; silence_db must be <= 0")
        if self.max_backoff < self.attempt_interval:
            raise ValueError("max_backoff must be >= attempt_interval")
        if (
            not isinstance(self.host, str)
            or not self.host
            or not isinstance(self.model_path, str)
            or not self.model_path
        ):
            raise ValueError("host and model_path must be nonempty strings")
        if not isinstance(self.state_dir, str) or not self.state_dir.strip():
            raise ValueError("state_dir must be a nonempty directory path")
        if self.device is not None and (
            isinstance(self.device, bool) or not isinstance(self.device, (str, int))
        ):
            raise ValueError("device must be a name or integer index")


def load_config(path: Path | None) -> Config:
    if path is None:
        base = user_data_directory()
        return replace(
            Config(), model_path=str(base / "models/yamnet"), state_dir=str(base / "data")
        )
    path = path.expanduser().resolve()
    with path.open("rb") as source:
        values = tomllib.load(source)
    unknown = values.keys() - {field.name for field in fields(Config)}
    if unknown:
        raise ValueError(f"Unknown configuration keys: {', '.join(sorted(unknown))}")
    config = Config(**values)
    base = path.expanduser().resolve().parent

    def anchored(value):
        candidate = Path(value).expanduser()
        return str(candidate if candidate.is_absolute() else base / candidate)

    return replace(
        config, model_path=anchored(config.model_path), state_dir=anchored(config.state_dir)
    )
