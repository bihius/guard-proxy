"""Tests for the repository-level Docker user-management wrapper."""

import os
import stat
import subprocess
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    """Return the repository root containing the users wrapper."""
    for directory in (start, *start.parents):
        if (directory / "bin" / "users").is_file():
            return directory
    raise RuntimeError("Could not locate the repository root")


REPO_ROOT = _find_repo_root(Path(__file__).resolve().parent)
USERS_WRAPPER = REPO_ROOT / "bin" / "users"


def _write_fake_command(directory: Path, name: str) -> Path:
    """Create a command that captures argv and returns a configured exit code."""
    directory.mkdir(exist_ok=True)
    command = directory / name
    command.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$@\" > \"$CAPTURE_PATH\"\n"
        'exit "${FAKE_EXIT_CODE:-0}"\n'
    )
    command.chmod(command.stat().st_mode | stat.S_IXUSR)
    return command


def _run_wrapper(
    tmp_path: Path, *arguments: str, exit_code: int = 0
) -> subprocess.CompletedProcess[str]:
    """Run the wrapper from another directory against fake Docker commands."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    capture_path = tmp_path / "arguments.txt"
    environment = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}/usr/bin{os.pathsep}/bin",
        "CAPTURE_PATH": str(capture_path),
        "FAKE_EXIT_CODE": str(exit_code),
    }
    return subprocess.run(
        [str(USERS_WRAPPER), *arguments],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_users_wrapper_prefers_docker_compose_and_preserves_arguments(
    tmp_path: Path,
) -> None:
    """The wrapper passes all CLI arguments unchanged to docker-compose."""
    _write_fake_command(tmp_path / "bin", "docker-compose")

    result = _run_wrapper(
        tmp_path,
        "create",
        "--email",
        "alice@example.com",
        "--password",
        "correct horse battery staple",
        "--full-name",
        "Alice Example",
        "--role",
        "viewer",
    )

    assert result.returncode == 0
    assert (tmp_path / "arguments.txt").read_text().splitlines() == [
        "-f",
        str(REPO_ROOT / "docker" / "docker-compose.yml"),
        "--env-file",
        str(REPO_ROOT / "docker" / ".env"),
        "exec",
        "backend",
        "/app/.venv/bin/python",
        "scripts/manage_users.py",
        "create",
        "--email",
        "alice@example.com",
        "--password",
        "correct horse battery staple",
        "--full-name",
        "Alice Example",
        "--role",
        "viewer",
    ]


def test_users_wrapper_falls_back_to_docker_compose_v2_and_preserves_exit_code(
    tmp_path: Path,
) -> None:
    """The wrapper uses `docker compose` when docker-compose is unavailable."""
    _write_fake_command(tmp_path / "bin", "docker")

    result = _run_wrapper(tmp_path, "list", "--json", exit_code=23)

    assert result.returncode == 23
    assert (tmp_path / "arguments.txt").read_text().splitlines()[:2] == [
        "compose",
        "-f",
    ]
