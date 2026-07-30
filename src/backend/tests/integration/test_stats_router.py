"""Integration tests for the /stats dashboard aggregation endpoints."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.log import Log, LogAction, LogSeverity
from app.models.policy import Policy
from app.models.vhost import VHost
from app.services import ban_list_service, stats_service


def _seed_log(
    db: Session,
    *,
    minutes_ago: int,
    action: LogAction = LogAction.deny,
    severity: LogSeverity = LogSeverity.warning,
    source_ip: str = "203.0.113.5",
    rule_id: int | None = 942100,
    vhost: str = "app.example.com",
) -> Log:
    now = datetime.now(UTC).replace(tzinfo=None)
    log = Log(
        event_at=now - timedelta(minutes=minutes_ago),
        vhost=vhost,
        action=action,
        source_ip=source_ip,
        method="GET",
        request_uri="/",
        severity=severity,
        rule_id=rule_id,
        rule_message="SQL Injection Attack Detected",
    )
    db.add(log)
    return log


# --- auth --------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/stats/overview", "/stats/timeseries", "/stats/top"])
def test_stats_endpoints_require_auth(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 401


def test_unknown_window_is_rejected(
    client: TestClient, viewer_token: dict[str, str]
) -> None:
    response = client.get("/stats/overview?window=99d", headers=viewer_token)

    assert response.status_code == 422


# --- overview ----------------------------------------------------------------


def test_overview_counts_events_inside_the_window(
    client: TestClient,
    viewer_token: dict[str, str],
    db: Session,
) -> None:
    _seed_log(db, minutes_ago=10, action=LogAction.deny)
    _seed_log(db, minutes_ago=20, action=LogAction.deny, severity=LogSeverity.critical)
    _seed_log(db, minutes_ago=30, action=LogAction.allow)
    _seed_log(db, minutes_ago=40, action=LogAction.monitor)
    # Outside the 1h window — must not be counted as current.
    _seed_log(db, minutes_ago=90, action=LogAction.deny)
    db.commit()

    body = client.get("/stats/overview?window=1h", headers=viewer_token).json()

    assert body["window"] == "1h"
    assert body["requests"]["current"] == 4
    assert body["blocked"]["current"] == 2
    assert body["monitored"]["current"] == 1
    assert body["critical"]["current"] == 1


def test_overview_compares_against_the_previous_window(
    client: TestClient,
    viewer_token: dict[str, str],
    db: Session,
) -> None:
    for _ in range(4):
        _seed_log(db, minutes_ago=10, action=LogAction.deny)
    for _ in range(2):
        _seed_log(db, minutes_ago=90, action=LogAction.deny)
    db.commit()

    blocked = client.get("/stats/overview?window=1h", headers=viewer_token).json()[
        "blocked"
    ]

    assert blocked["current"] == 4
    assert blocked["previous"] == 2
    assert blocked["delta_pct"] == 100.0


def test_overview_delta_is_null_without_a_baseline(
    client: TestClient,
    viewer_token: dict[str, str],
    db: Session,
) -> None:
    _seed_log(db, minutes_ago=5, action=LogAction.deny)
    db.commit()

    body = client.get("/stats/overview?window=1h", headers=viewer_token).json()

    assert body["blocked"]["previous"] == 0
    assert body["blocked"]["delta_pct"] is None


def test_overview_counts_protected_vhosts_and_active_policies(
    client: TestClient,
    viewer_token: dict[str, str],
    db: Session,
) -> None:
    policy = Policy(name="Protective policy", is_active=True)
    inactive_policy = Policy(name="Draft policy", is_active=False)
    db.add_all([policy, inactive_policy])
    db.flush()
    db.add_all(
        [
            VHost(
                domain="guarded.example.com",
                backend_url="http://backend:8000",
                is_active=True,
                policy_id=policy.id,
            ),
            VHost(
                domain="bare.example.com",
                backend_url="http://backend:8000",
                is_active=True,
            ),
        ]
    )
    db.commit()

    body = client.get("/stats/overview", headers=viewer_token).json()

    assert body["protected_vhosts"] == 1
    assert body["total_vhosts"] == 2
    assert body["active_policies"] == 1


def test_overview_hides_banned_ips_from_viewers(
    client: TestClient, viewer_token: dict[str, str]
) -> None:
    """The ban list is admin-only, so viewers get null instead of a count."""
    body = client.get("/stats/overview", headers=viewer_token).json()

    assert body["banned_ips"] is None


def test_overview_returns_banned_ip_count_for_admin(
    client: TestClient,
    admin_token: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.security import BannedIpResponse

    entries = [
        BannedIpResponse(
            ip="203.0.113.5",
            vhost_id=1,
            domain="app.example.com",
            gpc0=99,
            ban_threshold=10,
            banned=True,
            expires_in_seconds=60,
        ),
        BannedIpResponse(
            ip="203.0.113.9",
            vhost_id=1,
            domain="app.example.com",
            gpc0=1,
            ban_threshold=10,
            banned=False,
            expires_in_seconds=60,
        ),
    ]
    monkeypatch.setattr(
        ban_list_service.BanListService, "list_banned", lambda self: entries
    )

    body = client.get("/stats/overview", headers=admin_token).json()

    assert body["banned_ips"] == 1


def test_overview_survives_an_unreachable_runtime_api(
    client: TestClient,
    admin_token: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead stats socket must degrade to null, not blank the whole dashboard."""

    def explode(self: object) -> list[object]:
        raise ban_list_service.RuntimeApiError("socket is gone")

    monkeypatch.setattr(ban_list_service.BanListService, "list_banned", explode)
    _seed_log(db, minutes_ago=5, action=LogAction.deny)
    db.commit()

    response = client.get("/stats/overview?window=1h", headers=admin_token)

    assert response.status_code == 200
    body = response.json()
    assert body["banned_ips"] is None
    assert body["blocked"]["current"] == 1


# --- timeseries --------------------------------------------------------------


def test_timeseries_returns_dense_buckets(
    client: TestClient,
    viewer_token: dict[str, str],
) -> None:
    body = client.get("/stats/timeseries?window=24h", headers=viewer_token).json()

    assert body["bucket_seconds"] == 3600
    assert len(body["buckets"]) == 24
    assert all(
        bucket["allow"] == 0 and bucket["deny"] == 0 and bucket["monitor"] == 0
        for bucket in body["buckets"]
    )


def test_timeseries_places_events_in_the_right_bucket(
    client: TestClient,
    viewer_token: dict[str, str],
    db: Session,
) -> None:
    _seed_log(db, minutes_ago=2, action=LogAction.deny)
    _seed_log(db, minutes_ago=2, action=LogAction.allow)
    _seed_log(db, minutes_ago=32, action=LogAction.monitor)
    db.commit()

    buckets = client.get("/stats/timeseries?window=1h", headers=viewer_token).json()[
        "buckets"
    ]

    assert sum(bucket["deny"] for bucket in buckets) == 1
    assert sum(bucket["allow"] for bucket in buckets) == 1
    assert sum(bucket["monitor"] for bucket in buckets) == 1
    # 5-minute buckets over an hour: the two recent events share the last one,
    # the 32-minutes-ago event sits roughly in the middle.
    assert buckets[-1]["deny"] == 1
    assert buckets[-1]["allow"] == 1
    assert buckets[5]["monitor"] == 1


def test_timeseries_bucket_timestamps_are_ordered_and_evenly_spaced(
    client: TestClient,
    viewer_token: dict[str, str],
) -> None:
    body = client.get("/stats/timeseries?window=7d", headers=viewer_token).json()
    stamps = [datetime.fromisoformat(b["bucket_at"]) for b in body["buckets"]]

    assert len(stamps) == 28
    gaps = {(b - a).total_seconds() for a, b in zip(stamps, stamps[1:], strict=False)}
    assert gaps == {float(body["bucket_seconds"])}


# --- top-N -------------------------------------------------------------------


def test_top_ranks_rules_ips_and_vhosts_by_denies(
    client: TestClient,
    viewer_token: dict[str, str],
    db: Session,
) -> None:
    for _ in range(3):
        _seed_log(db, minutes_ago=5, rule_id=942100, source_ip="203.0.113.5")
    _seed_log(db, minutes_ago=5, rule_id=941100, source_ip="203.0.113.9")
    # Allowed traffic must never show up in a "top threats" list.
    _seed_log(db, minutes_ago=5, action=LogAction.allow, source_ip="198.51.100.1")
    db.commit()

    body = client.get("/stats/top?window=1h", headers=viewer_token).json()

    assert [rule["rule_id"] for rule in body["rules"]] == [942100, 941100]
    assert body["rules"][0]["count"] == 3
    assert body["rules"][0]["rule_message"] == "SQL Injection Attack Detected"
    assert [ip["source_ip"] for ip in body["source_ips"]] == [
        "203.0.113.5",
        "203.0.113.9",
    ]
    assert body["vhosts"][0]["vhost"] == "app.example.com"
    assert body["vhosts"][0]["count"] == 4


def test_top_respects_the_limit(
    client: TestClient,
    viewer_token: dict[str, str],
    db: Session,
) -> None:
    for index in range(6):
        _seed_log(db, minutes_ago=5, source_ip=f"203.0.113.{index}")
    db.commit()

    body = client.get("/stats/top?window=1h&limit=3", headers=viewer_token).json()

    assert len(body["source_ips"]) == 3


def test_top_rejects_an_out_of_range_limit(
    client: TestClient, viewer_token: dict[str, str]
) -> None:
    assert client.get("/stats/top?limit=0", headers=viewer_token).status_code == 422
    assert client.get("/stats/top?limit=21", headers=viewer_token).status_code == 422


def test_top_marks_banned_ips_for_admins_only(
    client: TestClient,
    admin_token: dict[str, str],
    viewer_token: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.security import BannedIpResponse

    monkeypatch.setattr(
        ban_list_service.BanListService,
        "list_banned",
        lambda self: [
            BannedIpResponse(
                ip="203.0.113.5",
                vhost_id=1,
                domain="app.example.com",
                gpc0=99,
                ban_threshold=10,
                banned=True,
                expires_in_seconds=60,
            )
        ],
    )
    _seed_log(db, minutes_ago=5, source_ip="203.0.113.5")
    db.commit()

    as_admin = client.get("/stats/top?window=1h", headers=admin_token).json()
    as_viewer = client.get("/stats/top?window=1h", headers=viewer_token).json()

    assert as_admin["source_ips"][0]["is_banned"] is True
    assert as_viewer["source_ips"][0]["is_banned"] is False


def test_stats_service_clock_is_overridable(db: Session) -> None:
    """`now` injection keeps window maths testable without sleeping."""
    fixed = datetime(2026, 7, 29, 12, 0, 0)
    _seed_log(db, minutes_ago=0)
    db.commit()

    result = stats_service.StatsService(db).timeseries("24h", now=fixed)

    assert result.end_at == fixed
    assert result.start_at == fixed - timedelta(hours=24)
