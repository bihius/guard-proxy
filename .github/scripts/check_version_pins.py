#!/usr/bin/env python3
"""Fail when a third-party component of the Guard Proxy stack can drift.

Checks every Dockerfile and the dev/release Compose files (the benchmark lab is
not covered) for:

- external images not pinned as ``name:tag@sha256:<digest>``;
- one image repository pinned to different references in different files
  (e.g. dev and release Compose running different PostgreSQL builds);
- the backend's HAProxy package (used for ``haproxy -c`` validation) not being
  the same HAProxy release as the ``haproxy`` image that runs the config.

Run from anywhere: ``python3 .github/scripts/check_version_pins.py``.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DOCKERFILE_PATHSPECS = ["*Dockerfile", "*.Dockerfile"]
COMPOSE_PATHSPECS = ["docker/docker-compose*.yml", "release/docker-compose*.yml"]
EXCLUDED_PREFIXES = ("benchmarks/",)

BACKEND_DOCKERFILE = "src/backend/Dockerfile"
HAPROXY_REPOSITORY = "haproxy"

PINNED_REF = re.compile(r"^(?P<repo>[^@\s]+):(?P<tag>[^@:/\s]+)@sha256:[0-9a-f]{64}$")
FROM_LINE = re.compile(
    r"^\s*FROM\s+(?:--platform=\S+\s+)?(?P<ref>\S+)(?:\s+AS\s+(?P<stage>\S+))?\s*$",
    re.IGNORECASE,
)
IMAGE_LINE = re.compile(r"^\s*image:\s*[\"']?(?P<ref>[^\"'\s#]+)")
HAPROXY_DEB_ARG = re.compile(r"^\s*ARG\s+HAPROXY_DEB_VERSION=(?P<version>\S+)\s*$")


def tracked_files(pathspecs: list[str]) -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "--", *pathspecs],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return sorted(
        path for path in output.splitlines() if not path.startswith(EXCLUDED_PREFIXES)
    )


def dockerfile_refs(path: str) -> list[tuple[int, str]]:
    refs: list[tuple[int, str]] = []
    stages: set[str] = set()
    lines = (REPO_ROOT / path).read_text().splitlines()
    for number, line in enumerate(lines, start=1):
        match = FROM_LINE.match(line)
        if match is None:
            continue
        ref = match["ref"]
        # FROM <earlier stage> reuses a build stage, not a registry image.
        if ref.lower() not in stages:
            refs.append((number, ref))
        if match["stage"]:
            stages.add(match["stage"].lower())
    return refs


def compose_refs(path: str) -> list[tuple[int, str]]:
    refs: list[tuple[int, str]] = []
    lines = (REPO_ROOT / path).read_text().splitlines()
    for number, line in enumerate(lines, start=1):
        match = IMAGE_LINE.match(line)
        # Guard Proxy's own images are versioned by GUARD_PROXY_IMAGE_TAG.
        if match is None or match["ref"].startswith("${"):
            continue
        refs.append((number, match["ref"]))
    return refs


def haproxy_deb_version() -> str | None:
    for line in (REPO_ROOT / BACKEND_DOCKERFILE).read_text().splitlines():
        match = HAPROXY_DEB_ARG.match(line)
        if match is not None:
            return match["version"]
    return None


def main() -> int:
    errors: list[str] = []
    refs: list[tuple[str, int, str]] = []
    for path in tracked_files(DOCKERFILE_PATHSPECS):
        refs.extend((path, number, ref) for number, ref in dockerfile_refs(path))
    for path in tracked_files(COMPOSE_PATHSPECS):
        refs.extend((path, number, ref) for number, ref in compose_refs(path))

    pins_by_repo: dict[str, dict[str, list[str]]] = {}
    for path, number, ref in refs:
        location = f"{path}:{number}"
        match = PINNED_REF.match(ref)
        if match is None:
            errors.append(
                f"{location}: {ref} is not pinned as name:tag@sha256:<digest>"
            )
            continue
        pins_by_repo.setdefault(match["repo"], {}).setdefault(ref, []).append(location)

    for repo, pins in sorted(pins_by_repo.items()):
        if len(pins) > 1:
            listing = "; ".join(
                f"{ref} ({', '.join(locations)})"
                for ref, locations in sorted(pins.items())
            )
            errors.append(f"{repo} is pinned to different references: {listing}")

    deb_version = haproxy_deb_version()
    if deb_version is None:
        errors.append(
            f"{BACKEND_DOCKERFILE}: ARG HAPROXY_DEB_VERSION=<version> not found"
        )
    haproxy_pins = pins_by_repo.get(HAPROXY_REPOSITORY, {})
    if not haproxy_pins:
        errors.append(
            f"no pinned {HAPROXY_REPOSITORY} image found in the Compose files"
        )
    if deb_version is not None:
        backend_release = deb_version.split("-", 1)[0]
        for ref in haproxy_pins:
            image_tag = ref.split("@", 1)[0].rsplit(":", 1)[1]
            image_release = image_tag.split("-", 1)[0]
            if image_release != backend_release:
                errors.append(
                    f"HAProxy mismatch: runtime image {ref} is {image_release}, but "
                    f"{BACKEND_DOCKERFILE} validates configs with {backend_release} "
                    f"(HAPROXY_DEB_VERSION={deb_version})"
                )

    if errors:
        print("Version pin check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"Version pins OK: {len(refs)} image references checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
