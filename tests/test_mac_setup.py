import unittest

from now_playing.mac_setup import microphone_settings


class MacSetupTests(unittest.TestCase):
    def test_prefers_macbook_microphone_over_default_virtual_device(self):
        devices = [
            {"name": "Virtual Audio", "max_input_channels": 2, "default_samplerate": 44100},
            {
                "name": "MacBook Pro Microphone",
                "max_input_channels": 1,
                "default_samplerate": 48000,
            },
            {"name": "MacBook Pro Speakers", "max_input_channels": 0, "default_samplerate": 48000},
        ]
        self.assertEqual(microphone_settings(devices, 0), (1, 48000))

    def test_falls_back_to_default_input(self):
        self.assertEqual(
            microphone_settings(
                [{"name": "USB Mic", "max_input_channels": 2, "default_samplerate": 44100}], 0
            ),
            (0, 44100),
        )

    def test_explicit_selection(self):
        devices = [{"name": "USB Mic", "max_input_channels": 1, "default_samplerate": 44100}]
        self.assertEqual(microphone_settings(devices, -1, "USB Mic"), (0, 44100))
        self.assertEqual(microphone_settings(devices, -1, "0"), (0, 44100))

    def test_no_input_device_gives_actionable_error(self):
        with self.assertRaisesRegex(RuntimeError, "microphone"):
            microphone_settings([], -1)
