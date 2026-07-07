#!/bin/sh
set -eu

SPOA_BIN=/usr/local/bin/coraza-spoa
SPOA_CONFIG=/etc/coraza-spoa/coraza-spoa.yaml
RUNTIME_DIR=/runtime
POLL_INTERVAL_SECONDS=1
SPOA_PID=""
WATCH_PID=""

if [ "$(id -u)" = "0" ]; then
    exec su-exec coraza "$0" "$@"
fi

current_release() {
    readlink "$RUNTIME_DIR/current" 2>/dev/null || echo "<missing>"
}

start_spoa() {
    "$SPOA_BIN" -config "$SPOA_CONFIG" &
    SPOA_PID=$!
}

watch_release() {
    spoa_pid="$1"
    last_release="$2"

    while true; do
        sleep "$POLL_INTERVAL_SECONDS"
        current_release="$(current_release)"
        [ "$current_release" != "$last_release" ] || continue
        echo "[supervisor] current release changed — restarting coraza-spoa" >&2
        kill -TERM "$spoa_pid" 2>/dev/null || true
        exit 0
    done
}

stop_process() {
    pid="$1"
    [ -n "$pid" ] || return 0
    kill -TERM "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
}

on_term() {
    stop_process "$WATCH_PID"
    stop_process "$SPOA_PID"
    exit 143
}

trap on_term TERM INT

LAST_RELEASE="$(current_release)"

while true; do
    start_spoa
    watch_release "$SPOA_PID" "$LAST_RELEASE" &
    WATCH_PID=$!

    wait "$SPOA_PID" 2>/dev/null || true
    stop_process "$WATCH_PID"
    WATCH_PID=""
    SPOA_PID=""

    CURRENT_RELEASE="$(current_release)"
    if [ "$CURRENT_RELEASE" != "$LAST_RELEASE" ]; then
        LAST_RELEASE="$CURRENT_RELEASE"
        continue
    fi

    echo "[supervisor] coraza-spoa exited — letting Compose restart container" >&2
    exit 1
done
