import tomllib
from collections.abc import Iterator
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

import app.version as version_module

_PYPROJECT_VERSION = tomllib.loads(
    (
        Path(version_module.__file__).resolve().parent.parent / "pyproject.toml"
    ).read_text()
)["project"]["version"]


@pytest.fixture
def package_metadata_missing() -> Iterator[None]:
    """Simulate the production Docker image, where the project itself is
    never installed as a distribution (only its dependencies are), so
    importlib.metadata has no dist-info to read.
    """

    def _raise(name: str) -> str:
        raise PackageNotFoundError(name)

    original = version_module._package_version
    version_module._package_version = _raise
    try:
        yield
    finally:
        version_module._package_version = original


def test_resolves_from_installed_package_metadata_when_present() -> None:
    assert version_module.resolve_app_version() == version_module._package_version(
        "guard-proxy-backend"
    )


def test_falls_back_to_pyproject_toml_when_package_metadata_missing(
    package_metadata_missing: None,
) -> None:
    assert version_module.resolve_app_version() == _PYPROJECT_VERSION
