"""Platform-aware microphone selection, separate from PortAudio capture."""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from typing import Any


def select_microphone(
    devices: Sequence[Mapping[str, Any]],
    default_input: int,
    requested: str | None = None,
    *,
    platform: str | None = None,
) -> tuple[int, int]:
    inputs = [
        (index, device) for index, device in enumerate(devices) if device["max_input_channels"] > 0
    ]
    if requested is not None:
        if requested.isdecimal():
            matches = [(index, device) for index, device in inputs if index == int(requested)]
        else:
            matches = [
                (index, device)
                for index, device in inputs
                if device["name"].casefold() == requested.casefold()
            ]
            if not matches:
                matches = [
                    (index, device)
                    for index, device in inputs
                    if requested.casefold() in device["name"].casefold()
                ]
        if len(matches) != 1:
            raise RuntimeError(
                "Microphone selection must match one input. Run --list-devices and select its numeric index."
            )
        selected = matches[0]
    else:
        selected = None
        if (platform or sys.platform) == "darwin":
            selected = next(
                (
                    (index, device)
                    for index, device in inputs
                    if "microphone" in device["name"].casefold()
                    and (
                        "macbook" in device["name"].casefold()
                        or "built-in" in device["name"].casefold()
                    )
                ),
                None,
            )
        if selected is None:
            selected = next(
                ((index, device) for index, device in inputs if index == default_input), None
            )
        if selected is None:
            raise RuntimeError(
                "No default microphone found. Connect a microphone and run --list-devices."
            )
    index, device = selected
    return index, int(device["default_samplerate"])
