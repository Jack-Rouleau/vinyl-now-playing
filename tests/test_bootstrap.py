import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bootstrap


class BootstrapTests(unittest.TestCase):
    def test_venv_paths(self):
        self.assertEqual(
            bootstrap.venv_python(Path("env"), "win32"), Path("env/Scripts/python.exe")
        )
        self.assertEqual(bootstrap.venv_python(Path("env"), "linux"), Path("env/bin/python"))

    def test_configuration_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.toml"
            bootstrap.ensure_config(path)
            self.assertIn("attempt_interval = 10", path.read_text())
            path.write_text("port = 9999\n")
            bootstrap.ensure_config(path)
            self.assertEqual(path.read_text(), "port = 9999\n")

    def test_live_install_satisfies_demo_and_failed_upgrade_is_not_stamped(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "pyproject.toml").write_text('version = "1"')
            python = bootstrap.venv_python(root / ".venv")
            python.parent.mkdir(parents=True)
            python.touch()
            with patch("bootstrap.checked") as install:
                bootstrap.prepare_environment(root, live=False)
                self.assertEqual(install.call_count, 1)
                install.side_effect = RuntimeError("network down")
                with self.assertRaises(RuntimeError):
                    bootstrap.prepare_environment(root, live=True)
                install.side_effect = None
                bootstrap.prepare_environment(root, live=True)
                self.assertEqual(install.call_count, 3)
                bootstrap.prepare_environment(root, live=False)
                bootstrap.prepare_environment(root, live=True)
                self.assertEqual(install.call_count, 3)

    def test_recreated_environment_does_not_trust_old_stamp(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "pyproject.toml").write_text('version = "1"')
            python = bootstrap.venv_python(root / ".venv")
            python.parent.mkdir(parents=True)
            python.touch()
            with patch("bootstrap.checked") as install:
                bootstrap.prepare_environment(root, live=False)
                python.unlink()
                with patch("bootstrap.venv.EnvBuilder") as builder:
                    builder.return_value.create.side_effect = lambda _: python.touch()
                    bootstrap.prepare_environment(root, live=False)
                self.assertEqual(install.call_count, 2)
