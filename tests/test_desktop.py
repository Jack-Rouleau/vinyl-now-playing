import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from now_playing.desktop_service import DesktopService, desktop_config


class DesktopTests(unittest.TestCase):
    def test_bundled_model_and_writable_history_are_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = desktop_config(root / "bundle", root / "profile")
            self.assertEqual(Path(config.model_path), root / "bundle/models/yamnet")
            self.assertEqual(Path(config.state_dir), root / "profile/data")
            self.assertEqual(config.attempt_interval, 10)
            self.assertEqual(config.music_threshold, 0.1)

    def test_stop_uses_protocol_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            history = root / "data"
            history.mkdir()
            (history / "keep").touch()
            process = Mock()
            process.exitcode = None
            process.is_alive.side_effect = [True, False]
            connection = Mock()
            service = DesktopService(root)
            service.process = process
            service.connection = connection
            service.stop()
            connection.send.assert_called_once_with("stop")
            process.join.assert_called_once_with(timeout=8)
            process.terminate.assert_not_called()
            self.assertTrue((history / "keep").exists())

    def test_failed_worker_is_reported_and_does_not_delete_logs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "listener.log").write_text("Error: microphone access denied\n")
            service = DesktopService(root)
            service.process = Mock()
            service.process.exitcode = 1
            self.assertIn("microphone access denied", service.failure_message())
            self.assertNotIn("Traceback", service.failure_message())
            self.assertIn("Microphone settings", service.failure_message())

    def test_parent_disconnect_stops_async_worker_without_windows_signals(self):
        import asyncio

        from now_playing.desktop_service import stop_from_parent

        async def check():
            stop = asyncio.Event()
            connection = Mock()
            connection.recv.side_effect = EOFError
            await stop_from_parent(stop, connection)
            self.assertTrue(stop.is_set())

        asyncio.run(check())

    def test_real_backend_starts_and_stops_without_a_console(self):
        import time

        from now_playing.desktop import available_port

        with tempfile.TemporaryDirectory() as folder:
            service = DesktopService(Path(folder))
            try:
                service.start(demo=True, port=available_port())
                process = service.process
                for _ in range(100):
                    self.assertTrue(service.running, service.failure_message())
                    try:
                        self.assertEqual(service.snapshot()["status"], "idle")
                        break
                    except OSError:
                        time.sleep(0.05)
                else:
                    self.fail("Desktop backend did not start")
            finally:
                service.stop()
            self.assertEqual(process.exitcode, 0)

    def test_startup_failure_does_not_leave_parent_monitor_blocked(self):
        import socket

        with tempfile.TemporaryDirectory() as folder, socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            service = DesktopService(Path(folder))
            try:
                service.start(demo=True, port=occupied.getsockname()[1])
                process = service.process
                process.join(timeout=8)
                self.assertFalse(process.is_alive(), "Startup failure left a blocked monitor")
                self.assertNotEqual(process.exitcode, 0)
            finally:
                service.stop()
