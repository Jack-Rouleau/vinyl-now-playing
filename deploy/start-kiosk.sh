#!/bin/sh
set -eu
# Run inside the graphical desktop session, as the desktop user.
now_playing_url="${NOW_PLAYING_URL:-http://127.0.0.1:8080}"
for now_playing_browser in chromium chromium-browser google-chrome; do
    if command -v "$now_playing_browser" >/dev/null 2>&1; then
        exec "$now_playing_browser" --kiosk --no-first-run --noerrdialogs "$now_playing_url"
    fi
done
printf '%s\n' 'Chromium was not found. Install a browser and run this script in your desktop session.' >&2
exit 1
