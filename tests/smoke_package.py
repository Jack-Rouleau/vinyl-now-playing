"""Build-output smoke test run in CI and from a clean local environment."""

import json
import socket
import subprocess
import sys
import time
from urllib.request import urlopen


def main():
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        port = candidate.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "now_playing", "--demo", "--demo-state", "idle", "--port", str(port)]
    )
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("Demo exited before it was ready")
            try:
                with urlopen(f"http://127.0.0.1:{port}/api/state", timeout=1) as response:
                    assert json.load(response)["status"] == "idle"
                with urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                    assert b"<html" in response.read()
                print("Installed wheel serves the demo and bundled UI.")
                return
            except OSError:
                time.sleep(0.1)
        raise TimeoutError("Demo did not become ready")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    main()
