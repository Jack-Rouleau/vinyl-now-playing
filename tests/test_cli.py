import os
import subprocess
import sys
import unittest
from pathlib import Path


class CLITests(unittest.TestCase):
    def command(self, *args):
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
        return subprocess.run(
            [sys.executable, "-S", *args], env=env, capture_output=True, text=True, timeout=5
        )

    def test_demo_core_requires_no_site_packages(self):
        result = self.command(
            "-c",
            'import sys; from now_playing.demo import Demo; from now_playing.server import response_for; assert Demo(fixed="matched").snapshot().track; assert response_for("/", Demo().snapshot)[0] == 200; assert not any(p in sys.modules for p in ("numpy", "tensorflow", "sounddevice", "shazamio"))',
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fixed_state_requires_demo(self):
        result = self.command("-m", "now_playing", "--demo-state", "matched")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--demo-state requires --demo", result.stderr)

    def test_help_without_live_dependencies(self):
        result = self.command("-m", "now_playing", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--list-devices", result.stdout)
