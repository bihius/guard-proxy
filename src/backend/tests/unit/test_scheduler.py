"""Unit tests for app.services.scheduler.

Covers the GeoIP refresh job (issue #175) and ACME contact selection during
certificate renewal.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.models.vhost import VHost
from app.services import config_apply, config_generator
from app.services import scheduler as scheduler_module
from app.services.vhost_service import VHostService


def test_refresh_geoip_database_logs_the_result(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    result = SimpleNamespace(message="GeoIP database refreshed: 5 entries written.")
    monkeypatch.setattr(
        scheduler_module.geoip_service, "refresh", lambda: result, raising=True
    )

    with caplog.at_level(logging.INFO):
        scheduler_module.refresh_geoip_database()

    assert "GeoIP refresh: GeoIP database refreshed: 5 entries written." in caplog.text


def test_refresh_geoip_database_does_not_swallow_scheduler_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`geoip_service.refresh()` is documented as never raising.

    If that ever changes the job should surface the error to APScheduler
    rather than the wrapper hiding it, so this pins the wrapper's behaviour.
    """

    def _boom() -> None:
        raise RuntimeError("refresh exploded")

    monkeypatch.setattr(scheduler_module.geoip_service, "refresh", _boom, raising=True)

    with pytest.raises(RuntimeError, match="refresh exploded"):
        scheduler_module.refresh_geoip_database()


def test_start_scheduler_schedules_an_initial_geoip_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without next_run_time the map stays a stub for a whole interval.

    An interval job's first run is one interval after start, so on every boot
    the country map would remain the empty stub — silently failing open — for
    a full refresh interval.
    """
    jobs: list[tuple[tuple[object, ...], dict[str, object]]] = []

    monkeypatch.setattr(
        scheduler_module.scheduler,
        "add_job",
        lambda *args, **kwargs: jobs.append((args, kwargs)),
    )
    monkeypatch.setattr(scheduler_module.scheduler, "start", lambda: None)

    before = datetime.now(UTC)
    scheduler_module.start_scheduler()

    geoip_jobs = [kw for _, kw in jobs if kw.get("id") == "refresh_geoip_database"]
    assert len(geoip_jobs) == 1
    next_run_time = geoip_jobs[0]["next_run_time"]
    assert isinstance(next_run_time, datetime)
    assert next_run_time > before


class _FakeQuery:
    """Minimal SQLAlchemy query stand-in returning a fixed row list."""

    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def filter(self, *args: object, **kwargs: object) -> _FakeQuery:
        return self

    def all(self) -> list[object]:
        return self._rows


class _FakeSession:
    """Session stand-in: VHost queries return the fixtures, others return none."""

    def __init__(self, vhosts: list[object]) -> None:
        self._vhosts = vhosts
        self.committed = False

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def query(self, model: object, *args: object) -> _FakeQuery:
        return _FakeQuery(self._vhosts if model is VHost else [])

    def commit(self) -> None:
        self.committed = True


class _FakeCertbot:
    """Records the contact each `provision_cert` call registers with."""

    calls: list[tuple[str, str]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def provision_cert(self, domain: str, email: str) -> tuple[str, str]:
        _FakeCertbot.calls.append((domain, email))
        return "cert-pem", "key-pem"


def _renew_one(
    monkeypatch: pytest.MonkeyPatch,
    *,
    domain: str,
    acme_contact_email: str | None,
) -> list[tuple[str, str]]:
    """Run the renewal job over a single expiring vhost, return its certbot calls."""
    _FakeCertbot.calls = []
    vhost = SimpleNamespace(
        domain=domain,
        acme_contact_email=acme_contact_email,
        ssl_expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        ssl_cert=None,
        ssl_key=None,
    )
    monkeypatch.setattr(
        scheduler_module, "SessionLocal", lambda: _FakeSession([vhost])
    )
    monkeypatch.setattr(scheduler_module, "CertbotService", _FakeCertbot)
    monkeypatch.setattr(
        VHostService, "_parse_cert_expiration", staticmethod(lambda cert: None)
    )
    monkeypatch.setattr(config_generator, "generate", lambda *args, **kwargs: None)
    monkeypatch.setattr(config_apply, "apply", lambda generated: None)

    scheduler_module.renew_certificates()
    return _FakeCertbot.calls


def test_renew_certificates_uses_the_contact_stored_at_issuance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _renew_one(
        monkeypatch,
        domain="app.example.com",
        acme_contact_email="owner@example.com",
    )

    assert calls == [("app.example.com", "owner@example.com")]


def test_renew_certificates_falls_back_for_vhosts_without_a_stored_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rows issued before the snapshot column existed keep the old behaviour."""
    calls = _renew_one(
        monkeypatch,
        domain="legacy.example.com",
        acme_contact_email=None,
    )

    assert calls == [("legacy.example.com", "admin@legacy.example.com")]
