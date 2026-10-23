# Development

Use Python 3.11 or 3.12. From the project directory:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m unittest discover -s tests
node tests/test_display.cjs
node tests/test_mosaic.cjs
node tests/test_mosaic_refresh.cjs
.venv/bin/python -m build
```

Windows equivalents use `py -3.12 -m venv .venv` and `.venv\Scripts\python.exe` / `.venv\Scripts\ruff.exe`. Node 20+ is needed only for frontend tests. Install `.[live]` separately to exercise actual audio and TensorFlow. The real-model test skips when the model/dependencies are absent.

For browser tests, install Playwright in a separate tooling directory or use `npm install --no-save --package-lock=false playwright`, then `npx playwright install chromium`. Start the demo on port 8081 with `sh start.sh --demo --demo-state idle --port 8081 --no-browser`. In another terminal:

```sh
mkdir -p output/playwright
node tests/browser_mosaic.cjs
```

`NOW_PLAYING_TEST_URL` overrides the server URL, `PLAYWRIGHT_MODULE` selects a Playwright module path, and `BROWSER_CHANNEL=chrome` selects an installed Chrome. Browser checks cover landscape/portrait bounds, shifting/paused/reduced-motion mosaics, and cover loading recovery. They write ignored screenshots under `output/`.

CI checks core/test dependencies on Windows, macOS, and Ubuntu with both Python versions; it builds distributions and smoke-tests the installed wheel's demo in a clean environment. A separate Linux job runs browser regressions. It does not install the full live stack or claim physical microphone/recognition validation on those hosts.

`config.toml`, generated settings, models, album data, private environments, logs, and screenshots are ignored by Git. Source archives explicitly include public docs and launchers, excluding session notes and local state. Inspect `git status` and distribution contents before release. No remote or publishing credentials are needed for local checks.

Choose a project license before public distribution; none has been assigned automatically. Review third-party package/model licenses separately. Dependencies have bounded compatibility ranges rather than a platform-specific lock; test live installation on each target before publishing a supported release.

## Windows desktop installer

The manually dispatched **Windows app** workflow builds a per-user Windows x64 installer on an actual Windows runner. It installs the live dependency set and PyInstaller, downloads YAMNet into build assets, freezes `packaging/desktop_entry.py` with `packaging/windows.spec`, runs the frozen smoke, compiles `packaging/windows.iss` with Inno Setup, installs it into a path containing spaces, and repeats the smoke on the installed executable. The installer artifact is `Now-Playing-Windows-Setup.exe`. Download and supply that file to users; the repository ZIP requires developer tooling.

The frozen smoke checks native Tk, PortAudio loading (no physical input required), spawned TensorFlow model loading and non-silent inference, Rust fingerprinting of WAV bytes, bundled web/album assets, and clean GUI-controller backend shutdown. Actual microphone capture, Windows privacy permissions, and live provider results still need a physical Windows test. The build is unsigned; signing requires a separate signing identity. Packaging is platform-specific; the Windows build does not produce macOS/Linux applications.

The desktop controller uses a multiprocessing pipe rather than console signals or standard input, which windowed frozen applications do not provide. Its backend is non-daemonic because it spawns the inference worker. The parent polls the pipe asynchronously, so startup errors do not leave a blocked shutdown thread. Closing the app requests graceful cleanup, with a bounded fallback restricted to that backend process tree. Runtime assets are read-only inside the installed bundle; history/preferences/logs live under the user-data directory. Source mode remains available unchanged.
