"""Version agreement between this image and the config/CRS it runs with.

Issue #312: `haproxy/coraza.cfg` is bind-mounted from the operator's extracted
release kit, so a tag-only upgrade runs a new image against an old file. A
pre-beta.5 `coraza.cfg` sends `app=str(default)`, so every request is inspected
by the default application instead of its vhost's `policy_<id>` — no error,
just the wrong policy. The stamp check below turns that into a loud, nameable
failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.constants.versions import EXPECTED_CONFIG_VERSION
from app.version import APP_VERSION

CONFIG_VERSION_STAMP = "# guard-proxy-config-version:"

_STAMP_RE = re.compile(rf"^{re.escape(CONFIG_VERSION_STAMP)}\s*(\d+)\s*$", re.MULTILINE)
# Release tags use the GitHub spelling `v0.1.0-beta.10`; the backend reports
# the PEP 440 spelling `0.1.0b10`.
_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.?(\d+))?$")
_TAG_SUFFIX = {"alpha": "a", "beta": "b", "rc": "rc"}


@dataclass(frozen=True)
class ConfigVersionCheck:
    """Result of comparing the mounted seed config with this image."""

    path: Path
    present: bool
    version: int | None
    detail: str | None

    @property
    def ok(self) -> bool:
        return self.detail is None


def check_seed_config(path: Path | None = None) -> ConfigVersionCheck:
    """Compare the bind-mounted seed `coraza.cfg` with what this image expects.

    A missing file is not a failure: local runs (and `pytest`) have no release
    kit mounted, and a wrong mount path fails loudly in HAProxy instead. A
    present file without a current stamp is the half-done upgrade of #312.
    """
    target = path or Path(settings.seed_coraza_config_path)
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ConfigVersionCheck(path=target, present=False, version=None, detail=None)

    match = _STAMP_RE.search(text)
    version = int(match.group(1)) if match else None
    if version == EXPECTED_CONFIG_VERSION:
        return ConfigVersionCheck(
            path=target, present=True, version=version, detail=None
        )

    if version is None:
        detail = (
            f"{target} has no '{CONFIG_VERSION_STAMP} N' stamp, so it predates "
            "this image. Replace the haproxy/ files with the ones from the "
            "release named by GUARD_PROXY_IMAGE_TAG."
        )
    elif version < EXPECTED_CONFIG_VERSION:
        detail = (
            f"{target} is config version {version}, but this image expects "
            f"{EXPECTED_CONFIG_VERSION}: it predates this image. Replace the "
            "haproxy/ files with the ones from the release named by "
            "GUARD_PROXY_IMAGE_TAG."
        )
    else:
        detail = (
            f"{target} is config version {version}, newer than the "
            f"{EXPECTED_CONFIG_VERSION} this image understands: the haproxy/ "
            "files belong to a newer release than GUARD_PROXY_IMAGE_TAG."
        )
    return ConfigVersionCheck(path=target, present=True, version=version, detail=detail)


def tag_to_pep440(tag: str) -> str | None:
    """Map a release tag (`v0.1.0-beta.10`) to PEP 440 (`0.1.0b10`)."""
    match = _TAG_RE.match(tag.strip())
    if match is None:
        return None
    major, minor, patch, stage, number = match.groups()
    suffix = "" if stage is None else f"{_TAG_SUFFIX[stage]}{int(number)}"
    return f"{major}.{minor}.{patch}{suffix}"


def configured_image_tag() -> str | None:
    """The image tag the operator selected, or None when it is not configured."""
    tag = (settings.guard_proxy_image_tag or "").strip()
    return tag or None


def image_tag_warning() -> str | None:
    """Warn when the configured image tag and this backend's version disagree."""
    tag = configured_image_tag()
    if tag is None or tag_to_pep440(tag) == APP_VERSION:
        return None
    return (
        f"GUARD_PROXY_IMAGE_TAG is {tag!r} but this backend is version "
        f"{APP_VERSION}: the stack mixes releases. Set the tag to the release "
        "the images were pulled from."
    )
