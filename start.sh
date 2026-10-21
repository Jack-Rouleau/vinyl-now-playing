#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for PYTHON in python3.12 python3.11 python3; do
    if command -v "$PYTHON" >/dev/null 2>&1 && "$PYTHON" -c 'import sys; sys.exit(sys.version_info[:2] not in ((3,11),(3,12)))' 2>/dev/null; then
        exec "$PYTHON" "$ROOT/run.py" "$@"
    fi
done
echo 'Install Python 3.12 (64-bit) from python.org, then run this file again.' >&2
exit 1
