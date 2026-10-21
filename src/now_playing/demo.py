"""Local, synthetic display fixtures. No third-party imports or network."""

import time

from .models import DisplayState, Track


class Demo:
    def __init__(self, fixed: str | None = None, clock=time.monotonic):
        self.fixed = fixed
        self.clock = clock
        self.started = clock()

    def snapshot(self) -> DisplayState:
        elapsed = int(self.clock() - self.started)
        step = elapsed // 4
        states = (
            "idle",
            "identifying",
            "matched",
            "matched",
            "matched",
            "matched",
            "unavailable",
            "idle",
        )
        status = self.fixed or states[step % len(states)]
        second = not self.fixed and step % len(states) >= 4
        track = (
            Track(
                "demo-2" if second else "demo-1",
                "A slower kind of Sunday" if second else "Between the quiet moments",
                "The Evening Hours" if second else "The Low Light Ensemble",
                "Windows open, volume up" if second else "Notes from another room",
                "/demo-artwork.svg",
            )
            if status == "matched"
            else None
        )
        return DisplayState(
            status,
            track,
            step if not self.fixed else 0,
            {
                "idle": "listening",
                "identifying": "identifying",
                "matched": "music_detected",
                "unavailable": "paused",
            }[status],
        )
