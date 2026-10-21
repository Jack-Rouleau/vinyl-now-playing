import unittest

from now_playing.config import Config
from now_playing.engine import Engine
from now_playing.models import Track


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.engine = Engine(Config(), lambda: self.now)
        self.track = Track("one", "Title", "Artist")

    def ready(self):
        self.engine.observe(True)
        self.engine.observe(True)

    def match(self):
        self.ready()
        token = self.engine.begin_recognition()
        self.engine.complete(token, self.track)

    def test_gating_cooldown_single_flight(self):
        self.engine.observe(True)
        self.assertIsNone(self.engine.begin_recognition())
        self.engine.observe(True)
        token = self.engine.begin_recognition()
        self.assertIsNotNone(token)
        self.assertIsNone(self.engine.begin_recognition())
        self.engine.complete(token, self.track)
        self.now = 19
        self.engine.observe(True)
        self.assertIsNone(self.engine.begin_recognition())
        self.now = 20
        self.engine.observe(True)
        self.assertIsNotNone(self.engine.begin_recognition())

    def test_track_change_and_repeat(self):
        self.match()
        revision = self.engine.snapshot().revision
        self.now = 20
        self.engine.observe(True)
        token = self.engine.begin_recognition()
        self.assertEqual(self.engine.snapshot().status, "matched")
        self.engine.complete(token, self.track)
        self.assertEqual(self.engine.snapshot().revision, revision)
        self.now = 40
        self.engine.observe(True)
        self.engine.complete(self.engine.begin_recognition(), Track("two", "Next", "Artist"))
        self.assertEqual(self.engine.snapshot().track.id, "two")

    def test_no_match_and_expiry_with_continuous_music(self):
        self.match()
        self.now = 20
        self.engine.observe(True)
        self.engine.complete(self.engine.begin_recognition(), None)
        self.assertEqual(self.engine.snapshot().track, self.track)
        self.now = 89
        self.engine.observe(True)
        self.assertEqual(self.engine.snapshot().track, self.track)
        self.now = 90
        self.engine.observe(True)
        self.assertIsNone(self.engine.snapshot().track)
        self.assertEqual(self.engine.snapshot().status, "identifying")

    def test_silence_and_late_result(self):
        self.ready()
        token = self.engine.begin_recognition()
        self.now = 30
        self.engine.observe(False)
        self.assertEqual(self.engine.snapshot().status, "idle")
        self.engine.complete(token, self.track)
        self.assertIsNone(self.engine.snapshot().track)

    def test_no_events_still_expires(self):
        self.match()
        self.now = 30
        self.engine.tick()
        self.assertEqual(self.engine.snapshot().status, "idle")

    def test_timeout_backoff_and_late_result(self):
        self.ready()
        token = self.engine.begin_recognition()
        self.now = 15
        self.engine.observe(True)
        self.engine.tick()
        self.engine.complete(token, self.track)
        self.assertIsNone(self.engine.snapshot().track)
        self.now = 19
        self.assertIsNone(self.engine.begin_recognition())
        self.now = 20
        self.assertIsNotNone(self.engine.begin_recognition())

    def test_late_completion_before_next_tick_is_rejected(self):
        self.ready()
        token = self.engine.begin_recognition()
        self.now = 16
        self.engine.complete(token, self.track)
        self.assertIsNone(self.engine.snapshot().track)
        self.assertEqual(self.engine.snapshot().status, "unavailable")

    def test_failure_backoff_cap_and_reset(self):
        self.ready()
        for delay in (20, 40, 80, 120, 120):
            started = self.now
            token = self.engine.begin_recognition()
            self.assertIsNotNone(token)
            self.engine.complete(token, None, failed=True)
            self.now = started + delay - 1
            self.engine.observe(True)
            self.assertIsNone(self.engine.begin_recognition())
            self.now = started + delay
            self.engine.observe(True)
        token = self.engine.begin_recognition()
        self.engine.complete(token, self.track)
        self.now += 20
        self.engine.observe(True)
        self.assertIsNotNone(self.engine.begin_recognition())

    def test_capture_failure_clears_and_recovers(self):
        self.match()
        self.engine.capture_failed()
        self.assertEqual(self.engine.snapshot().status, "unavailable")
        self.assertIsNone(self.engine.snapshot().track)
        self.ready()
        self.assertEqual(self.engine.snapshot().status, "identifying")

    def test_speech_resets_positive_windows(self):
        self.engine.observe(True)
        self.engine.observe(False)
        self.engine.observe(True)
        self.assertIsNone(self.engine.begin_recognition())

    def test_activity_is_independent_of_displayed_track(self):
        self.assertEqual(self.engine.snapshot().activity, "listening")
        self.ready()
        self.assertEqual(self.engine.snapshot().activity, "music_detected")
        token = self.engine.begin_recognition()
        self.assertEqual(self.engine.snapshot().activity, "identifying")
        self.engine.complete(token, self.track)
        self.now = 20
        self.engine.observe(True)
        self.engine.begin_recognition()
        self.assertEqual(self.engine.snapshot().status, "matched")
        self.assertEqual(self.engine.snapshot().activity, "identifying")
        self.assertEqual(self.engine.snapshot().track, self.track)
        self.engine.capture_failed()
        self.assertEqual(self.engine.snapshot().activity, "paused")
