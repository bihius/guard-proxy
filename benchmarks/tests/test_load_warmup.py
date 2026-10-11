"""A cold WordPress origin must not contaminate either measured wrk run."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "lab/runners/run-load.sh"


def test_wordpress_warms_each_path_before_measuring(tmp_path: Path) -> None:
    scripts = tmp_path / "benchmarks/lab/runners"
    scripts.mkdir(parents=True)
    runner = scripts / "run-load.sh"
    shutil.copyfile(RUNNER, runner)
    (scripts / "lib.sh").write_text(
        """SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
REPO_ROOT=.
RUN_DIR="${SCRIPT_DIR}/../../results/run-${RUN_ID}"
LAB_FTW_DOMAIN=ftw.local
LAB_WP_DOMAIN=wp.local
ATTACKER_CPUSET=
HAPROXY_HTTP_PORT=8080
DOCKER_NETWORK=guard-proxy_gp_internal
resolve_policy() { POLICY_JSON='{}'; }
write_manifest() { :; }
compose_container_id() { :; }
copy_audit_log_snapshot() { :; }
write_summary() { :; }
env_value() { printf '%s' "$2"; }
setup_run_dir() { mkdir -p "${RUN_DIR}/$1"; printf '%s' "${RUN_DIR}/$1"; }
"""
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
case "$*" in *' -v') echo 'wrk 4.2.0'; exit 0;; esac
case "$*" in
  *'http://haproxy:80/'*) target=waf;;
  *'http://wordpress:80/'*) target=direct;;
  *) exit 1;;
esac
flag="$FAKE_WRK_STATE/$target"
errors=0
if [ ! -f "$flag" ]; then
  : > "$flag"
  errors=7
fi
printf 'WRK_SUMMARY requests=100 duration_us=1000000 rps=100.00 lat_p50_us=5000 lat_p95_us=10000 lat_p99_us=15000 errors=%s\\n' "$errors"
"""
    )
    docker.chmod(0o755)
    result = subprocess.run(
        ["bash", str(runner)],
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "FAKE_WRK_STATE": str(tmp_path),
            "RUN_ID": "warmup-test",
            "LOAD_TARGET": "wordpress",
            "LOAD_CLIENT": "local",
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads((tmp_path / "benchmarks/results/run-warmup-test/load-wp.local/performance.json").read_text())
    assert output["valid"] is True
    assert output["waf_errors"] == 0
    assert output["baseline_errors"] == 0
    assert output["config"]["warmup_duration"] == "5s"
