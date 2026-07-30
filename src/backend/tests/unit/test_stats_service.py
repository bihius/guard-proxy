"""Unit tests for the dashboard aggregation helpers."""

from datetime import datetime, timedelta

import pytest

from app.services.stats_service import (
    WINDOW_SPECS,
    bucket_index_expression,
    compute_delta_pct,
    resolve_window,
)


@pytest.mark.parametrize(
    ("window", "span", "bucket", "count"),
    [
        ("1h", timedelta(hours=1), timedelta(minutes=5), 12),
        ("24h", timedelta(hours=24), timedelta(hours=1), 24),
        ("7d", timedelta(days=7), timedelta(hours=6), 28),
        ("30d", timedelta(days=30), timedelta(days=1), 30),
    ],
)
def test_window_specs_bucket_counts(
    window: str,
    span: timedelta,
    bucket: timedelta,
    count: int,
) -> None:
    spec = WINDOW_SPECS[window]  # type: ignore[index]

    assert spec.span == span
    assert spec.bucket == bucket
    assert spec.bucket_count == count


def test_resolve_window_uses_supplied_clock() -> None:
    now = datetime(2026, 7, 29, 12, 0, 0)

    start_at, end_at, spec = resolve_window("24h", now)

    assert end_at == now
    assert start_at == now - timedelta(hours=24)
    assert spec is WINDOW_SPECS["24h"]


def test_compute_delta_pct_positive_and_negative() -> None:
    assert compute_delta_pct(120, 100) == 20.0
    assert compute_delta_pct(80, 100) == -20.0
    assert compute_delta_pct(100, 100) == 0.0


def test_compute_delta_pct_is_none_without_baseline() -> None:
    """A jump from zero has no meaningful percentage — the UI shows 'new'."""
    assert compute_delta_pct(42, 0) is None
    assert compute_delta_pct(0, 0) is None


def test_bucket_index_expression_differs_per_dialect() -> None:
    """SQLite grouping must not silently leak into a Postgres deployment."""
    from app.models.log import Log

    sqlite_sql = str(bucket_index_expression("sqlite", Log.event_at, 0, 3600))
    postgres_sql = str(bucket_index_expression("postgresql", Log.event_at, 0, 3600))

    assert "strftime" in sqlite_sql
    assert "strftime" not in postgres_sql
