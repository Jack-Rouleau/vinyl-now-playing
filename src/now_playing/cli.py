"""Parse user commands and delegate to application services."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import replace
from pathlib import Path

from .application import RunOptions, run_application
from .config import Config, load_config


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Listen for music and show the song and your album mosaic."
    )
    command.add_argument(
        "--config", type=Path, help="TOML settings file; relative paths resolve beside this file"
    )
    command.add_argument(
        "--demo", action="store_true", help="preview only: no microphone or recognition"
    )
    command.add_argument("--demo-state", choices=("idle", "identifying", "matched", "unavailable"))
    command.add_argument(
        "--list-devices",
        action="store_true",
        help="list microphone inputs without loading the model",
    )
    command.add_argument("--device", help="microphone index or unique name")
    command.add_argument("--port", type=int, help="display server port (default 8080)")
    command.add_argument(
        "--setup-model", action="store_true", help="download/validate the model, then exit"
    )
    browser = command.add_mutually_exclusive_group()
    browser.add_argument(
        "--open",
        dest="open_browser",
        action="store_true",
        help="open the display in your default browser",
    )
    browser.add_argument(
        "--no-browser",
        dest="open_browser",
        action="store_false",
        help="leave browser startup to you",
    )
    command.set_defaults(open_browser=False)
    return command


def configure_input(config: Config, requested: str | None) -> Config:
    import sounddevice as sd

    from .devices import select_microphone

    device = (
        requested
        if requested is not None
        else str(config.device)
        if config.device is not None
        else None
    )
    index, rate = select_microphone(sd.query_devices(), int(sd.default.device[0]), device)
    logging.info("Microphone: %s", sd.query_devices(index)["name"])
    return replace(config, device=index, capture_rate=config.capture_rate or rate)


def main(argv: list[str] | None = None) -> int:
    command = parser()
    args = command.parse_args(argv)
    if args.demo_state and not args.demo:
        command.error("--demo-state requires --demo")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        config = load_config(args.config)
        if args.port is not None:
            config = replace(config, port=args.port)
        if args.list_devices:
            from .audio import list_devices

            print(json.dumps(list_devices(), indent=2))
            return 0
        if args.setup_model:
            from .model_setup import ensure_model

            print(f"Model ready: {ensure_model(Path(config.model_path))}")
            return 0
        if not args.demo:
            config = configure_input(config, args.device)
        asyncio.run(
            run_application(config, RunOptions(args.demo, args.demo_state, args.open_browser))
        )
        return 0
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError, RuntimeError, ImportError) as error:
        message = str(error)
        if isinstance(error, OSError) and error.errno in (48, 98, 10048):
            message = f"Port {config.port} is already in use. Close the other instance or choose --port 8082."
        command.exit(
            1,
            f"Error: {message}\nSee README.md or docs/troubleshooting.md for setup and microphone help.\n",
        )
