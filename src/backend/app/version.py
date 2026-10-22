"""The backend's own version, resolved once from a single source of truth."""

from __future__ import annotations

import tomllib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from pathlib import Path


def resolve_app_version() -> str:
    """Return the app version, reading from a single source of truth.

    Prefers installed package metadata (present in dev venvs where the
    project is installed editable). The production Docker image installs
    only dependencies as a distinct layer and copies app source on top
    without installing the project itself, so no dist-info exists there —
    fall back to parsing `pyproject.toml` directly in that case.
    """
    try:
        return _package_version("guard-proxy-backend")
    except PackageNotFoundError:
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        try:
            with pyproject_path.open("rb") as f:
                version = tomllib.load(f)["project"]["version"]
            if not isinstance(version, str):
                raise KeyError("project.version is not a string")
            return version
        except (OSError, KeyError):  # pragma: no cover - defensive fallback
            return "0.0.0+unknown"


APP_VERSION = resolve_app_version()
