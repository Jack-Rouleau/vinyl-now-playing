"""Small native control window for the self-contained desktop distribution."""

from __future__ import annotations

import json
import socket
import sys
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .desktop_service import DesktopService


def input_choices() -> dict[str, int | None]:
    import sounddevice as sd

    apis = sd.query_hostapis()
    choices = {"Use Windows default microphone": None}
    for index, device in enumerate(sd.query_devices()):
        if device["max_input_channels"]:
            label = f"{device['name']} ({apis[device['hostapi']]['name']})"
            if label in choices:
                label += f" [{index}]"
            choices[label] = index
    return choices


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class DesktopWindow:
    def __init__(self, root, *, smoke: bool = False):
        import tkinter as tk
        from tkinter import ttk

        self.root = root
        self.service = DesktopService()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.pending = None
        self.snapshot_future = None
        self.closing = False
        self.opened = False
        self.started_at = 0
        self.inputs = {"Use Windows default microphone": None}
        root.title("Now Playing")
        root.geometry("540x340")
        root.resizable(False, False)
        outer = ttk.Frame(root, padding=24)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Now Playing", font=("Segoe UI", 20)).pack(anchor="w")
        ttk.Label(
            outer,
            text="Play music near your microphone. Your display opens in the browser.",
            wraplength=485,
        ).pack(anchor="w", pady=(8, 18))
        self.status = tk.StringVar(value="Starting…")
        ttk.Label(outer, textvariable=self.status, wraplength=485).pack(anchor="w", pady=(0, 16))
        ttk.Label(outer, text="Microphone").pack(anchor="w")
        self.selected = tk.StringVar(value=next(iter(self.inputs)))
        self.microphone = ttk.Combobox(
            outer, textvariable=self.selected, state="readonly", width=63
        )
        self.microphone["values"] = list(self.inputs)
        self.microphone.pack(fill="x", pady=(4, 16))
        self.microphone.bind("<<ComboboxSelected>>", lambda _: self.restart())
        buttons = ttk.Frame(outer)
        buttons.pack(fill="x")
        self.toggle = ttk.Button(buttons, text="Stop", command=self.toggle_listener)
        self.toggle.pack(side="left")
        self.display = ttk.Button(
            buttons, text="Open display", command=self.open_display, state="disabled"
        )
        self.display.pack(side="left", padx=8)
        ttk.Button(buttons, text="Microphone settings", command=self.open_permissions).pack(
            side="right"
        )
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.preferences = self.service.profile / "desktop.json"
        if smoke:
            root.after(100, root.destroy)
            self.executor.shutdown(wait=False)
            return
        self.pending = self.executor.submit(input_choices)
        self.action = "inputs"
        root.after(100, self.poll)

    def set_busy(self, text):
        self.status.set(text)
        self.toggle.configure(state="disabled")
        self.microphone.configure(state="disabled")
        self.display.configure(state="disabled")

    def restart(self):
        if self.pending:
            return
        self.set_busy("Starting the music detector… This may take a minute.")
        self.opened = False
        self.started_at = time.monotonic()
        label = self.selected.get()

        def start():
            self.service.stop()
            self.service.profile.mkdir(parents=True, exist_ok=True)
            self.preferences.write_text(json.dumps({"microphone": label}), encoding="utf-8")
            self.service.start(self.inputs.get(label), port=available_port())

        self.pending = self.executor.submit(start)
        self.action = "start"

    def toggle_listener(self):
        if self.pending:
            return
        if self.service.running:
            self.set_busy("Stopping…")
            self.pending = self.executor.submit(self.service.stop)
            self.action = "stop"
        else:
            self.restart()

    def open_display(self):
        self.executor.submit(webbrowser.open, self.service.url)

    def open_permissions(self):
        if sys.platform == "win32":
            import os

            os.startfile("ms-settings:privacy-microphone")
        else:
            from tkinter import messagebox

            messagebox.showinfo(
                "Microphone access", "Allow microphone access in your system privacy settings."
            )

    def poll(self):
        if self.closing:
            return
        from tkinter import messagebox

        if self.pending and self.pending.done():
            pending, self.pending = self.pending, None
            try:
                result = pending.result()
                if self.action == "inputs":
                    self.inputs = result
                    self.microphone["values"] = list(result)
                    try:
                        saved = json.loads(self.preferences.read_text(encoding="utf-8")).get(
                            "microphone"
                        )
                        if saved in self.inputs:
                            self.selected.set(saved)
                    except (OSError, ValueError):
                        pass
                    self.restart()
                elif self.action == "stop":
                    self.status.set("Stopped. Click Start to listen again.")
                    self.toggle.configure(text="Start", state="normal")
                    self.microphone.configure(state="readonly")
                else:
                    self.toggle.configure(text="Stop", state="normal")
                    self.microphone.configure(state="readonly")
            except Exception as error:
                self.status.set("Could not start. Check your microphone and try again.")
                self.toggle.configure(text="Start", state="normal")
                self.microphone.configure(state="readonly")
                messagebox.showerror("Now Playing", str(error))
        if self.service.process is not None and not self.service.running and not self.pending:
            self.status.set("The listener stopped. Check microphone access, then click Start.")
            self.toggle.configure(text="Start", state="normal")
            self.display.configure(state="disabled")
            details = self.service.failure_message()
            self.service.stop()
            messagebox.showerror("Could not start listening", details)
        if self.snapshot_future and self.snapshot_future.done():
            future, self.snapshot_future = self.snapshot_future, None
            try:
                snapshot = future.result()
                labels = {
                    "listening": "Listening for music",
                    "music_detected": "Music detected",
                    "identifying": "Identifying song…",
                }
                activity = snapshot.get("activity")
                if activity == "paused":
                    text = (
                        "Starting the music detector…"
                        if time.monotonic() - self.started_at < 30
                        else "Still starting or waiting for microphone. Check microphone access if this continues."
                    )
                else:
                    text = labels.get(activity, "Listening for music")
                if self.service.running and not self.pending:
                    self.status.set(text)
                    self.display.configure(state="normal")
                    if not self.opened:
                        self.opened = True
                        self.open_display()
            except Exception:
                pass
        if self.service.running and not self.pending and not self.snapshot_future:
            self.snapshot_future = self.executor.submit(self.service.snapshot)
        if not self.closing:
            self.root.after(500, self.poll)

    def close(self):
        self.closing = True
        self.set_busy("Closing…")
        closing = self.executor.submit(self.service.stop)

        def finish():
            if closing.done():
                self.executor.shutdown(wait=False)
                self.root.destroy()
            else:
                self.root.after(100, finish)

        finish()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in args:
        from .desktop_smoke import self_test

        destination = Path(args[args.index("--self-test") + 1])
        return self_test(destination)
    import tkinter as tk

    mutex = None
    if sys.platform == "win32":
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.restype = ctypes.c_void_p
        mutex = kernel.CreateMutexW(None, False, "Local\\VinylNowPlayingDesktop")
        if ctypes.get_last_error() == 183:
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(
                "Now Playing", "Now Playing is already open. Find its window on your taskbar."
            )
            root.destroy()
            return 0
    root = tk.Tk()
    DesktopWindow(root, smoke="--gui-smoke" in args)
    root.mainloop()
    if mutex:
        kernel.CloseHandle(ctypes.c_void_p(mutex))
    return 0


if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()
    raise SystemExit(main())
