#!/bin/sh
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$ROOT/start.sh" "$@"
RESULT=$?
if [ "$RESULT" -ne 0 ] && [ "$RESULT" -ne 130 ]; then
    printf '\nPress Enter to close.'
    read -r REPLY
fi
exit "$RESULT"
