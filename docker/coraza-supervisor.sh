#!/bin/sh
set -eu

SPOA_BIN=/usr/local/bin/coraza-spoa
SPOA_PORT=9000
RUNTIME_DIR=/runtime
# The backend generates one Coraza application per WAF policy into the
# release. Releases without it (the entrypoint stub, or releases written
# before per-policy applications existed) use the single-application config
# baked into the image.
RUNTIME_CONFIG="$RUNTIME_DIR/current/coraza-spoa.yaml"
FALLBACK_CONFIG=/etc/coraza-spoa/coraza-spoa.yaml
# Writable volume, mounted over the read-only /runtime tree. Apply reads
# this file to learn whether the release compiled.
STATUS_DIR="$RUNTIME_DIR/coraza-status"
STATUS_FILE="$STATUS_DIR/reload-status"
POLL_INTERVAL_SECONDS=1
SPOA_PID=""
SPOA_CONFIG=""

if [ "$(id -u)" = "0" ]; then
    # An older Compose file has no writable status volume. Keep serving
    # traffic; apply then times out waiting for a status file that never
    # appears and restores the previous release.
    mkdir -p "$STATUS_DIR" 2>/dev/null || true
    chown coraza:coraza "$STATUS_DIR" 2>/dev/null || true
    exec su-exec coraza "$0" "$@"
fi

current_release() {
    readlink "$RUNTIME_DIR/current" 2>/dev/null || echo "<missing>"
}

selected_config() {
    if [ -f "$RUNTIME_CONFIG" ]; then
        echo "$RUNTIME_CONFIG"
    else
        echo "$FALLBACK_CONFIG"
    fi
}

start_spoa() {
    SPOA_CONFIG="$(selected_config)"
    echo "[supervisor] starting coraza-spoa with $SPOA_CONFIG" >&2
    "$SPOA_BIN" -config "$SPOA_CONFIG" &
    SPOA_PID=$!
}

stop_spoa() {
    kill -TERM "$SPOA_PID" 2>/dev/null || true
    wait "$SPOA_PID" 2>/dev/null || true
}

# Three lines, so a reader can ignore a torn write. Detail is one line and
# capped: the apply response stores it.
write_status() {
    release=$1
    result=$2
    detail=$3
    if [ ! -d "$STATUS_DIR" ] || [ ! -w "$STATUS_DIR" ]; then
        echo "[supervisor] reload status directory is not writable" >&2
        return 0
    fi
    detail=$(printf '%s' "$detail" | tr '\n\r' '  ' | cut -c 1-400)
    tmp="$STATUS_DIR/reload-status.tmp"
    {
        printf 'release=%s\n' "$release"
        printf 'result=%s\n' "$result"
        printf 'detail=%s\n' "$detail"
    } > "$tmp"
    mv "$tmp" "$STATUS_FILE"
}

# Compile the selected config before touching the running process. On
# failure coraza-spoa keeps the rules it already loaded.
accept_release() {
    release=$1
    config=$(selected_config)
    errfile=$(mktemp)
    if ! "$SPOA_BIN" -config "$config" -validate >"$errfile" 2>&1; then
        echo "[supervisor] coraza-spoa rejected $release" >&2
        write_status "$release" error "$(cat "$errfile")"
        rm -f "$errfile"
        return 1
    fi
    rm -f "$errfile"
    if [ "$config" != "$SPOA_CONFIG" ]; then
        # SIGHUP re-reads the same file, and coraza-spoa keeps the
        # default_application it started with, so switching between the
        # fallback and the generated config needs a fresh process.
        echo "[supervisor] coraza-spoa config file changed — restarting coraza-spoa" >&2
        stop_spoa
        start_spoa
    else
        echo "[supervisor] current release changed — reloading coraza-spoa" >&2
        kill -HUP "$SPOA_PID"
    fi
    write_status "$release" ok ""
}

on_term() {
    if [ -n "$SPOA_PID" ]; then
        stop_spoa
    fi
    exit 143
}

trap on_term TERM INT

LAST_RELEASE="$(current_release)"
start_spoa

# A new release is picked up after coraza-spoa -validate succeeds. SIGHUP
# makes coraza-spoa rebuild every application and swap them in while the
# listener stays open. Restarting the process instead closed port 9000 on
# every config apply, and HAProxy's fail-closed rules answered every request
# in that window with 503 (#303).
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

    if accept_release "$CURRENT_RELEASE"; then
        LAST_RELEASE="$CURRENT_RELEASE"
    else
        # Do not validate the same rejected release on every poll. Apply
        # restores the previous symlink, and that change is still noticed.
        LAST_RELEASE="$CURRENT_RELEASE"
    fi
done
