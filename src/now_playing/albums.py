"""Durable unique albums and known cached artwork, independent of live state."""

import hashlib
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from .artwork import artwork_identity
from .models import Track

KEY = re.compile(r"^[a-f0-9]{64}$")
MIMES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def album_key(track: Track) -> str:
    if track.artwork_url:
        identity = artwork_identity(track.artwork_url)
    else:
        identity = "metadata:" + "\0".join(
            unicodedata.normalize("NFKC", value or "").strip().casefold()
            for value in (track.album, track.artist)
        )
    return hashlib.sha256(identity.encode()).hexdigest()


class AlbumStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.cache = self.path / "artwork"
        self.cache.mkdir(exist_ok=True)
        self.database = self.path / "albums.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS albums (
                    id TEXT PRIMARY KEY, album TEXT, artist TEXT NOT NULL,
                    source_url TEXT, filename TEXT
                );
                CREATE TABLE IF NOT EXISTS collection (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL);
                INSERT OR IGNORE INTO collection VALUES (1, 0);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def record(self, track: Track) -> str:
        key = album_key(track)
        with self.connect() as db:
            result = db.execute(
                "INSERT OR IGNORE INTO albums(id, album, artist, source_url) VALUES (?, ?, ?, ?)",
                (key, track.album, track.artist, track.artwork_url),
            )
            changed = result.rowcount
            if track.artwork_url:
                db.execute(
                    "UPDATE albums SET source_url=? WHERE id=? AND (source_url IS NULL OR source_url!=?)",
                    (track.artwork_url, key, track.artwork_url),
                )
            changed += db.execute(
                "UPDATE albums SET album=? WHERE id=? AND album IS NULL AND ? IS NOT NULL",
                (track.album, key, track.album),
            ).rowcount
            if changed:
                db.execute("UPDATE collection SET revision=revision+1 WHERE id=1")
        return key

    def delete(self, key: str) -> bool:
        if not KEY.fullmatch(key):
            return False
        with self.connect() as db:
            deleted = db.execute("DELETE FROM albums WHERE id=?", (key,)).rowcount
            if deleted:
                db.execute("UPDATE collection SET revision=revision+1 WHERE id=1")
        # Cached bytes may be in use by a concurrent download. Removing the row
        # makes them inaccessible; a later recognition can safely reuse the path.
        return bool(deleted)

    def snapshot(self) -> dict:
        with self.connect() as db:
            db.execute("BEGIN")
            revision = db.execute("SELECT revision FROM collection WHERE id=1").fetchone()[0]
            rows = db.execute(
                "SELECT id, album, artist, filename FROM albums WHERE filename IS NOT NULL ORDER BY rowid"
            ).fetchall()
        albums = [
            {
                "id": row["id"],
                "album": row["album"],
                "artist": row["artist"],
                "artwork_url": f"/artwork/{row['id']}",
            }
            for row in rows
            if (self.cache / row["filename"]).is_file()
        ]
        return {"revision": revision, "albums": albums}

    def pending(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id, source_url, filename, album FROM albums WHERE source_url IS NOT NULL ORDER BY rowid"
            ).fetchall()
        return [
            dict(row)
            for row in rows
            if not row["filename"] or not (self.cache / row["filename"]).is_file()
        ]

    def set_cached(self, key: str, filename: str):
        if not KEY.fullmatch(key) or filename not in {key + suffix for suffix in MIMES}:
            raise ValueError("Invalid album artwork reference")
        with self.connect() as db:
            result = db.execute(
                "UPDATE albums SET filename=? WHERE id=? AND (filename IS NULL OR filename!=?)",
                (filename, key, filename),
            )
            if result.rowcount:
                db.execute("UPDATE collection SET revision=revision+1 WHERE id=1")

    def artwork(self, key: str) -> tuple[str, bytes] | None:
        if not KEY.fullmatch(key):
            return None
        with self.connect() as db:
            row = db.execute("SELECT filename FROM albums WHERE id=?", (key,)).fetchone()
        if not row or row["filename"] not in {key + suffix for suffix in MIMES}:
            return None
        path = self.cache / row["filename"]
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            return None
        return MIMES[path.suffix], data
