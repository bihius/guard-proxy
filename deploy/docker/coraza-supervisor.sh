#!/bin/sh
set -eu

SPOA_BIN=/usr/local/bin/coraza-spoa
SPOA_CONFIG=/etc/coraza-spoa/coraza-spoa.yaml
RUNTIME_DIR=/runtime
SPOA_PID=""

start_spoa() {
    "$SPOA_BIN" -config "$SPOA_CONFIG" &
    SPOA_PID=$!
}

stop_spoa() {
    [ -n "$SPOA_PID" ] || return 0
    kill -TERM "$SPOA_PID" 2>/dev/null || true
    wait "$SPOA_PID" 2>/dev/null || true
    SPOA_PID=""
}

on_term() {
    stop_spoa
    exit 143
}

trap on_term TERM INT

start_spoa

while changed=$(inotifywait -q -e moved_to,create --format '%f' "$RUNTIME_DIR"); do
    [ "$changed" = "current" ] || continue
    echo "[supervisor] current symlink changed — restarting coraza-spoa" >&2
    stop_spoa
    start_spoa
done

# inotifywait exited unexpectedly — let Compose restart the container
stop_spoa
exit 1
