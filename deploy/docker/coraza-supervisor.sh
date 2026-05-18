#!/bin/sh
set -eu

SPOA_BIN=/usr/local/bin/coraza-spoa
SPOA_CONFIG=/etc/coraza-spoa/coraza-spoa.yaml
RUNTIME_DIR=/runtime
LOG_DIR=/var/log/coraza
POLL_INTERVAL_SECONDS=1
SPOA_PID=""

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$LOG_DIR"
    chown -R coraza:coraza "$LOG_DIR"
    exec su-exec coraza "$0" "$@"
fi

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

current_release() {
    readlink "$RUNTIME_DIR/current" 2>/dev/null || echo "<missing>"
}

start_spoa
LAST_RELEASE="$(current_release)"

while true; do
    sleep "$POLL_INTERVAL_SECONDS"
    CURRENT_RELEASE="$(current_release)"
    [ "$CURRENT_RELEASE" != "$LAST_RELEASE" ] || continue
    LAST_RELEASE="$CURRENT_RELEASE"
    echo "[supervisor] current release changed — restarting coraza-spoa" >&2
    stop_spoa
    start_spoa
done
