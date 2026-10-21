import signal
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from now_playing.devices import select_microphone
from now_playing.platforms import shutdown_signals, user_data_directory


class PlatformTests(unittest.TestCase):
    def test_windows_shutdown_falls_back_and_restores_handlers(self):
        loop = Mock()
        loop.add_signal_handler.side_effect = NotImplementedError
        loop.call_soon_threadsafe.side_effect = lambda callback: callback()
        stop = Mock()
        previous = object()
        with (
            patch("now_playing.platforms.signal.getsignal", return_value=previous),
            patch("now_playing.platforms.signal.signal") as install,
        ):
            with shutdown_signals(loop, stop):
                handler = install.call_args_list[0].args[1]
                handler(signal.SIGINT, None)
                stop.set.assert_called_once()
            self.assertEqual(install.call_args_list[-1].args[1], previous)

    def test_unix_shutdown_removes_async_handlers(self):
        loop, stop = Mock(), Mock()
        with shutdown_signals(loop, stop):
            loop.add_signal_handler.call_args_list[0].args[1]()
            stop.set.assert_called_once()
        self.assertEqual(loop.remove_signal_handler.call_count, 2)

    def test_user_directories_follow_platform_conventions(self):
        home = Path("/users/test")
        self.assertEqual(
            user_data_directory("win32", {"LOCALAPPDATA": "/local"}, home),
            Path("/local/NowPlaying"),
        )
        self.assertEqual(
            user_data_directory("darwin", {}, home), home / "Library/Application Support/NowPlaying"
        )
        self.assertEqual(
            user_data_directory("linux", {"XDG_DATA_HOME": "/xdg"}, home), Path("/xdg/now-playing")
        )

    def test_unix_device_default_is_not_replaced_by_mac_policy(self):
        devices = [
            {"name": "MacBook Microphone", "max_input_channels": 1, "default_samplerate": 48000},
            {"name": "USB Input", "max_input_channels": 1, "default_samplerate": 16000},
        ]
        self.assertEqual(select_microphone(devices, 1, platform="linux"), (1, 16000))
        self.assertEqual(select_microphone(devices, 1, platform="darwin"), (0, 48000))
