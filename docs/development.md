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
