"""Unit tests for app.services.geoip_service (issue #175).

No database, no HTTP layer — httpx and maxminddb are monkeypatched so these
tests run offline and never touch the real ip66.dev database.
"""

from __future__ import annotations

import json
import logging
import os
from ipaddress import IPv4Network, IPv6Network
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

    def __init__(self, entries: list[tuple[object, dict]]) -> None:
        self._entries = entries

    def __enter__(self) -> _FakeReader:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def __iter__(self):
        return iter(self._entries)


class _FakeStreamResponse:
    """Stand-in for the context manager returned by `httpx.stream()`."""

    def __init__(
        self,
        status_code: int,
        content: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._content = content
        self.headers = headers or {}

    def __enter__(self) -> _FakeStreamResponse:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error", request=Mock(), response=Mock(status_code=self.status_code)
            )

    def iter_bytes(self, chunk_size: int):
        yield self._content


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


def test_generate_map_file_collapses_adjacent_networks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mmdb = tmp_path / "fake.mmdb"
    mmdb.write_bytes(b"not a real mmdb, just needs to exist")
    # Two adjacent /24s for the same country collapse into a single /23.
    entries = [
        (IPv4Network("10.0.0.0/24"), {"country": {"iso_code": "PL"}}),
        (IPv4Network("10.0.1.0/24"), {"country": {"iso_code": "PL"}}),
    ]
    monkeypatch.setattr(
        geoip_service.maxminddb,
        "open_database",
        lambda *args, **kwargs: _FakeReader(entries),
    )

    entries_written = geoip_service.generate_map_file(mmdb)

    assert entries_written == 1
    content = geoip_service.map_file_path().read_text(encoding="utf-8")
    assert "10.0.0.0/23 PL" in content


def test_generate_map_file_does_not_mix_ip_versions_when_collapsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mmdb = tmp_path / "fake.mmdb"
    mmdb.write_bytes(b"not a real mmdb, just needs to exist")
    entries = [
        (IPv4Network("10.0.0.0/24"), {"country": {"iso_code": "PL"}}),
        (IPv6Network("2001:db8::/32"), {"country": {"iso_code": "PL"}}),
    ]
    monkeypatch.setattr(
        geoip_service.maxminddb,
        "open_database",
        lambda *args, **kwargs: _FakeReader(entries),
    )

    # Must not raise TypeError from mixing IPv4/IPv6 in collapse_addresses().
    entries_written = geoip_service.generate_map_file(mmdb)

    assert entries_written == 2
    content = geoip_service.map_file_path().read_text(encoding="utf-8")
    assert "10.0.0.0/24 PL" in content
    assert "2001:db8::/32 PL" in content


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


def test_download_database_happy_path_writes_mmdb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mmdb_bytes = b"fake mmdb payload"

    def _fake_stream(
        method: str, url: str, headers=None, timeout=None, follow_redirects=None
    ):
        assert method == "GET"
        assert url == settings.geoip_database_url
        assert headers == {}
        return _FakeStreamResponse(
            200, content=mmdb_bytes, headers={"ETag": '"abc123"'}
        )

    monkeypatch.setattr(httpx, "stream", _fake_stream)

    result_path, downloaded = geoip_service.download_database()

    assert downloaded is True
    assert result_path == geoip_service.mmdb_path()
    assert result_path.read_bytes() == mmdb_bytes
    leftover = list(geoip_service.geoip_dir().glob("*.tmp"))
    assert leftover == []


def test_download_database_persists_conditional_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_stream(
        method: str, url: str, headers=None, timeout=None, follow_redirects=None
    ):
        return _FakeStreamResponse(
            200,
            content=b"payload",
            headers={
                "ETag": '"abc123"',
                "Last-Modified": "Tue, 01 Jul 2026 00:00:00 GMT",
            },
        )

    monkeypatch.setattr(httpx, "stream", _fake_stream)

    geoip_service.download_database()

    meta = json.loads(geoip_service._meta_path().read_text(encoding="utf-8"))
    assert meta["etag"] == '"abc123"'
    assert meta["last_modified"] == "Tue, 01 Jul 2026 00:00:00 GMT"


def test_download_database_sends_conditional_headers_on_second_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    geoip_service.mmdb_path().parent.mkdir(parents=True, exist_ok=True)
    geoip_service.mmdb_path().write_bytes(b"old payload")
    geoip_service._meta_path().write_text(
        json.dumps(
            {"etag": '"abc123"', "last_modified": "Tue, 01 Jul 2026 00:00:00 GMT"}
        ),
        encoding="utf-8",
    )

    captured_headers: dict[str, str] = {}

    def _fake_stream(
        method: str, url: str, headers=None, timeout=None, follow_redirects=None
    ):
        captured_headers.update(headers or {})
        return _FakeStreamResponse(304)

    monkeypatch.setattr(httpx, "stream", _fake_stream)

    result_path, downloaded = geoip_service.download_database()

    assert downloaded is False
    assert result_path == geoip_service.mmdb_path()
    assert captured_headers["If-None-Match"] == '"abc123"'
    assert captured_headers["If-Modified-Since"] == "Tue, 01 Jul 2026 00:00:00 GMT"
    # The existing database is left untouched on a 304.
    assert result_path.read_bytes() == b"old payload"


def test_download_database_raises_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_stream(
        method: str, url: str, headers=None, timeout=None, follow_redirects=None
    ):
        return _FakeStreamResponse(500)

    monkeypatch.setattr(httpx, "stream", _fake_stream)

    with pytest.raises(httpx.HTTPError):
        geoip_service.download_database()

    leftover = list(geoip_service.geoip_dir().glob("*.tmp"))
    assert leftover == []


# ---------------------------------------------------------------------------
# refresh — reload triggering and error swallowing
# ---------------------------------------------------------------------------


def test_refresh_reloads_haproxy_when_map_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        geoip_service, "download_database", lambda: (geoip_service.mmdb_path(), True)
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

    assert result.downloaded is True
    assert result.changed is True
    assert result.reloaded is True
    reload_mock.assert_called_once()


def test_refresh_does_not_regenerate_or_reload_when_not_modified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_content = geoip_service._STUB_HEADER + "1.0.0.0/24 PL\n"
    geoip_service.map_file_path().parent.mkdir(parents=True, exist_ok=True)
    geoip_service.map_file_path().write_text(fixed_content, encoding="utf-8")

    monkeypatch.setattr(
        geoip_service, "download_database", lambda: (geoip_service.mmdb_path(), False)
    )
    generate_mock = Mock()
    monkeypatch.setattr(geoip_service, "generate_map_file", generate_mock)
    reload_mock = Mock(return_value=SimpleNamespace(ok=True, output="ok"))
    monkeypatch.setattr("app.services.config_apply.reload_haproxy", reload_mock)

    result = geoip_service.refresh()

    assert result.downloaded is False
    assert result.changed is False
    assert result.reloaded is False
    generate_mock.assert_not_called()
    reload_mock.assert_not_called()


def test_refresh_regenerates_when_map_is_still_a_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 304 must not leave a stub map in place.

    The MMDB can be current while the map is not — first boot after an
    upgrade, a wiped volume, or a generation that failed last run. Reporting
    "up to date" there would leave every lookup missing, silently failing open.
    """
    geoip_service.ensure_map_file_exists()
    assert geoip_service._map_is_stub()

    monkeypatch.setattr(
        geoip_service, "download_database", lambda: (geoip_service.mmdb_path(), False)
    )
    generate_mock = Mock(return_value=7)
    monkeypatch.setattr(geoip_service, "generate_map_file", generate_mock)

    result = geoip_service.refresh(force_reload=False)

    assert result.downloaded is False
    generate_mock.assert_called_once()
    assert result.entries == 7


def test_refresh_reports_failed_reload_when_map_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    geoip_service.map_file_path().parent.mkdir(parents=True, exist_ok=True)
    geoip_service.map_file_path().write_text(
        geoip_service._STUB_HEADER + "1.0.0.0/24 PL\n", encoding="utf-8"
    )

    monkeypatch.setattr(
        geoip_service, "download_database", lambda: (geoip_service.mmdb_path(), True)
    )

    def _generate() -> int:
        geoip_service.map_file_path().write_text(
            geoip_service._STUB_HEADER + "2.0.0.0/24 DE\n", encoding="utf-8"
        )
        return 1

    monkeypatch.setattr(geoip_service, "generate_map_file", _generate)
    reload_mock = Mock(return_value=SimpleNamespace(ok=False, output="reload failed"))
    monkeypatch.setattr("app.services.config_apply.reload_haproxy", reload_mock)

    result = geoip_service.refresh()

    assert result.changed is True
    assert result.reloaded is False
    reload_mock.assert_called_once()


def test_generate_map_file_reports_unusable_reader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The pure Python maxminddb reader cannot enumerate the real database.

    It raises "ValueError: ::1:0:0/0 has host bits set" partway through, so
    that must surface as an actionable GeoipError rather than an opaque crash.
    """
    mmdb = tmp_path / "country.mmdb"
    mmdb.write_bytes(b"not-a-real-mmdb")

    class _Reader:
        def __enter__(self) -> _Reader:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def __iter__(self) -> object:
            raise ValueError("::1:0:0/0 has host bits set")

    monkeypatch.setattr(
        geoip_service.maxminddb, "open_database", lambda *a, **kw: _Reader()
    )

    with pytest.raises(geoip_service.GeoipError, match="maxminddb C extension"):
        geoip_service.generate_map_file(mmdb)


def test_refresh_swallows_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args: object, **kwargs: object) -> None:
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(geoip_service, "download_database", _raise)

    result = geoip_service.refresh()

    assert result.downloaded is False
    assert "GeoIP refresh failed" in result.message


def test_refresh_swallows_os_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(geoip_service, "download_database", _raise)

    result = geoip_service.refresh()

    assert result.downloaded is False
    assert "GeoIP refresh failed" in result.message
