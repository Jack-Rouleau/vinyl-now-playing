# Now Playing

Listen to music through a microphone and show the song, artist, album, and cover on a standard HDMI display. Between songs, a shifting mosaic shows the albums previously identified. A small activity indicator shows when the app hears music or identifies a song.

No Spotify account, playlists, or special display hardware. Recognition uses Shazam through ShazamIO; music detection runs locally with YAMNet. An internet connection is needed for setup, identification, and new covers.

## Start here

1. Install **Python 3.12, 64-bit**, from [python.org](https://www.python.org/downloads/). Python 3.11 also works. On Windows, include the Python launcher (`py`) when installing.
2. Download and extract this project into a folder you can write to. Keep all its files together.
3. Connect a microphone and select it as the system input. Open a terminal in the extracted project folder and run the command for your computer:

| Computer | Command |
| --- | --- |
| macOS or Linux | `sh start.sh` |
| Windows, PowerShell | `.\start.cmd` |
| Windows, Command Prompt | `start.cmd` |

On macOS you can also open `start.command`; on Windows you can open `start.cmd`. If macOS blocks the downloaded script, use the terminal command above.

The first run creates a private `.venv`, installs dependencies, downloads the music detector, and creates `config.toml`. This can take several minutes and requires space for TensorFlow and its dependencies. Later runs reuse this setup. The launcher never installs system packages or requests administrator access.

Allow microphone access when asked. Your browser opens at **http://127.0.0.1:8080**. Allow model startup, then play music near the microphone. Identification usually needs 10–30 seconds of clear music and can take longer on slower hardware or networks. Use the browser's full-screen mode on your HDMI screen. Keep the terminal open; press **Ctrl+C** there to stop.

### Linux preparation

On Debian, Ubuntu, or Raspberry Pi OS, you may need these system packages first:

```sh
sudo apt update
sudo apt install python3-venv libportaudio2
```

You still need Python 3.11 or 3.12 selected by `start.sh`; a newer system Python is not selected automatically. Other Linux distributions use different package names. [Sounddevice documents PortAudio installation](https://python-sounddevice.readthedocs.io/en/latest/installation.html).

### Preview without a microphone

```sh
# macOS / Linux
sh start.sh --demo
```

```powershell
# Windows
.\start.cmd --demo
```

Demo mode uses fictional song data and a sample cover. It does **not** listen, identify songs, download the model, or install live dependencies. Use `--demo --demo-state idle` to preview the mosaic. Remove `--demo` to listen for real music.

## Everyday commands

Append these options to your platform's start command:

| Option | Purpose |
| --- | --- |
| `--list-devices` | List audio inputs without starting the detector |
| `--device "USB Microphone"` | Choose a microphone by unique name; a numeric index also works |
| `--port 8082` | Use another port if 8080 is occupied |
| `--no-browser` | Start without opening a browser |
| `--setup-only` | Install and prepare, then exit |
| `--config "path/to/settings.toml"` | Use your own settings file |

For example: `sh start.sh --device "USB Microphone" --port 8082`.

Edit the generated `config.toml` to keep your preferences, then restart. Existing settings are never overwritten. [Configuration reference](docs/configuration.md) covers microphone selection, recognition timing, and storage. [Troubleshooting](docs/troubleshooting.md) covers permission errors, missing dependencies, and blank displays.

## Platforms

Use a modern browser and a 64-bit operating system. CPU inference is sufficient; no GPU setup is needed.

| Platform | Status |
| --- | --- |
| Apple Silicon macOS | Live microphone, model, identification, persistence, and browser tested locally |
| Windows x86-64 | Native launcher and signal handling implemented; hardware test still needed |
| Linux x86-64 | Target platform; hardware test still needed |
| Linux ARM64 / Raspberry Pi OS 64-bit | Target platform; exact Pi, microphone, and performance still to be tested |
| Intel macOS | Demo works; current live dependencies are incompatible with the last Intel TensorFlow wheels |
| Windows ARM, 32-bit systems, other UNIX | Live mode not supported by this dependency set |

Python 3.11/3.12 are the launcher targets. CI is configured to check unit tests, packaging, and demo startup on macOS, Windows, and Linux; those checks do not validate microphones or TensorFlow on each platform. TensorFlow's [installation requirements](https://www.tensorflow.org/install/pip) apply, including the Microsoft Visual C++ runtime on Windows. Pi performance depends on the eventual hardware choice.

## Data and recognition

The source launcher keeps everything inside the project folder:

- `.venv/`: private Python dependencies.
- `models/yamnet/`: downloaded detector.
- `config.toml`: your settings.
- `data/`: SQLite album history and downloaded covers.
- `.now-playing/`: setup bookkeeping.

The display fetches the collection again whenever it returns to the mosaic, so newly identified albums appear without restarting. Album history survives restarts. Stop the app and back up `data/` to preserve your collection; delete it to reset the collection.

Audio is held in memory rather than saved as recordings. Music detection runs locally; recognition sends a fingerprint derived from the sample to Shazam through ShazamIO. Album metadata and artwork persist locally, and cover downloads contact the artwork provider. Recognition is an unofficial third-party integration and can change or stop working. No account/API key is required by this app; it cannot guarantee a service quota. Requests are spaced ten seconds apart when music is detected, with backoff after failures.

The server listens only on this computer by default. No internet access is needed to show already cached mosaic covers. New recognition requires the service to be reachable.

## Development and deployment

See [architecture](docs/architecture.md), [development and checks](docs/development.md), and the [Raspberry Pi autostart notes](docs/raspberry-pi.md). Node is used only for frontend tests, not to run the app. No playlist or Spotify integration is included.

Inspired by [maurocastermans/now-playing](https://github.com/maurocastermans/now-playing). A project license has not yet been selected; choose one before public distribution. Third-party packages and the downloaded model retain their own licenses.
