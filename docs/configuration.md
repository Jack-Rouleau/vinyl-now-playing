# Configuration

The source launcher creates `config.toml` once. Edit it in a text editor, save, then restart. `config.example.toml` lists every setting. Unknown keys and invalid values cause a startup error rather than being silently ignored.

Relative `model_path` and `state_dir` are resolved beside the selected config file, regardless of your terminal's current folder. `--config` must point to an existing file. The launcher does not rewrite that file. Back up your settings and `data/` before moving the project.

| Setting | Generated launcher value | Meaning |
| --- | --- | --- |
| `host` | `"127.0.0.1"` | Listen on this computer; `"0.0.0.0"` exposes the display to your LAN |
| `port` | `8080` | HTTP port, 1–65535 |
| `device` | omitted | System input; macOS prefers its built-in mic when available. Name or integer index |
| `capture_rate` | omitted | Use the chosen device's native rate. Specify only if needed |
| `channels` | `1` | Input channels; mixed to mono |
| `model_path` | `"models/yamnet"` | Local YAMNet SavedModel directory |
| `state_dir` | `"data"` | Album database and artwork directory |
| `music_threshold` | `0.1` | Local music score threshold, 0–1. Raise to reject more background sound |
| `silence_db` | `-50.0` | Audio below this level bypasses model inference |
| `positive_windows` | `2` | Consecutive music-positive classifications before recognition |
| `sample_seconds` | `10` | Rolling audio duration sent to the recognizer |
| `attempt_interval` | `10` | Minimum seconds between recognition attempts |
| `silence_seconds` | `30` | Sustained nonmusic before returning to the mosaic |
| `track_expiry` | `90` | Maximum seconds without a successful refresh before clearing the song |
| `request_timeout` | `15` | Recognition request deadline |
| `max_backoff` | `120` | Maximum retry spacing after failures; at least attempt_interval |
| `inference_timeout` | `10` | Deadline for one model inference |
| `model_startup_timeout` | `120` | Deadline for initial model load |

A package-only invocation (`now-playing` without `--config`) uses conservative defaults: music_threshold 0.5, attempt_interval 20. Its model and data live under the OS application-data folder (macOS `~/Library/Application Support/NowPlaying`, Windows `%LOCALAPPDATA%\NowPlaying`, Linux `$XDG_DATA_HOME/now-playing` or `~/.local/share/now-playing`). It does not automatically install the model: run `now-playing --setup-model` first. The source launcher is the recommended beginner entry point.

Use `--device`, `--port`, and `--no-browser` for temporary overrides. Avoid device indexes in permanent settings if you frequently plug/unplug devices; names are more stable. Ambiguous names produce an error.

Recognition runs separately from classification. A song stays visible during refresh, and results arriving after a deadline or a transition to silence are discarded. A ten-second interval does not promise a ten-second update: filling the audio window, detection, fingerprinting, service response, and one-second UI polling add latency.
