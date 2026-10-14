"""Unit tests for the repository's version-pin checker (GitHub Actions half).

The image half is exercised by the CI job that runs the script; the workflow
checks are pure enough to test with fixtures, which is how the mutable-tag and
missing-`permissions` rules are pinned down here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".git").exists():
            return candidate
    raise FileNotFoundError("repository root not found")


_SCRIPT = _repo_root() / ".github" / "scripts" / "check_version_pins.py"
_spec = importlib.util.spec_from_file_location("check_version_pins", _SCRIPT)
assert _spec is not None and _spec.loader is not None
checker = importlib.util.module_from_spec(_spec)
sys.modules["check_version_pins"] = checker
_spec.loader.exec_module(checker)


def _workflow(tmp_path: Path, body: str, name: str = "ci.yml") -> Path:
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(body)
    return directory


PINNED = (
    "name: CI\n"
    "on: [push]\n"
    "permissions:\n"
    "  contents: read\n"
    "jobs:\n"
    "  build:\n"
    "    steps:\n"
    "      - uses: actions/checkout@"
    "11d5960a326750d5838078e36cf38b85af677262 # v4.4.0\n"
)


def test_pinned_workflow_reports_no_problems(tmp_path: Path) -> None:
    errors, checked = checker.workflow_errors(_workflow(tmp_path, PINNED))

    assert errors == []
    assert checked == 1


@pytest.mark.parametrize("ref", ["v4", "main", "v4.4.0"])
def test_mutable_action_ref_is_reported(tmp_path: Path, ref: str) -> None:
    body = PINNED.replace(
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0",
        f"actions/checkout@{ref}",
    )

    errors, _ = checker.workflow_errors(_workflow(tmp_path, body))

    assert len(errors) == 1
    assert "is not pinned to a commit SHA" in errors[0]
    assert ref in errors[0]


def test_missing_permissions_block_is_reported(tmp_path: Path) -> None:
    body = PINNED.replace("permissions:\n  contents: read\n", "")

    errors, _ = checker.workflow_errors(_workflow(tmp_path, body))

    assert len(errors) == 1
    assert "no `permissions:` block" in errors[0]


def test_inline_empty_permissions_block_counts(tmp_path: Path) -> None:
    """`permissions: {}` still replaces the default token scopes."""
    body = PINNED.replace("permissions:\n  contents: read\n", "permissions: {}\n")

    errors, _ = checker.workflow_errors(_workflow(tmp_path, body))

    assert errors == []


def test_every_shipped_workflow_is_pinned_and_scoped() -> None:
    """The repository's own workflows must pass the check the CI job runs."""
    errors, checked = checker.workflow_errors(checker.REPO_ROOT / ".github/workflows")

    assert errors == []
    assert checked >= 10
