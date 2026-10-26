# Now Playing

Listen to music through a microphone and show the song, artist, album, and cover on a standard HDMI display. Between songs, a shifting mosaic shows the albums previously identified. A small activity indicator shows when the app hears music or identifies a song.

No Spotify account, playlists, or special display hardware. Recognition uses Shazam through ShazamIO; music detection runs locally with YAMNet. An internet connection is needed for setup, identification, and new covers.

## Windows: install the app

**[Download the Windows installer](https://github.com/Jack-Rouleau/vinyl-now-playing/releases/download/v0.3.0/Now-Playing-Windows-Setup.exe)** (Windows x64 preview, about 308 MB). The source-code ZIP from the green Code button is for developers; it is not the app installer.

1. Open the installer and click **Install**.
2. Open **Now Playing** from the Start menu.
3. Allow microphone access if Windows asks, then play music nearby.

Your browser opens the display automatically. The app window shows progress while the music detector starts, which can take a minute. Choose another microphone in that window if needed. Close the app window to stop listening; open it from the Start menu next time.

**No Python installation, terminal, account, or setup commands are needed.** Python, audio/recognition dependencies, Microsoft runtime DLLs, and the detector are bundled. Internet is needed to identify songs and fetch new covers. Album history survives upgrades and uninstall/reinstall. The preview installer is unsigned, so Windows may display a publisher warning. Use a build supplied by the project owner or the repository's release page.

Windows x64 is the first packaged target. The installer and installed executable are tested on a Windows build runner, including spawned TensorFlow inference, audio-library loading, native window startup, browser assets, and shutdown. Physical microphone/identification testing on a Windows computer remains necessary. An installer is available to friends once its build has passed and the owner has supplied or published it; downloading the repository alone does not produce one.

## Run from source (developers and other platforms)

The following path requires **Python 3.12, 64-bit**, from [python.org](https://www.python.org/downloads/) (3.11 also works). It is useful for development and platforms without a packaged build. On Windows, include the Python launcher (`py`). Extract the source into a writable folder and open a terminal there:

| Computer | Command |
| --- | --- |
| macOS or Linux | `sh start.sh` |
| Windows, PowerShell | `.\start.cmd` |
| Windows, Command Prompt | `start.cmd` |

The first source run creates a private `.venv`, installs dependencies, downloads the detector, and creates `config.toml`. This can take several minutes. Later runs reuse setup. Source setup never installs system packages or requests administrator access.

Allow microphone access for the launching terminal. The source display opens at **http://127.0.0.1:8080**. Allow model startup, then 10–30 seconds of clear music for identification; slower hardware or networks can take longer. Use browser full-screen mode on the HDMI screen. Keep the terminal open and press **Ctrl+C** there to stop.

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
| Windows x86-64 | Self-contained desktop installer; frozen model/UI/lifecycle checked in build workflow; physical microphone test still needed |
| Linux x86-64 | Target platform; hardware test still needed |
| Linux ARM64 / Raspberry Pi OS 64-bit | Target platform; exact Pi, microphone, and performance still to be tested |
| Intel macOS | Demo works; current live dependencies are incompatible with the last Intel TensorFlow wheels |
| Windows ARM, 32-bit systems, other UNIX | Live mode not supported by this dependency set |

Python 3.11/3.12 are the launcher targets. CI is configured to check unit tests, packaging, and demo startup on macOS, Windows, and Linux; those checks do not validate microphones or TensorFlow on each platform. TensorFlow's [installation requirements](https://www.tensorflow.org/install/pip) apply, including the Microsoft Visual C++ runtime on Windows. Pi performance depends on the eventual hardware choice.

## Data and recognition

The Windows installed app keeps album history and logs under `%LOCALAPPDATA%\NowPlaying`, outside its installation folder. Use the app window to select inputs and stop/start listening. Its display port is chosen automatically. It does not read the source tree’s `config.toml` or migrate its `data/` automatically.

The source launcher keeps everything inside the project folder:

- `.venv/`: private Python dependencies.
- `models/yamnet/`: downloaded detector.
- `config.toml`: your settings.
- `data/`: SQLite album history and downloaded covers.
- `.now-playing/`: setup bookkeeping.

The display fetches the collection again whenever it returns to the mosaic, so newly identified albums appear without restarting. Album history survives restarts. Stop the app and back up `data/` to preserve your collection; delete it to reset the collection.

Click a mosaic cover once to show a translucent red removal confirmation with a trash icon, then click it again to remove the album. Click elsewhere or press Escape to cancel. All copies of that album disappear together. Playing and identifying the album again can save it again.

For records played in order, the app looks up the recognized album's ordered songs and durations using Apple's public iTunes metadata service. It uses the recognition's playback position when available to follow the album through missed matches. Songs inferred from album timing show 💿 beside their title; successful recognition corrects the timeline. The bottom-right corner shows “Next song” when a following track is known. Sustained silence clears the timeline, and playback never loops automatically after the last track.

Album inference depends on finding a complete matching digital edition. Missing metadata falls back to normal recognition. Vinyl editions can differ in order, gaps, or speed; without a playback position, timing starts conservatively at the first recognition and can be late. Track lists are cached in memory for the running session. The public [iTunes Search API](https://performance-partners.apple.com/search-api) requires no account or API key.

Audio is held in memory rather than saved as recordings. Music detection runs locally; recognition sends a fingerprint derived from the sample to Shazam through ShazamIO. Album metadata and artwork persist locally, and cover downloads contact the artwork provider. Recognition is an unofficial third-party integration and can change or stop working. No account/API key is required by this app; it cannot guarantee a service quota. Requests are spaced ten seconds apart when music is detected, with backoff after failures.

The server listens only on this computer by default. No internet access is needed to show already cached mosaic covers. New recognition requires the service to be reachable.

## Development and deployment

See [architecture](docs/architecture.md), [development and checks](docs/development.md), and the [Raspberry Pi autostart notes](docs/raspberry-pi.md). Node is used only for frontend tests, not to run the app. No playlist or Spotify integration is included.

Inspired by [maurocastermans/now-playing](https://github.com/maurocastermans/now-playing). A project license has not yet been selected; choose one before public distribution. Third-party packages and the downloaded model retain their own licenses.
