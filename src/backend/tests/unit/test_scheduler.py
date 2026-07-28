"""Unit tests for the GeoIP parts of app.services.scheduler (issue #175)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.services import scheduler as scheduler_module


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
