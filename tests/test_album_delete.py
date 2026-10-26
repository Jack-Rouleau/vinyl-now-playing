import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from now_playing.albums import AlbumStore
from now_playing.models import DisplayState, Track
from now_playing.server import Server


class AlbumDeleteTests(unittest.TestCase):
    def test_deletion_updates_revision_and_hides_all_covers(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AlbumStore(Path(folder))
            key = store.record(Track("1", "Song", "Artist", "Album"))
            (store.cache / (key + ".jpg")).write_bytes(b"cover")
            store.set_cached(key, key + ".jpg")
            revision = store.snapshot()["revision"]
            self.assertTrue(store.delete(key))
            self.assertEqual(store.snapshot(), {"revision": revision + 1, "albums": []})
            self.assertIsNone(store.artwork(key))
            self.assertFalse(store.delete(key))
            self.assertEqual(store.snapshot()["revision"], revision + 1)
            self.assertFalse(store.delete("../albums.sqlite3"))

    def test_http_delete_and_origin_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AlbumStore(Path(folder))
            key = store.record(Track("1", "Song", "Artist", "Album"))
            with Server(
                DisplayState, port=0, albums=store.snapshot, delete_album=store.delete
            ) as server:
                base = f"http://127.0.0.1:{server.http.server_port}"
                for origin in ("https://other.example", "null"):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(
                            Request(
                                base + "/api/albums/" + key,
                                method="DELETE",
                                headers={"Origin": origin},
                            )
                        )
                    self.assertEqual(error.exception.code, 403)
                request = Request(
                    base + "/api/albums/" + key, method="DELETE", headers={"Origin": base}
                )
                with urlopen(request) as response:
                    self.assertEqual(response.status, 200)
                with urlopen(base + "/api/albums") as response:
                    self.assertEqual(json.load(response)["albums"], [])
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base + "/api/albums/bad", method="DELETE"))
                self.assertEqual(error.exception.code, 400)
