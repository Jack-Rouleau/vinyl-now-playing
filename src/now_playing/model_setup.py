"""Install the official YAMNet SavedModel without importing TensorFlow."""

from __future__ import annotations

import logging
import re
import shutil
import tarfile
import tempfile
import time
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from urllib.request import urlopen

MODEL_URL = "https://tfhub.dev/google/yamnet/1?tf-hub-format=compressed"
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
_REQUIRED = ("saved_model.pb", "variables/variables.index", "assets/yamnet_class_map.csv")
_ALLOWED = re.compile(
    r"^(saved_model\.pb|assets/yamnet_class_map\.csv|variables/variables\.index|variables/variables\.data-\d+-of-\d+)$"
)
log = logging.getLogger(__name__)


def model_is_ready(path: Path) -> bool:
    files = [path / name for name in _REQUIRED]
    files.extend(path.glob("variables/variables.data-*-of-*"))
    return len(files) > len(_REQUIRED) and all(
        file.is_file() and file.stat().st_size > 0 for file in files
    )


def download_model(url: str, destination: Path) -> None:
    deadline = time.monotonic() + 120
    count = 0
    with urlopen(url, timeout=10) as response, destination.open("wb") as output:
        if int(response.headers.get("Content-Length", "0")) > MAX_ARCHIVE_BYTES:
            raise ValueError("Model download exceeds 64 MiB")
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError("Model download exceeded two minutes; rerun setup to retry")
            chunk = response.read(65536)
            if not chunk:
                break
            count += len(chunk)
            if count > MAX_ARCHIVE_BYTES:
                raise ValueError("Model download exceeds 64 MiB")
            output.write(chunk)


def _extract_model(archive_path: Path, destination: Path) -> None:
    total = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for index, member in enumerate(archive):
            path = PurePosixPath(member.name)
            if (
                index > 32
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in member.name
                or ":" in member.name
            ):
                raise ValueError("Unsafe path in model archive")
            if member.isdir() and str(path) in (".", "assets", "variables"):
                continue
            if not member.isfile() or not _ALLOWED.fullmatch(str(path)):
                raise ValueError(f"Unexpected model archive member: {member.name}")
            total += member.size
            if member.size < 0 or total > MAX_EXPANDED_BYTES:
                raise ValueError("Expanded model exceeds 128 MiB")
            target = destination.joinpath(*path.parts)
            if target.exists():
                raise ValueError("Duplicate file in model archive")
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("Unreadable model archive member")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=65536)
    if not model_is_ready(destination):
        raise ValueError(
            "Downloaded model is incomplete; expected SavedModel, weights, and class map"
        )


def install_archive(archive_path: Path, target: Path) -> None:
    """Stage/validate before replacing a previous incomplete installation."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".yamnet-install-", dir=target.parent) as temporary:
        staged = Path(temporary) / "model"
        staged.mkdir()
        _extract_model(archive_path, staged)
        backup = Path(temporary) / "previous"
        if target.exists():
            target.rename(backup)
        try:
            staged.rename(target)
        except BaseException:
            if backup.exists() and not target.exists():
                backup.rename(target)
            raise


def ensure_model(target: Path, *, downloader: Callable[[str, Path], None] = download_model) -> Path:
    target = target.expanduser().absolute()
    if model_is_ready(target):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading music detection model (first run only)…")
    with tempfile.TemporaryDirectory(prefix=".yamnet-download-", dir=target.parent) as temporary:
        archive = Path(temporary) / "model.tar.gz"
        downloader(MODEL_URL, archive)
        install_archive(archive, target)
    return target
