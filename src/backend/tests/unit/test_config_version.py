from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.config import settings
from app.constants.versions import CRS_VERSION, EXPECTED_CONFIG_VERSION
from app.services.config_version import (
    CONFIG_VERSION_STAMP,
    check_seed_config,
    image_tag_warning,
    tag_to_pep440,
)
from app.version import APP_VERSION


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".git").exists():
            return candidate
    raise FileNotFoundError("repository root not found")


REPO_ROOT = _repo_root()

# What the release kit shipped before the stamp existed: no version header,
# hardcoded `app=str(default)` so per-vhost policies are never selected.
STALE_CORAZA_CFG = """\
[coraza]

spoe-agent coraza-agent
    groups              coraza-req
    option              var-prefix  coraza
    option              set-on-error  error

spoe-message coraza-req
    args app=str(default) id=unique-id method=method path=path
"""


@pytest.mark.parametrize(
    "relative_path",
    [
        "configs/haproxy/coraza.cfg",
        "configs/haproxy/haproxy.cfg",
        "release/haproxy/coraza.cfg",
        "release/haproxy/haproxy.cfg",
    ],
)
def test_shipped_configs_carry_the_expected_stamp(relative_path: str) -> None:
    check = check_seed_config(REPO_ROOT / relative_path)

    assert check.present
    assert check.ok
    assert check.version == EXPECTED_CONFIG_VERSION


def test_config_without_stamp_is_stale(tmp_path: Path) -> None:
    stale = tmp_path / "coraza.cfg"
    stale.write_text(STALE_CORAZA_CFG)

    check = check_seed_config(stale)

    assert check.present
    assert not check.ok
    assert check.version is None
    assert str(stale) in check.detail
    assert CONFIG_VERSION_STAMP in check.detail
    assert "Replace the haproxy/ files" in check.detail


def test_older_stamp_is_stale(tmp_path: Path) -> None:
    stale = tmp_path / "coraza.cfg"
    stale.write_text(f"{CONFIG_VERSION_STAMP} 0\n\n[coraza]\n")

    check = check_seed_config(stale)

    assert not check.ok
    assert check.version == 0
    assert "config version 0" in check.detail
    assert str(EXPECTED_CONFIG_VERSION) in check.detail


def test_newer_stamp_is_stale(tmp_path: Path) -> None:
    """Config files from a newer release are as wrong as older ones."""
    future = tmp_path / "coraza.cfg"
    future.write_text(f"{CONFIG_VERSION_STAMP} {EXPECTED_CONFIG_VERSION + 1}\n")

    check = check_seed_config(future)

    assert not check.ok
    assert "newer than" in check.detail


def test_missing_seed_config_is_not_an_error(tmp_path: Path) -> None:
    """No release kit mounted (local runs, pytest) must not degrade health."""
    check = check_seed_config(tmp_path / "absent.cfg")

    assert not check.present
    assert check.ok
    assert check.detail is None


def test_check_reads_the_configured_seed_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = tmp_path / "coraza.cfg"
    seed.write_text(STALE_CORAZA_CFG)
    monkeypatch.setattr(settings, "seed_coraza_config_path", str(seed))

    check = check_seed_config()

    assert check.path == seed
    assert not check.ok


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v0.1.0-beta.10", "0.1.0b10"),
        ("0.1.0-beta.10", "0.1.0b10"),
        ("v0.1.0-rc.1", "0.1.0rc1"),
        ("v0.1.0-alpha.2", "0.1.0a2"),
        ("v0.1.0", "0.1.0"),
        ("nightly", None),
        ("v0.1", None),
    ],
)
def test_tag_to_pep440(tag: str, expected: str | None) -> None:
    assert tag_to_pep440(tag) == expected


def test_image_tag_warning_is_silent_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "guard_proxy_image_tag", None)

    assert image_tag_warning() is None


def test_image_tag_warning_is_silent_when_it_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tag = "v" + re.sub(r"b(\d+)$", r"-beta.\1", APP_VERSION)
    monkeypatch.setattr(settings, "guard_proxy_image_tag", tag)

    assert tag_to_pep440(tag) == APP_VERSION
    assert image_tag_warning() is None


def test_image_tag_warning_names_a_skewed_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "guard_proxy_image_tag", "v0.0.1")

    warning = image_tag_warning()

    assert warning is not None
    assert "v0.0.1" in warning
    assert APP_VERSION in warning


def test_crs_version_matches_the_submodule() -> None:
    """The generated CRS metadata must describe the rules the submodule ships."""
    example = REPO_ROOT / "configs/coraza/crs/crs-setup.conf.example"
    if not example.exists():
        pytest.skip("configs/coraza/crs submodule is not initialized")

    header = "\n".join(example.read_text(encoding="utf-8").splitlines()[:4])

    assert f"# OWASP CRS ver.{CRS_VERSION}" in header
