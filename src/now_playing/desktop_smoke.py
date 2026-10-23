"""Exercise a frozen desktop build on its actual target OS, without a microphone."""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
import traceback
from pathlib import Path


def self_test(destination: Path) -> int:
    results = []
    try:
        import tkinter as tk

        from .desktop import DesktopWindow, available_port

        root = tk.Tk()
        DesktopWindow(root, smoke=True)
        root.mainloop()
        results.append("Native window opens and closes")

        import sounddevice as sd

        sd.query_devices()  # A runner may legitimately have zero microphone devices.
        results.append("Bundled PortAudio loads")

        import numpy as np

        from .desktop_service import DesktopService, bundle_root, desktop_config
        from .detector_process import ProcessDetector
        from .model_setup import model_is_ready
        from .recognizer import Recognizer, wav_bytes

        with tempfile.TemporaryDirectory(prefix="Now Playing smoke ") as folder:
            profile = Path(folder)
            config = desktop_config(bundle_root(), profile)
            assert model_is_ready(Path(config.model_path)), "Bundled model missing"

            async def inference():
                async with ProcessDetector(config) as detector:
                    assert not await detector.classify(np.zeros(16000, dtype=np.float32))
                async with Recognizer() as recognizer:
                    samples = (
                        np.sin(np.arange(160000, dtype=np.float32) * (440 * 2 * np.pi / 16000))
                        * 0.3
                    )
                    signature = await recognizer.provider.core_recognizer.recognize_bytes(
                        value=wav_bytes(samples, 16000)
                    )
                    assert signature is not None

            asyncio.run(inference())
            results.append("Spawned bundled TensorFlow loads model and classifies silence")
            results.append(
                "Bundled ShazamIO Rust fingerprints in-memory WAV without external decoder"
            )
            service = DesktopService(profile)
            port = available_port()
            try:
                service.start(demo=True, port=port)
                process = service.process
                for _ in range(200):
                    if not service.running:
                        raise RuntimeError(service.failure_message())
                    try:
                        assert service.snapshot()["status"] == "idle"
                        break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise TimeoutError("Frozen server did not become ready")
                from urllib.request import urlopen

                for path, fragment in (
                    ("/", b"<html"),
                    ("/app.js", b"fetch"),
                    ("/api/albums", b"demo-cover"),
                    ("/demo-artwork.svg", b"<svg"),
                ):
                    with urlopen(service.url + path, timeout=3) as response:
                        assert fragment in response.read(), path
                results.append("Frozen child serves bundled display and album assets")
            finally:
                service.stop()
            assert process.exitcode == 0, f"Worker did not stop gracefully: {process.exitcode}"
            results.append("Window controller stops backend cleanly without console signals")
        destination.write_text(
            json.dumps({"passed": True, "checks": results}, indent=2), encoding="utf-8"
        )
        return 0
    except BaseException:
        destination.write_text(
            json.dumps(
                {"passed": False, "checks": results, "error": traceback.format_exc()}, indent=2
            ),
            encoding="utf-8",
        )
        return 1
