#!/bin/sh
# Compatibility entry point for existing Mac installations.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -f "$ROOT/config.mac.generated.toml" ]; then
    exec sh "$ROOT/start.sh" --config "$ROOT/config.mac.generated.toml" "$@"
fi
exec sh "$ROOT/start.sh" "$@"
