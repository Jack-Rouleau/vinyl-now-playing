import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from now_playing.albums import AlbumStore, album_key
from now_playing.models import Track

ART = "https://is1-ssl.mzstatic.com/image/thumb/Music211/v4/a/album.jpg/400x400cc.jpg"


class AlbumTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.store = AlbumStore(self.path)
        self.track = Track("one", "Song", "Artist", "Album", ART)

    def test_persists_and_deduplicates_songs_and_cdn_variants(self):
        key = self.store.record(self.track)
        variant = Track(
            "two",
            "Other song",
            "Guest artist",
            "Album",
            ART.replace("is1-ssl", "is2-ssl").replace("400x400cc", "1200x1200bb"),
        )
        self.assertEqual(self.store.record(variant), key)
        reopened = AlbumStore(self.path)
        self.assertEqual(len(reopened.pending()), 1)
        self.assertEqual(reopened.pending()[0]["album"], "Album")
        self.assertEqual(album_key(self.track), album_key(variant))
        distinct = Track(
            "three", "Song", "Artist", "Album", ART.replace("album.jpg", "different.jpg")
        )
        self.assertNotEqual(self.store.record(distinct), key)

    def test_missing_art_keeps_metadata_without_placeholder_tiles(self):
        self.store.record(Track("one", "Song", "Artist", "Album"))
        self.assertEqual(self.store.snapshot()["albums"], [])
        self.assertEqual(self.store.pending(), [])
        with self.store.connect() as db:
            self.assertEqual(db.execute("select count(*) from albums").fetchone()[0], 1)

    def test_revision_and_cached_artwork(self):
        initial = self.store.snapshot()["revision"]
        key = self.store.record(self.track)
        after_record = self.store.snapshot()["revision"]
        self.store.record(self.track)
        self.assertEqual(self.store.snapshot()["revision"], after_record)
        self.assertGreater(after_record, initial)
        (self.path / "artwork" / f"{key}.jpg").write_bytes(b"image-data")
        self.store.set_cached(key, f"{key}.jpg")
        item = self.store.snapshot()["albums"][0]
        self.assertEqual(item["artwork_url"], f"/artwork/{key}")
        self.assertEqual(self.store.artwork(key), ("image/jpeg", b"image-data"))
        self.assertIsNone(self.store.artwork("../albums.sqlite3"))

    def test_concurrent_repeats_remain_one_album(self):
        with ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda _: self.store.record(self.track), range(20)))
        self.assertEqual(len(self.store.pending()), 1)

    def test_fresh_canonical_artwork_url_replaces_expired_source(self):
        key = self.store.record(self.track)
        fresh = Track(
            "two", "Other song", "Artist", "Album", ART.replace("is1-ssl", "is2-ssl") + "?fresh=1"
        )
        self.assertEqual(self.store.record(fresh), key)
        self.assertEqual(self.store.pending()[0]["source_url"], fresh.artwork_url)
