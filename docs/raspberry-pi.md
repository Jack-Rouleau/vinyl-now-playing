# Raspberry Pi and HDMI

Use a 64-bit OS, Python 3.11/3.12, an input microphone, and a desktop browser driving the HDMI screen. The Pi model and microphone are deliberately not fixed yet. Validate TensorFlow installation and inference speed on the actual device before committing to hardware. A 32-bit Pi OS does not fit this dependency set.

First run the normal Linux setup from the README. Confirm microphone selection, song recognition, cached covers, and browser full-screen mode manually. A desktop session is required for the HDMI browser; a headless SSH terminal alone does not create one.

Optional examples in `deploy/` separate the backend from the browser. The systemd user service assumes the project is at `~/now-playing` with `config.toml` and an installed `.venv`. Adjust paths and the URL/port to match your installation, and replace `YOUR_USER` in the desktop autostart example. The service does not install dependencies or download the model.

```sh
mkdir -p ~/.config/systemd/user
cp deploy/now-playing.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now now-playing
journalctl --user -u now-playing -f
```

Only enable browser autostart after verifying its command in the device's desktop session. Browser package/executable names differ between distributions. Do not enable two backend services or reuse an occupied display port. Keep localhost binding for a single-device display.
