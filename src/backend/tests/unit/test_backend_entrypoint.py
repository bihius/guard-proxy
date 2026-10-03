"""Behaviour of the runtime-config stub seeded by docker-entrypoint.sh."""

import os
import subprocess
from pathlib import Path

import pytest

ENTRYPOINT = Path(__file__).resolve().parents[2] / "docker-entrypoint.sh"

pytestmark = pytest.mark.skipif(
    os.geteuid() == 0, reason="as root the entrypoint chowns and drops to app"
)


def _run_entrypoint(runtime_dir: Path) -> None:
    subprocess.run(
        ["sh", str(ENTRYPOINT), "true"],
        env={**os.environ, "GUARD_PROXY_RUNTIME_DIR": str(runtime_dir)},
        check=True,
        timeout=10,
    )


def test_entrypoint_seeds_a_stub_release_on_an_empty_volume(tmp_path: Path) -> None:
    _run_entrypoint(tmp_path)

    current = tmp_path / "current"
    assert os.readlink(current) == "releases/seed"
    assert "id:900990" in (current / "crs-setup.conf").read_text()
    assert (current / "rule-overrides.conf").is_file()


def test_entrypoint_keeps_an_applied_release_active(tmp_path: Path) -> None:
    """Applied releases keep CRS files under coraza/<app>/, not at the root."""
    release = tmp_path / "releases" / "applied"
    (release / "coraza" / "default").mkdir(parents=True)
    (release / "haproxy.cfg").write_text("global\n")
    (release / "coraza" / "default" / "rule-overrides.conf").write_text("# applied\n")
    (tmp_path / "current").symlink_to("releases/applied")

    _run_entrypoint(tmp_path)

    assert os.readlink(tmp_path / "current") == "releases/applied"
    assert not (tmp_path / "releases" / "seed").exists()
