import tomllib
from collections.abc import Iterator
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

import app.main as main_module

_PYPROJECT_VERSION = tomllib.loads(
    (Path(main_module.__file__).resolve().parent.parent / "pyproject.toml").read_text()
)["project"]["version"]


@pytest.fixture
def package_metadata_missing() -> Iterator[None]:
    """Simulate the production Docker image, where the project itself is
    never installed as a distribution (only its dependencies are), so
    importlib.metadata has no dist-info to read.
    """

    def _raise(name: str) -> str:
        raise PackageNotFoundError(name)

    original = main_module._package_version
    main_module._package_version = _raise
    try:
        yield
    finally:
        main_module._package_version = original


def test_resolves_from_installed_package_metadata_when_present() -> None:
    assert main_module._resolve_app_version() == main_module._package_version(
        "guard-proxy-backend"
    )


def test_falls_back_to_pyproject_toml_when_package_metadata_missing(
    package_metadata_missing: None,
) -> None:
    assert main_module._resolve_app_version() == _PYPROJECT_VERSION
