#!/usr/bin/env python3
"""Fail when a third-party component of the Guard Proxy stack can drift.

Checks every Dockerfile, the dev/release Compose files and the evaluation lab
(its Compose overlay plus the runner scripts that start tool containers) for:

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
COMPOSE_PATHSPECS = [
    "docker/docker-compose*.yml",
    "release/docker-compose*.yml",
    "benchmarks/lab/docker-compose*.yml",
]
RUNNER_PATHSPECS = ["benchmarks/lab/runners/*.sh"]
WORKFLOW_PATHSPECS = [".github/workflows/*.yml"]

BACKEND_DOCKERFILE = "src/backend/Dockerfile"
HAPROXY_REPOSITORY = "haproxy"

PINNED_REF = re.compile(r"^(?P<repo>[^@\s]+):(?P<tag>[^@:/\s]+)@sha256:[0-9a-f]{64}$")
FROM_LINE = re.compile(
    r"^\s*FROM\s+(?:--platform=\S+\s+)?(?P<ref>\S+)(?:\s+AS\s+(?P<stage>\S+))?\s*$",
    re.IGNORECASE,
)
IMAGE_LINE = re.compile(r"^\s*image:\s*[\"']?(?P<ref>[^\"'\s#]+)")
HAPROXY_DEB_ARG = re.compile(r"^\s*ARG\s+HAPROXY_DEB_VERSION=(?P<version>\S+)\s*$")
# Runner scripts: `SOMETHING_IMAGE=<ref>` assignments (including `export`), and
# the image argument of a `docker run` line.
RUNNER_IMAGE_ASSIGNMENT = re.compile(
    r"^\s*(?:export\s+)?[A-Z0-9_]*IMAGE=(?P<quote>[\"']?)(?P<ref>[^\"'\s]+)(?P=quote)\s*$"
)
DOCKER_RUN_LINE = re.compile(r"(?:^|\s)docker\s+run\s+(?P<args>.*)$")
# GitHub Actions: `uses: owner/repo@<ref>`, where <ref> must be a commit SHA.
USES_LINE = re.compile(
    r"^\s*(?:-\s*)?uses:\s*(?P<action>[^\s@]+)@(?P<ref>[^\s#]+)"
)
PINNED_ACTION_REF = re.compile(r"^[0-9a-f]{40}$")
PERMISSIONS_LINE = re.compile(r"^permissions:")


def tracked_files(pathspecs: list[str]) -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "--", *pathspecs],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return sorted(output.splitlines())


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


def runner_refs(path: str) -> list[tuple[int, str]]:
    """Image references a lab runner script starts with ``docker run``.

    Two forms are recognized: a ``*_IMAGE=<ref>`` assignment, and the image
    argument on the ``docker run`` line itself (the first argument that is
    neither an option nor a variable expansion, e.g. ``curlimages/curl:8.11.1``).
    shortcut: an image written literally on a continuation line of a multi-line
    ``docker run`` is not seen; declare it as ``*_IMAGE=`` when that happens.
    """
    refs: list[tuple[int, str]] = []
    for number, line in enumerate((REPO_ROOT / path).read_text().splitlines(), start=1):
        assignment = RUNNER_IMAGE_ASSIGNMENT.match(line)
        if assignment is not None:
            refs.append((number, assignment["ref"]))
            continue
        run = DOCKER_RUN_LINE.search(line)
        if run is None:
            continue
        for token in run["args"].split():
            # Options, variable expansions and the trailing `\` continuation.
            if token.startswith("-") or "$" in token or "\\" in token:
                continue
            refs.append((number, token.strip("\"'")))
            break
    return refs


def workflow_action_refs(path: Path) -> list[tuple[int, str, str]]:
    """``uses:`` references a workflow pulls in, as ``(line, action, ref)``.

    A tag such as ``@v4`` is mutable: whoever controls the action repository can
    repoint it and run different code with this workflow's token. Pinning to the
    commit SHA (with the version in a trailing comment) removes that.
    """
    refs: list[tuple[int, str, str]] = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        match = USES_LINE.match(line)
        if match is not None:
            refs.append((number, match["action"], match["ref"]))
    return refs


def workflow_declares_permissions(path: Path) -> bool:
    """Whether a workflow scopes its token instead of taking the default.

    A top-level `permissions:` key (with its mapping on the following lines, or
    `{}` inline) is enough: it replaces the default scopes.
    """
    return any(
        PERMISSIONS_LINE.match(line) is not None
        for line in path.read_text().splitlines()
    )


def workflow_errors(workflow_dir: Path) -> tuple[list[str], int]:
    """Pin and token-scope problems in a directory of workflow files."""
    errors: list[str] = []
    checked = 0
    for path in sorted(workflow_dir.glob("*.yml")):
        location = path.relative_to(REPO_ROOT) if REPO_ROOT in path.parents else path
        if not workflow_declares_permissions(path):
            errors.append(
                f"{location}: no `permissions:` block; the workflow runs with the "
                "repository's default token scopes"
            )
        for number, action, ref in workflow_action_refs(path):
            checked += 1
            if PINNED_ACTION_REF.match(ref) is None:
                errors.append(
                    f"{location}:{number}: {action}@{ref} is not pinned to a commit "
                    "SHA (mutable tag)"
                )
    return errors, checked


def image_variant(ref: str) -> str:
    """Tag without its version numbers: the role a repository is pinned for.

    ``wordpress:7.1.3-php8.3-apache`` and ``wordpress:cli-2.12.0-php8.3`` are two
    images from one repository (the site and the CLI container), so they may
    hold different references; ``wordpress:7.1.3-php8.3-apache`` and
    ``wordpress:6.9-php8.3-apache`` may not.
    """
    tag = ref.split("@", 1)[0].rsplit(":", 1)[1]
    return re.sub(r"\d+(?:\.\d+)*", "", tag).strip("-.")


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
    for path in tracked_files(RUNNER_PATHSPECS):
        refs.extend((path, number, ref) for number, ref in runner_refs(path))

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

    # One repository may hold several variants (WordPress site vs. CLI), each
    # pinned once; the same variant pinned twice must agree.
    for repo, pins in sorted(pins_by_repo.items()):
        by_variant: dict[str, dict[str, list[str]]] = {}
        for ref, locations in pins.items():
            by_variant.setdefault(image_variant(ref), {})[ref] = locations
        for variant, variant_pins in sorted(by_variant.items()):
            if len(variant_pins) > 1:
                listing = "; ".join(
                    f"{ref} ({', '.join(locations)})"
                    for ref, locations in sorted(variant_pins.items())
                )
                errors.append(
                    f"{repo}:{variant or '<version only>'} is pinned to different "
                    f"references: {listing}"
                )

    workflow_problems, action_refs = workflow_errors(REPO_ROOT / ".github/workflows")
    errors.extend(workflow_problems)

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
    print(
        f"Version pins OK: {len(refs)} image references and "
        f"{action_refs} workflow action references checked."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
