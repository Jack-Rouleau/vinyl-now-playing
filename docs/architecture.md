# Architecture

`run.py` delegates installation to the standard-library `bootstrap.py`. Thin OS launchers locate a supported Python. The bootstrap owns the private environment, setup fingerprint, missing configuration, and model preparation; it delegates runtime to the installed package. It never imports the ML stack itself.

`cli.py` validates commands and input selection. `application.py` composes the server, engine, persistence, and live pipeline and owns their lifetimes. `platforms.py` isolates application-data paths and portable shutdown handlers. `devices.py` contains microphone selection policy.

`engine.py` is a deterministic state machine with an injected clock. It owns music gating, recognition attempt tokens, expiry, cooldown, and retry backoff. It has no audio, TensorFlow, HTTP, or SQLite dependency. Structural protocols in `contracts.py` describe classifier, recognizer, and archive boundaries.

`audio.py` bounds callback buffering, mixes/resamples to 16 kHz mono, and builds rolling windows. `detector.py` loads the local YAMNet SavedModel. `detector_process.py` supervises a spawned inference worker so a hung model can be terminated. `runtime.py` coordinates classification and independent timed recognition. `recognizer.py` fingerprints WAV bytes in memory through ShazamIO and maps results to immutable `Track` data.

`artwork.py` owns artwork URL/identity policy. `image_formats.py` validates bounded image headers/dimensions. `album_cache.py` downloads covers in a bounded background workflow and activates cached files atomically. `albums.py` owns SQLite persistence and album snapshots. Only accepted recognition results enter the archive.

`server.py` exposes read-only `/api/state`, `/api/albums`, known `/artwork/<id>` files, and bundled static assets. The browser polls state once per second. `mosaic.js` maintains bounded tiles and a fair queue of album covers, pauses hidden animation, respects reduced motion, and refreshes the collection on every return to idle. Stale fetch responses cannot replace a newer collection.

`model_setup.py` downloads the official model to a temporary directory, restricts archive members and sizes, validates required files, and activates the staged directory only after validation. A complete existing installation is reused. Model structural validation is not a cryptographic integrity guarantee.

Demo mode uses the same server/UI with synthetic state and sample artwork. It imports no microphone, NumPy, TensorFlow, or recognition packages. Tests exercise the engine with fake clocks, boundaries with injected collaborators, model extraction with local archives, HTTP behavior, and frontend lifecycle in Node and a real browser.

The packaged Windows entry calls `freeze_support` before importing the desktop UI. `desktop.py` owns a Tk control window; `desktop_service.py` owns the independently spawned backend and its stop pipe. The same `run_application` composition accepts an optional stop event, preserving CLI signals while supporting a console-free app. `desktop_smoke.py` validates the actual frozen bundle on Windows. PyInstaller and Inno Setup run only at build time; users receive the complete installer.
