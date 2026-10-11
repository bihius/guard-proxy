"""The run manifest records the WordPress core version the run measured.

``write_manifest`` puts the version of the target into ``manifest.json`` next to
the git SHA, so a run states what it measured even after the image pin moves.
These tests stub ``docker`` and call the function from ``lib.sh``, so they run
without a lab (unit tests, not lab integration tests).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_SH = REPO_ROOT / "benchmarks" / "lab" / "runners" / "lib.sh"

DOCKER_STUB = """#!/bin/sh
# Records its argv so the test can check how the runner called `docker compose`.
printf '[%s]\\n' "$@" >> "$DOCKER_STUB_LOG"
{body}
"""


def write_manifest(tmp_path: Path, stub_body: str) -> tuple[Any, dict, list[str]]:
    """Run write_manifest with a stubbed docker; return (result, manifest, argv)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "docker"
    stub.write_text(DOCKER_STUB.format(body=stub_body))
    stub.chmod(0o755)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    log = tmp_path / "docker-argv.log"

    result = subprocess.run(
        ["bash", "-c", f'source "{LIB_SH}"; RUN_DIR="{run_dir}" write_manifest'],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "RUN_ID": "unit-test",
            "DOCKER_STUB_LOG": str(log),
        },
    )
    manifest = json.loads((run_dir / "manifest.json").read_text())
    argv = log.read_text().splitlines() if log.exists() else []
    return result, manifest, argv


def test_records_the_wordpress_core_version(tmp_path: Path) -> None:
    result, manifest, argv = write_manifest(tmp_path, 'echo "7.1.3"')

    assert result.returncode == 0, result.stderr
    assert manifest["config"]["wordpress_version"] == "7.1.3"
    # `wp core version` must reach the container as one argument: the wp-cli
    # entrypoint is `sh -c`, which runs only the first one. Split into three
    # arguments it would run bare `wp` and print WP-CLI's help text.
    assert argv[-1] == "[wp core version]"


def test_records_null_when_the_lab_is_not_up(tmp_path: Path) -> None:
    result, manifest, _ = write_manifest(
        tmp_path, 'echo "no container to run" >&2\nexit 1'
    )

    assert result.returncode == 0, result.stderr
    assert manifest["config"]["wordpress_version"] is None
