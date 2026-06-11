#!/bin/sh
set -eu

# Must match RUNTIME_GENERATED_CONFIG_ROOT so the shared volume Coraza mounts at
# /runtime is seeded before Coraza starts.
runtime_dir="${GUARD_PROXY_RUNTIME_DIR:-${RUNTIME_GENERATED_CONFIG_ROOT:-/runtime}}"

seed_runtime_config() {
    if [ ! -f "${runtime_dir}/current/rule-overrides.conf" ]; then
        mkdir -p "${runtime_dir}/releases/seed"
        if [ ! -f "${runtime_dir}/releases/seed/crs-setup.conf" ]; then
            # Rule 900990 marks crs-setup.conf as loaded; without it CRS rule
            # 901001 reports "CRS is deployed without configuration!" on every
            # request until the first apply. The app replaces this stub with
            # the full template-rendered config during backend startup.
            {
                printf "SecRuleEngine On\n"
                printf "SecAction \"id:900990,phase:1,pass,nolog,tag:'OWASP_CRS',ver:'OWASP_CRS/4.25.0',setvar:tx.crs_setup_version=4250\"\n"
            } > "${runtime_dir}/releases/seed/crs-setup.conf"
        fi
        if [ ! -f "${runtime_dir}/releases/seed/rule-overrides.conf" ]; then
            printf "# No generated CRS rule overrides yet.\n" > "${runtime_dir}/releases/seed/rule-overrides.conf"
        fi
        ln -sfn releases/seed "${runtime_dir}/current"
    fi
}

if [ "$(id -u)" = "0" ]; then
    mkdir -p "${runtime_dir}/crs"
    seed_runtime_config
    chown -R app:app "${runtime_dir}"
    chmod 755 "${runtime_dir}" "${runtime_dir}/crs"

    exec gosu app "$@"
fi

mkdir -p "${runtime_dir}/crs"
seed_runtime_config
exec "$@"
