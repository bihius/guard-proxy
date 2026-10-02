#!/bin/sh
set -eu

SPOA_BIN=/usr/local/bin/coraza-spoa
SPOA_CONFIG=/etc/coraza-spoa/coraza-spoa.yaml
SPOA_PORT=9000
RUNTIME_DIR=/runtime
POLL_INTERVAL_SECONDS=1
SPOA_PID=""

if [ "$(id -u)" = "0" ]; then
    exec su-exec coraza "$0" "$@"
fi

current_release() {
    readlink "$RUNTIME_DIR/current" 2>/dev/null || echo "<missing>"
}

on_term() {
    if [ -n "$SPOA_PID" ]; then
        kill -TERM "$SPOA_PID" 2>/dev/null || true
        wait "$SPOA_PID" 2>/dev/null || true
    fi
    exit 143
}

trap on_term TERM INT

LAST_RELEASE="$(current_release)"
"$SPOA_BIN" -config "$SPOA_CONFIG" &
SPOA_PID=$!

# A new release is picked up with SIGHUP, which makes coraza-spoa rebuild its
# WAF from the same config (re-reading /runtime/current/*) and swap it in while
# the listener stays open. Restarting the process instead closed port 9000 on
# every config apply, and HAProxy's fail-closed rules answered every request
# in that window with 503 (#303). If the new rules fail to load, coraza-spoa
# logs the error and keeps serving the previous ones.
while true; do
    sleep "$POLL_INTERVAL_SECONDS"

    if ! kill -0 "$SPOA_PID" 2>/dev/null; then
        wait "$SPOA_PID" 2>/dev/null || true
        echo "[supervisor] coraza-spoa exited — letting Compose restart container" >&2
        exit 1
    fi

    CURRENT_RELEASE="$(current_release)"
    [ "$CURRENT_RELEASE" != "$LAST_RELEASE" ] || continue

    # coraza-spoa installs its SIGHUP handler only once it has loaded the rules
    # and opened the listener; a SIGHUP before that would kill it. Wait until it
    # is listening. Rules loaded meanwhile may already be the new ones, which
    # makes this reload redundant but harmless.
    nc -z 127.0.0.1 "$SPOA_PORT" 2>/dev/null || continue

    echo "[supervisor] current release changed — reloading coraza-spoa" >&2
    kill -HUP "$SPOA_PID"
    LAST_RELEASE="$CURRENT_RELEASE"
done
