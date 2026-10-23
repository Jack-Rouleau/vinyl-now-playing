"""Desktop lifecycle independent of window toolkit and console signal support."""

from __future__ import annotations

import asyncio
import json
import logging
import multiprocessing
import subprocess
import sys
from dataclasses import replace
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.request import urlopen

from .config import Config
from .platforms import user_data_directory


def bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def desktop_config(bundle: Path, profile: Path) -> Config:
    return replace(
        Config(),
        model_path=str(bundle / "models/yamnet"),
        state_dir=str(profile / "data"),
        music_threshold=0.1,
        attempt_interval=10,
    )


async def stop_from_parent(stop: asyncio.Event, connection) -> None:
    try:
        while not connection.poll():
            await asyncio.sleep(0.1)
        connection.recv()
    except (EOFError, OSError):
        pass
    finally:
        stop.set()


def worker_main(connection, config: Config, profile: Path, demo: bool = False) -> None:
    from .application import RunOptions, run_application
    from .cli import configure_input

    profile.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        profile / "listener.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8"
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[handler],
        force=True,
    )
    try:
        if not demo:
            config = configure_input(
                config, str(config.device) if config.device is not None else None
            )

        async def run():
            stop = asyncio.Event()
            monitor = asyncio.create_task(stop_from_parent(stop, connection))
            try:
                await run_application(
                    config, RunOptions(demo=demo, demo_state="idle" if demo else None), stop=stop
                )
            finally:
                # The monitor polls asynchronously, so startup failures never leave a blocked thread.
                connection.close()
                monitor.cancel()
                await asyncio.gather(monitor, return_exceptions=True)

        asyncio.run(run())
    except Exception:
        logging.exception("Listener could not start")
        raise
    finally:
        connection.close()
        handler.close()


class DesktopService:
    def __init__(self, profile: Path | None = None):
        self.profile = profile or user_data_directory()
        self.config = desktop_config(bundle_root(), self.profile)
        self.process = None
        self.connection = None

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.is_alive()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.config.port}"

    def start(self, device: int | None = None, *, demo: bool = False, port: int = 8080) -> None:
        if self.running:
            return
        self.stop()
        self.profile.mkdir(parents=True, exist_ok=True)
        self.config = replace(self.config, device=device, port=port)
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        self.connection = parent
        self.process = context.Process(
            target=worker_main, args=(child, self.config, self.profile, demo)
        )
        try:
            self.process.start()
        except BaseException:
            parent.close()
            self.process = self.connection = None
            raise
        finally:
            child.close()

    def snapshot(self) -> dict:
        with urlopen(self.url + "/api/state", timeout=0.3) as response:
            return json.load(response)

    def failure_message(self) -> str:
        try:
            log = (
                (self.profile / "listener.log")
                .read_text(encoding="utf-8", errors="replace")[-16000:]
                .lower()
            )
        except OSError:
            log = ""
        log = log.rsplit("listener could not start", 1)[-1]
        if "microphone access denied" in log:
            message = "Windows reported microphone access denied. Click Microphone settings and allow desktop apps to use your microphone, then click Start."
        elif any(word in log for word in ("microphone", "portaudio", "input device")):
            message = "The microphone is unavailable. Connect a microphone, select it in the app, and check Microphone settings. Then click Start."
        elif any(word in log for word in ("yamnet", "tensorflow", "model")):
            message = "The music detector could not start. Close and reopen Now Playing. If this continues, reinstall the app; your album history will be kept."
        elif "already in use" in log:
            message = "The display could not open. Close the app and open it again to retry."
        else:
            message = "Now Playing could not start. Close and reopen the app, then try again."
        return (
            message
            + "\n\nIf you need help, send the project owner this log file:\n"
            + str(self.profile / "listener.log")
        )

    def stop(self) -> None:
        if self.process is None:
            return
        try:
            if self.process.is_alive():
                try:
                    self.connection.send("stop")
                except (BrokenPipeError, EOFError, OSError):
                    pass
                self.process.join(timeout=8)
                if self.process.is_alive():
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                            capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                    else:
                        self.process.terminate()
                    self.process.join(timeout=3)
                    if self.process.is_alive():
                        self.process.kill()
                        self.process.join(timeout=2)
            else:
                self.process.join(timeout=0)
        finally:
            if self.connection:
                self.connection.close()
            self.process = self.connection = None
