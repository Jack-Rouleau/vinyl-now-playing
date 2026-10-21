import json
import unittest

from now_playing.demo import Demo
from now_playing.models import DisplayState
from now_playing.server import response_for


class ServerTests(unittest.TestCase):
    def test_state_and_missing_routes(self):
        state = DisplayState("idle", None, 7)
        code, mime, body = response_for("/api/state", lambda: state)
        self.assertEqual(code, 200)
        self.assertEqual(mime, "application/json")
        self.assertEqual(
            json.loads(body),
            {"status": "idle", "track": None, "revision": 7, "activity": "listening"},
        )
        self.assertEqual(response_for("/../../config.toml", lambda: state)[0], 404)
        self.assertEqual(response_for("/missing", lambda: state)[0], 404)

    def test_demo_fixed_and_cycle(self):
        now = [0.0]
        demo = Demo(clock=lambda: now[0])
        self.assertEqual(demo.snapshot().status, "idle")
        now[0] = 4
        self.assertEqual(demo.snapshot().status, "identifying")
        now[0] = 8
        self.assertEqual(demo.snapshot().status, "matched")
        now[0] = 24
        self.assertEqual(demo.snapshot().status, "unavailable")
        for status in ("idle", "identifying", "matched", "unavailable"):
            self.assertEqual(Demo(fixed=status).snapshot().status, status)

    def test_album_routes_and_safe_artwork_keys(self):
        import tempfile
        from pathlib import Path

        from now_playing.albums import AlbumStore
        from now_playing.models import Track

        with tempfile.TemporaryDirectory() as directory:
            store = AlbumStore(Path(directory))
            key = store.record(Track("1", "Song", "Artist", "Album"))
            (store.cache / f"{key}.jpg").write_bytes(b"cached-cover")
            store.set_cached(key, f"{key}.jpg")
            state = DisplayState()
            code, mime, body = response_for(
                "/api/albums", lambda: state, store.snapshot, store.artwork
            )
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body)["albums"][0]["id"], key)
            self.assertEqual(
                response_for("/artwork/" + key, lambda: state, store.snapshot, store.artwork),
                (200, "image/jpeg", b"cached-cover"),
            )
            for path in (
                "/artwork/../albums.sqlite3",
                "/artwork/%2e%2e%2falbums.sqlite3",
                "/artwork/unknown",
            ):
                self.assertEqual(
                    response_for(path, lambda: state, store.snapshot, store.artwork)[0], 404
                )
