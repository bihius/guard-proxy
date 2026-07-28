"""Unit tests for app.services.geoip_service (issue #175).

No database, no HTTP layer — httpx and maxminddb are monkeypatched so these
tests run offline and never touch the real MaxMind API.
"""

from __future__ import annotations

import io
import logging
import os
import tarfile
from ipaddress import IPv4Network
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-onlyx")

from app.config import settings  # noqa: E402
from app.services import geoip_service  # noqa: E402


class _FakeReader:
    """Stand-in for the `maxminddb.open_database()` context manager."""

    def __init__(self, entries: list[tuple[IPv4Network, dict]]) -> None:
        self._entries = entries

    def __enter__(self) -> _FakeReader:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def __iter__(self):
        return iter(self._entries)


@pytest.fixture(autouse=True)
def _isolated_runtime_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(tmp_path))


# ---------------------------------------------------------------------------
# ensure_map_file_exists
# ---------------------------------------------------------------------------


def test_ensure_map_file_exists_creates_stub_when_absent() -> None:
    path = geoip_service.ensure_map_file_exists()

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "192.0.2.0/24 ZZ" in content


def test_ensure_map_file_exists_is_noop_when_already_present() -> None:
    path = geoip_service.map_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("custom content\n", encoding="utf-8")

    geoip_service.ensure_map_file_exists()

    assert path.read_text(encoding="utf-8") == "custom content\n"


# ---------------------------------------------------------------------------
# generate_map_file
# ---------------------------------------------------------------------------


def test_generate_map_file_writes_one_line_per_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mmdb = tmp_path / "fake.mmdb"
    mmdb.write_bytes(b"not a real mmdb, just needs to exist")
    entries = [
        (IPv4Network("1.0.0.0/24"), {"country": {"iso_code": "PL"}}),
        (IPv4Network("2.0.0.0/24"), {"registered_country": {"iso_code": "DE"}}),
        (IPv4Network("3.0.0.0/24"), {}),
        (IPv4Network("4.0.0.0/24"), {"country": {"iso_code": "XX"}}),
    ]
    monkeypatch.setattr(
        geoip_service.maxminddb,
        "open_database",
        lambda *args, **kwargs: _FakeReader(entries),
    )

    entries_written = geoip_service.generate_map_file(mmdb)

    assert entries_written == 2
    content = geoip_service.map_file_path().read_text(encoding="utf-8")
    assert "1.0.0.0/24 PL" in content
    assert "2.0.0.0/24 DE" in content
    assert "3.0.0.0/24" not in content
    assert "4.0.0.0/24" not in content
    # Atomic write: no leftover .tmp file.
    leftover = list(geoip_service.geoip_dir().glob("*.tmp"))
    assert leftover == []


def test_generate_map_file_missing_mmdb_writes_stub_and_returns_zero(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="app.services.geoip_service")
    missing = tmp_path / "does-not-exist.mmdb"

    entries_written = geoip_service.generate_map_file(missing)

    assert entries_written == 0
    assert geoip_service.map_file_path().exists()
    assert any("missing" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# download_database
# ---------------------------------------------------------------------------


def test_download_database_without_license_key_skips_http_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "maxmind_license_key", "")

    def _fail_if_called(*args: object, **kwargs: object) -> None:
        pytest.fail("httpx.get must not be called when unconfigured")

    monkeypatch.setattr(httpx, "get", _fail_if_called)

    with pytest.raises(geoip_service.GeoipNotConfiguredError):
        geoip_service.download_database()


def test_refresh_without_license_key_reports_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "maxmind_license_key", "")

    def _fail_if_called(*args: object, **kwargs: object) -> None:
        pytest.fail("httpx.get must not be called when unconfigured")

    monkeypatch.setattr(httpx, "get", _fail_if_called)

    result = geoip_service.refresh()

    assert result.configured is False
    assert result.downloaded is False


def _build_tarball(mmdb_bytes: bytes) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo(
            name="GeoLite2-Country_20260101/GeoLite2-Country.mmdb"
        )
        info.size = len(mmdb_bytes)
        archive.addfile(info, io.BytesIO(mmdb_bytes))
    return buffer.getvalue()


def test_download_database_happy_path_extracts_mmdb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "maxmind_license_key", "fake-license-key-abc123")
    mmdb_bytes = b"fake mmdb payload"
    tarball_bytes = _build_tarball(mmdb_bytes)

    def _fake_get(url: str, params=None, timeout=None, follow_redirects=None):
        return SimpleNamespace(
            content=tarball_bytes,
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(httpx, "get", _fake_get)

    result_path = geoip_service.download_database()

    assert result_path == geoip_service.mmdb_path()
    assert result_path.read_bytes() == mmdb_bytes
    leftover = list(geoip_service.geoip_dir().glob("*.tar.gz.tmp"))
    assert leftover == []


def test_download_database_never_logs_the_license_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "super-secret-license-99999"
    monkeypatch.setattr(settings, "maxmind_license_key", secret)
    caplog.set_level(logging.DEBUG)

    def _raise(*args: object, **kwargs: object) -> None:
        raise httpx.HTTPError("network down")

    monkeypatch.setattr(httpx, "get", _raise)

    with pytest.raises(httpx.HTTPError):
        geoip_service.download_database()

    for record in caplog.records:
        assert secret not in record.getMessage()
        if record.exc_text:
            assert secret not in record.exc_text


# ---------------------------------------------------------------------------
# refresh — reload triggering and error swallowing
# ---------------------------------------------------------------------------


def test_refresh_reloads_haproxy_when_map_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "maxmind_license_key", "key123")
    monkeypatch.setattr(
        geoip_service, "download_database", lambda: geoip_service.mmdb_path()
    )

    def _fake_generate(mmdb: Path | None = None) -> int:
        path = geoip_service.map_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("changed content\n", encoding="utf-8")
        return 1

    monkeypatch.setattr(geoip_service, "generate_map_file", _fake_generate)
    reload_mock = Mock(return_value=SimpleNamespace(ok=True, output="ok"))
    monkeypatch.setattr("app.services.config_apply.reload_haproxy", reload_mock)

    result = geoip_service.refresh()

    assert result.changed is True
    assert result.reloaded is True
    reload_mock.assert_called_once()


def test_refresh_does_not_reload_when_map_is_byte_identical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "maxmind_license_key", "key123")
    monkeypatch.setattr(
        geoip_service, "download_database", lambda: geoip_service.mmdb_path()
    )
    fixed_content = geoip_service._STUB_HEADER + "1.0.0.0/24 PL\n"

    def _fake_generate(mmdb: Path | None = None) -> int:
        path = geoip_service.map_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fixed_content, encoding="utf-8")
        return 1

    monkeypatch.setattr(geoip_service, "generate_map_file", _fake_generate)
    reload_mock = Mock(return_value=SimpleNamespace(ok=True, output="ok"))
    monkeypatch.setattr("app.services.config_apply.reload_haproxy", reload_mock)

    geoip_service.refresh()
    reload_mock.reset_mock()

    result = geoip_service.refresh()

    assert result.changed is False
    assert result.reloaded is False
    reload_mock.assert_not_called()


def test_refresh_swallows_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "maxmind_license_key", "key123")

    def _raise(*args: object, **kwargs: object) -> None:
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(geoip_service, "download_database", _raise)

    result = geoip_service.refresh()

    assert result.configured is True
    assert result.downloaded is False
    assert "GeoIP refresh failed" in result.message


def test_refresh_swallows_os_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "maxmind_license_key", "key123")

    def _raise(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(geoip_service, "download_database", _raise)

    result = geoip_service.refresh()

    assert result.configured is True
    assert result.downloaded is False
    assert "GeoIP refresh failed" in result.message
