"""Screenshot data must span chart windows without posing as real WAF evidence."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from random import Random

import pytest

from scripts.generate_demo_traffic import generate_events, run_live


def test_demo_events_cover_hosts_rules_actions_and_time_windows() -> None:
    now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
    hosts = ("shop.example.test", "api.example.test", "portal.example.test")

    events = generate_events(240, 48, hosts, now, "test-run")

    assert {event["vhost"] for event in events} == set(hosts)
    assert {event["rule_id"] for event in events} == {942100, 941100, 930100, 913100}
    assert {event["action"] for event in events} == {"deny", "monitor", "allow"}
    timestamps = [datetime.fromisoformat(str(event["event_at"])) for event in events]
    assert any(now - timedelta(minutes=5) < at <= now for at in timestamps)
    assert any(now - timedelta(hours=24) < at < now - timedelta(hours=1) for at in timestamps)
    assert any(at < now - timedelta(hours=24) for at in timestamps)
    assert all(
        event["raw_context"] == {"synthetic": True, "purpose": "dashboard screenshot"}
        for event in events
    )


def test_demo_events_can_be_replayed_without_creating_new_ids() -> None:
    now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)

    first = generate_events(20, 24, ("shop.example.test",), now, "same-run")
    again = generate_events(20, 24, ("shop.example.test",), now, "same-run")

    assert first == again
    assert len({event["producer_event_id"] for event in first}) == 20
    assert all(
        event["status_code"] == (403 if event["action"] == "deny" else 200)
        for event in first
    )


def test_live_demo_varies_chart_buckets_and_stops_at_one_hour() -> None:
    started = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
    elapsed = 0.0
    batches: list[list[dict[str, object]]] = []

    def now() -> datetime:
        return started + timedelta(seconds=elapsed)

    def wait(seconds: float) -> None:
        nonlocal elapsed
        elapsed += seconds

    def send(batch: list[dict[str, object]]) -> int:
        batches.append(batch)
        return len(batch)

    run_live(
        3600, ("shop.example.test", "api.example.test"), "live-run",
        send, rng=Random(7), now=now, clock=lambda: elapsed, wait=wait,
    )

    assert elapsed == 3600
    assert len(batches) == 23 + 12 + 60
    assert len({len(batch) for batch in batches[:23]}) > 1
    assert len({len(batch) for batch in batches[-60:]}) > 1
    events = [event for batch in batches for event in batch]
    assert len({event["producer_event_id"] for event in events}) == len(events)
    recent = [
        event for event in events
        if started - timedelta(hours=1) <= datetime.fromisoformat(str(event["event_at"])) < started
    ]
    buckets = Counter(
        int((started - datetime.fromisoformat(str(event["event_at"]))).total_seconds() // 300)
        for event in recent
    )
    assert set(buckets) == set(range(12))
    assert len(set(buckets.values())) > 1
    assert all(event["raw_context"]["synthetic"] is True for event in events)
    assert len({event["request_uri"] for event in events}) > 1


def test_live_demo_stops_on_ingest_failure() -> None:
    calls = 0

    def failing_send(batch: list[dict[str, object]]) -> int:
        nonlocal calls
        calls += 1
        raise RuntimeError("ingest unavailable")

    with pytest.raises(RuntimeError, match="ingest unavailable"):
        run_live(
            3600, ("shop.example.test",), "failed",
            failing_send, rng=Random(1),
            now=lambda: datetime(2026, 10, 10, tzinfo=timezone.utc),
            clock=lambda: 0,
            wait=lambda _: pytest.fail("must not wait after ingest failure"),
        )

    assert calls == 1
