# Troubleshooting

Keep the terminal open and read the first error above “Setup failed.” Correct the problem and rerun your normal start command. Partial dependency installs are retried; existing settings and albums are preserved.

## Python or dependency installation

Use Python 3.12 64-bit (3.11 also supported). On Windows, install the Python launcher and verify `py -3.12 --version`. On macOS/Linux, verify `python3.12 --version` or `python3.11 --version`. The launcher intentionally avoids Python 3.13+ because the live dependency stack is not validated there.

If pip says no matching distribution, check the platform table in the README: Intel macOS, Windows ARM, and 32-bit operating systems are not supported for live mode. Windows may need the [Microsoft Visual C++ x64 redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).

On Debian/Ubuntu/Pi OS, “PortAudio library not found” needs `sudo apt install libportaudio2`. A missing `venv`/`ensurepip` needs the venv package for your Python version (for example `python3.11-venv`). On macOS and Windows, pip's sounddevice package includes PortAudio.

If the private environment was moved or its Python was uninstalled, stop the app, delete only `.venv/` and `.now-playing/`, then start again. Keep `data/`, `models/`, and your config. To force dependency reinstallation without deleting the environment, delete `.now-playing/setup.json`.

## Microphone permission or wrong input

macOS: System Settings → Privacy & Security → Microphone; allow the terminal application used to launch the app, then restart that terminal. Windows: Settings → Privacy & security → Microphone; enable access for desktop apps. Linux: check the desktop input source and recording permission.

List devices with `sh start.sh --list-devices` (Windows: `.\start.cmd --list-devices`). Choose one with `--device "exact device name"`. Omit `capture_rate` from your config to use its native rate. Test the microphone with your OS sound recorder and confirm its input meter moves. A quiet room is valid and does not cause startup to fail.

## Display stays on Listening

Check that you launched without `--demo`. Allow model startup and 10–30 seconds of clear music. Move the microphone closer, turn up the input level, or select a different microphone. Recognition depends on an external service and may fail for obscure tracks, live performances, or noisy recordings. The activity indicator distinguishes hearing music from identifying it. Exceptions and model restart attempts are printed in the terminal.

If `Cannot load YAMNet` appears, stop, rename the `models/yamnet` directory to keep a backup, and start again. Setup downloads a fresh model. Check internet connectivity and available storage. A proxy/certificate error must be fixed at the network or Python certificate configuration; TLS verification is not disabled by this app.

## Blank browser, occupied port, or old song

Open the exact URL printed in the terminal. Use `--port 8082` if another process occupies 8080; don't stop unrelated processes. Refresh the browser after source updates. Recognition is asynchronous: old songs remain during refresh and clear after silence/expiry. The mosaic is empty until at least one album cover has downloaded; new covers require internet access.

The server binds to localhost by default. A browser on another computer cannot access that address. If intentionally configuring LAN access, choose a suitable host/interface and firewall rule; the built-in server has no login and is intended for a trusted local display.

## Stop, back up, reset

Ctrl+C in the launching terminal stops the server and model worker. Stop before copying the whole `data/` directory to back up the collection. Delete `data/` only if you want to forget all albums. Removing `.venv/` alone does not remove your history. Deleting the project folder removes the source launcher's local state too.
