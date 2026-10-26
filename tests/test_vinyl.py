import unittest
from dataclasses import replace

from now_playing.config import Config
from now_playing.engine import Engine
from now_playing.models import Track
from now_playing.recognizer import parse_track


class VinylTests(unittest.TestCase):
    def setUp(self):
        from now_playing.models import AlbumTrack

        self.now = 0.0
        self.engine = Engine(Config(), lambda: self.now)
        self.song = Track("one", "First", "Artist", "Album", position_seconds=70)
        self.second = Track("two", "Second", "Artist", "Album")
        self.third = Track("three", "Third", "Artist", "Album")
        self.tracks = (
            AlbumTrack(self.song, 100),
            AlbumTrack(self.second, 120),
            AlbumTrack(self.third, 80),
        )
        self.match(self.song)
        self.engine.set_tracklist(self.token, self.tracks)

    def match(self, song, captured_at=None):
        self.engine.observe(True)
        self.engine.observe(True)
        self.token = self.engine.begin_recognition()
        self.assertIsNotNone(self.token)
        self.engine.complete(self.token, song, captured_at=captured_at)

    def advance(self, seconds):
        # Keep music observations flowing rather than bypassing silence expiry.
        while self.now < seconds:
            self.now = min(seconds, self.now + 10)
            self.engine.observe(True)

    def test_next_track_and_inferred_transitions(self):
        self.assertEqual(self.engine.snapshot().next_track.title, "Second")
        self.advance(30)
        self.assertEqual(self.engine.snapshot().track.title, "Second")
        self.assertTrue(self.engine.snapshot().inferred)
        self.assertEqual(self.engine.snapshot().next_track.title, "Third")
        self.advance(150)
        self.assertEqual(self.engine.snapshot().track.title, "Third")
        self.advance(230)
        self.assertIsNone(self.engine.snapshot().track)
        self.assertIsNone(self.engine.snapshot().next_track)

    def test_confirmed_match_corrects_and_removes_marker(self):
        self.advance(40)
        self.match(replace(self.second, position_seconds=20))
        self.assertFalse(self.engine.snapshot().inferred)
        self.advance(139)
        self.assertEqual(self.engine.snapshot().track.title, "Second")
        self.advance(140)
        self.assertEqual(self.engine.snapshot().track.title, "Third")
        self.assertTrue(self.engine.snapshot().inferred)

    def test_repeated_match_without_offset_does_not_restart_clock(self):
        self.advance(20)
        self.match(replace(self.song, position_seconds=None))
        self.engine.set_tracklist(self.token, self.tracks)
        self.advance(30)
        self.assertEqual(self.engine.snapshot().track.title, "Second")

    def test_silence_and_capture_failure_clear_timeline(self):
        self.now = 30
        self.engine.observe(False)
        self.assertEqual(self.engine.snapshot().status, "idle")
        self.assertIsNone(self.engine.snapshot().next_track)
        self.assertFalse(self.engine.set_tracklist(self.token, self.tracks))
        self.match(self.song)
        self.engine.set_tracklist(self.token, self.tracks)
        self.engine.capture_failed()
        self.assertIsNone(self.engine.snapshot().next_track)
        self.assertFalse(self.engine.set_tracklist(self.token, self.tracks))

    def test_stale_tracklist_cannot_replace_new_record(self):
        old = self.token
        self.advance(20)
        self.match(Track("other", "Other", "Someone", "Other album"))
        self.assertFalse(self.engine.set_tracklist(old, self.tracks))
        self.assertIsNone(self.engine.snapshot().next_track)

    def test_sample_time_not_response_time_anchors_offset(self):
        self.advance(20)
        self.match(replace(self.song, position_seconds=80), captured_at=10)
        self.advance(30)
        self.assertEqual(self.engine.snapshot().track.title, "Second")

    def test_missing_position_uses_first_match_and_survives_expiry(self):
        self.advance(20)
        self.match(replace(self.second, position_seconds=None))
        self.advance(110)
        self.assertEqual(self.engine.snapshot().track.title, "Second")
        self.advance(140)
        self.assertEqual(self.engine.snapshot().track.title, "Third")

    def test_network_failure_does_not_stop_known_timeline(self):
        self.advance(20)
        self.match(None)
        self.advance(30)
        self.assertEqual(self.engine.snapshot().track.title, "Second")


class OffsetTests(unittest.TestCase):
    def test_playback_offset_is_optional_and_validated(self):
        payload = {
            "track": {"key": "1", "title": "Song", "subtitle": "Artist"},
            "matches": [{"offset": 65.5}],
        }
        self.assertEqual(parse_track(payload).position_seconds, 65.5)
        for offset in (None, -2, float("nan"), float("inf"), "65", True):
            payload["matches"][0]["offset"] = offset
            self.assertIsNone(parse_track(payload).position_seconds)
