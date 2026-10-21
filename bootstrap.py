"""Standard-library setup shared by all desktop launchers."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import venv
from pathlib import Path

DEFAULT_CONFIG = """# Paths resolve relative to this file. Omit device/capture_rate for automatic input.
host = "127.0.0.1"
port = 8080
model_path = "models/yamnet"
state_dir = "data"
music_threshold = 0.1
attempt_interval = 10
"""


def venv_python(folder: Path, platform: str | None = None) -> Path:
    return folder / (
        "Scripts/python.exe" if (platform or sys.platform) == "win32" else "bin/python"
    )


def checked(command: list[str], root: Path) -> None:
    result = subprocess.run(command, cwd=root)
    if result.returncode:
        raise RuntimeError(
            f"Command failed (exit {result.returncode}): {command[0]}. Check the message above, then run again."
        )


def ensure_config(path: Path) -> None:
    try:
        with path.open("x", encoding="utf-8") as target:
            target.write(DEFAULT_CONFIG)
    except FileExistsError:
        pass


def prepare_environment(root: Path, *, live: bool) -> Path:
    folder = root / ".venv"
    python = venv_python(folder)
    created = not python.exists()
    if created:
        print("Creating a private Python environment…", flush=True)
        venv.EnvBuilder(with_pip=True).create(folder)
    digest = hashlib.sha256((root / "pyproject.toml").read_bytes()).hexdigest()
    stamp = root / ".now-playing" / "setup.json"
    try:
        installed = json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        installed = {}
    if created or installed.get("fingerprint") != digest or (live and not installed.get("live")):
        print("Installing dependencies. First live setup can take several minutes…", flush=True)
        checked(
            [str(python), "-m", "pip", "install", "-e", str(root) + ("[live]" if live else "")],
            root,
        )
        stamp.parent.mkdir(exist_ok=True)
        temporary = stamp.with_suffix(".tmp")
        temporary.write_text(json.dumps({"fingerprint": digest, "live": live}), encoding="utf-8")
        temporary.replace(stamp)
    return python


def run_child(command: list[str], root: Path) -> int:
    child = subprocess.Popen(command, cwd=root)
    try:
        return child.wait()
    except KeyboardInterrupt:
        # Terminal Ctrl+C reaches both processes; let the application's cleanup finish.
        try:
            return child.wait(timeout=8)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            child.terminate()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            return 130


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parent
    if "--help" in args or "-h" in args:
        print("Usage: python run.py [--demo] [--setup-only] [--list-devices] [--device NAME]")
        print("                     [--config FILE] [--port PORT] [--no-browser]")
        print("First run installs dependencies and the music detector. Ctrl+C stops the app.")
        return 0
    if sys.version_info[:2] not in ((3, 11), (3, 12)):
        print(
            "Please install Python 3.12 (64-bit) from python.org, then run this launcher with it.",
            file=sys.stderr,
        )
        return 1
    setup_only = "--setup-only" in args
    args = [arg for arg in args if arg != "--setup-only"]
    live = "--demo" not in args
    try:
        # Resolve explicit settings before switching the child's working directory.
        config = root / "config.toml"
        for index, argument in enumerate(args):
            if argument == "--config":
                if index + 1 >= len(args):
                    raise ValueError("--config requires a file path")
                config = Path(args[index + 1]).expanduser().resolve()
                args[index + 1] = str(config)
                break
            if argument.startswith("--config="):
                config = Path(argument.split("=", 1)[1]).expanduser().resolve()
                args[index] = "--config=" + str(config)
                break
        else:
            ensure_config(config)
            args += ["--config", str(config)]
        if not config.is_file():
            raise ValueError(f"Configuration file does not exist: {config}")
        python = prepare_environment(root, live=live)
        if live and "--list-devices" not in args and "--setup-model" not in args:
            checked(
                [str(python), "-m", "now_playing", "--config", str(config), "--setup-model"], root
            )
        if setup_only:
            return 0
        if not any(
            flag in args for flag in ("--open", "--no-browser", "--list-devices", "--setup-model")
        ):
            args.append("--open")
        return run_child([str(python), "-m", "now_playing", *args], root)
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError) as error:
        print(
            f"Setup failed: {error}\nSee docs/troubleshooting.md, correct the problem, and run again.",
            file=sys.stderr,
        )
        return 1
