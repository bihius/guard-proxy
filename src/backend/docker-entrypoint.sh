#!/bin/sh
set -eu

runtime_dir="${GUARD_PROXY_RUNTIME_DIR:-/runtime}"

if [ "$(id -u)" = "0" ]; then
    mkdir -p "${runtime_dir}/crs"
    chown -R app:app "${runtime_dir}"
    chmod 755 "${runtime_dir}" "${runtime_dir}/crs"

    exec gosu app "$@"
fi

mkdir -p "${runtime_dir}/crs"
exec "$@"
