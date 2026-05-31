#!/bin/sh
set -eu

STATE_DIR="$(dirname "${SHIPPER_STATE_FILE:-/var/lib/log-shipper/offset}")"

if [ "$(id -u)" = "0" ]; then
    mkdir -p "${STATE_DIR}"
    chown -R shipper:shipper "${STATE_DIR}"
    exec gosu shipper "$@"
fi

mkdir -p "${STATE_DIR}"
exec "$@"
