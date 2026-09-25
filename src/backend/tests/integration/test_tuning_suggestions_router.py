"""Integration tests for learning-mode tuning suggestions (issue #263)."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.log import Log, LogAction, LogSeverity
from app.models.policy import PolicyEnforcementMode
from app.services.tuning_service import analyze_detect_only_policies

_NOW = datetime.now(UTC).replace(tzinfo=None)


def _match(rule_id: int, data: str) -> dict[str, object]:
    """One coraza-spoa 0.6.1 message in the format it really emits."""
    return {
        "error_message": (
            f'Coraza: Warning. [id "{rule_id}"] [msg "Rule {rule_id}"] '
            f'[data "{data}"] [severity "critical"]'
        ),
        "data": None,
    }


# Anomaly evaluation: fires alongside every blocked request, matches no target.
_EVALUATION = _match(949110, "")


def _create_policy(
    client: TestClient, headers: dict[str, str], name: str = "Learning"
) -> int:
    resp = client.post(
        "/policies",
        headers=headers,
        json={
            "name": name,
            "paranoia_level": 1,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 4,
            "enforcement_mode": "detect_only",
        },
    )
    assert resp.status_code == 201
    return int(resp.json()["id"])


def _log(
    db: Session,
    policy_id: int,
    *messages: dict[str, object],
    uri: str = "/search?q=x",
    ip: str = "203.0.113.1",
    hours_ago: float = 1,
) -> Log:
    log = Log(
        event_at=_NOW - timedelta(hours=hours_ago),
        vhost="app.local",
        action=LogAction.monitor,
        source_ip=ip,
        method="GET",
        request_uri=uri,
        severity=LogSeverity.critical,
        raw_context={"messages": list(messages)},
        policy_id=policy_id,
    )
    db.add(log)
    db.commit()
    return log


def _false_positive_traffic(db: Session, policy_id: int) -> None:
    """942100 on ARGS:q from many clients across hours, rule firing alone."""
    for i in range(6):
        _log(
            db,
            policy_id,
            _match(942100, "Matched Data: s&1c found within ARGS:q: o'brien"),
            _EVALUATION,
            uri=f"/search?q={i}",
            ip=f"203.0.113.{i}",
            hours_ago=i + 1,
        )


def _analyze(client: TestClient, headers: dict[str, str], policy_id: int) -> dict:
    resp = client.post(f"/policies/{policy_id}/suggestions/analyze", headers=headers)
    assert resp.status_code == 200
    return resp.json()


def test_analysis_suggests_exclusion_for_repeated_single_rule_matches(
    client: TestClient, db: Session, admin_token: dict[str, str]
) -> None:
    policy_id = _create_policy(client, admin_token)
    _false_positive_traffic(db, policy_id)
    # Too rare to suggest: below the minimum event count.
    _log(db, policy_id, _match(941100, "Matched Data: x found within ARGS:bio: <b>"))

    result = _analyze(client, admin_token, policy_id)
    suggestions = client.get(
        f"/policies/{policy_id}/suggestions", headers=admin_token
    ).json()

    assert (result["events_scanned"], result["created"]) == (7, 1)
    [suggestion] = suggestions
    assert (
        suggestion["rule_id"],
        suggestion["target_type"],
        suggestion["target_value"],
        suggestion["scope_path"],
    ) == (942100, "args", "q", "/search")
    assert (suggestion["event_count"], suggestion["source_ip_count"]) == (6, 6)
    assert suggestion["confidence"] >= 70
    assert len(suggestion["sample_log_ids"]) == 5


def _two_rule_event(db: Session, policy_id: int, ip: str, hours_ago: float) -> None:
    _log(
        db,
        policy_id,
        _match(930100, "Matched Data: /../ found within REQUEST_URI_RAW: /?f=../x"),
        _match(930120, "Matched Data: etc/passwd found within ARGS:f: ../x"),
        _EVALUATION,
        uri="/?f=../etc/passwd",
        ip=ip,
        hours_ago=hours_ago,
    )


def test_every_rule_in_an_event_is_considered_not_only_the_primary_one(
    client: TestClient, db: Session, admin_token: dict[str, str]
) -> None:
    policy_id = _create_policy(client, admin_token)
    for i in range(6):
        _two_rule_event(db, policy_id, ip=f"203.0.113.{i}", hours_ago=i + 1)

    _analyze(client, admin_token, policy_id)
    suggestions = client.get(
        f"/policies/{policy_id}/suggestions", headers=admin_token
    ).json()

    targets = {(s["rule_id"], s["target_type"], s["target_value"]) for s in suggestions}
    assert targets == {(930100, "request_uri_raw", None), (930120, "args", "f")}


def test_single_client_attack_burst_is_not_suggested(
    client: TestClient, db: Session, admin_token: dict[str, str]
) -> None:
    """One client, one burst, several rules at once: an attack, not a false positive."""
    policy_id = _create_policy(client, admin_token)
    for _ in range(5):
        _two_rule_event(db, policy_id, ip="198.51.100.66", hours_ago=0.1)

    assert _analyze(client, admin_token, policy_id)["created"] == 0


def test_reanalysis_refreshes_instead_of_duplicating(
    client: TestClient, db: Session, admin_token: dict[str, str]
) -> None:
    policy_id = _create_policy(client, admin_token)
    _false_positive_traffic(db, policy_id)
    _analyze(client, admin_token, policy_id)
    _log(
        db,
        policy_id,
        _match(942100, "Matched Data: s&1c found within ARGS:q: x"),
        uri="/search/advanced?q=1",
        ip="198.51.100.9",
        hours_ago=0.5,
    )

    second = _analyze(client, admin_token, policy_id)
    [suggestion] = client.get(
        f"/policies/{policy_id}/suggestions", headers=admin_token
    ).json()

    assert (second["created"], second["updated"]) == (0, 1)
    assert suggestion["event_count"] == 7
    assert suggestion["scope_path"] == "/search"


def test_approve_creates_the_reviewed_exclusion_and_rejected_stays_rejected(
    client: TestClient, db: Session, admin_token: dict[str, str]
) -> None:
    policy_id = _create_policy(client, admin_token)
    _false_positive_traffic(db, policy_id)
    for _ in range(3):
        _log(db, policy_id, _match(941100, "Matched Data: x found within ARGS:bio: x"))
    _analyze(client, admin_token, policy_id)
    by_rule = {
        s["rule_id"]: s
        for s in client.get(
            f"/policies/{policy_id}/suggestions", headers=admin_token
        ).json()
    }
    base = f"/policies/{policy_id}/suggestions"

    # The admin narrows the scope before approving.
    approved = client.post(
        f"{base}/{by_rule[942100]['id']}/approve",
        headers=admin_token,
        json={
            "rule_id": 942100,
            "target_type": "args",
            "target_value": "q",
            "scope_path": "/search/basic",
            "comment": "Names with apostrophes",
        },
    )
    rejected = client.post(
        f"{base}/{by_rule[941100]['id']}/reject", headers=admin_token
    )
    again = client.post(f"{base}/{by_rule[942100]['id']}/reject", headers=admin_token)

    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert rejected.json()["status"] == "rejected"
    assert again.status_code == 409
    [exclusion] = client.get(
        f"/policies/{policy_id}/exclusions", headers=admin_token
    ).json()
    assert exclusion["id"] == approved.json()["rule_exclusion_id"]
    assert (exclusion["scope_path"], exclusion["comment"]) == (
        "/search/basic",
        "Names with apostrophes",
    )

    for _ in range(3):
        _log(db, policy_id, _match(941100, "Matched Data: x found within ARGS:bio: x"))
    rerun = _analyze(client, admin_token, policy_id)
    assert rerun["created"] == 0
    assert client.get(base, headers=admin_token).json() == []


def test_analysis_skips_targets_already_excluded(
    client: TestClient, db: Session, admin_token: dict[str, str]
) -> None:
    policy_id = _create_policy(client, admin_token)
    client.post(
        f"/policies/{policy_id}/exclusions",
        headers=admin_token,
        json={"rule_id": 942100, "target_type": "args", "target_value": "q"},
    )
    _false_positive_traffic(db, policy_id)

    assert _analyze(client, admin_token, policy_id)["created"] == 0


@pytest.mark.parametrize(
    ("exclusion_scope", "traffic_path", "created"),
    [
        # Shares a string prefix but is a different path: not covered.
        ("/api", "/apiv2/foo", 1),
        ("/api", "/api", 0),
        ("/api", "/api/foo", 0),
        # A trailing-slash scope, as common_scope_path produces, covers
        # everything under it.
        ("/api/", "/api/foo", 0),
        ("/api/", "/api", 1),
    ],
)
def test_existing_scoped_exclusion_covers_only_its_own_path_segments(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
    exclusion_scope: str,
    traffic_path: str,
    created: int,
) -> None:
    policy_id = _create_policy(client, admin_token)
    resp = client.post(
        f"/policies/{policy_id}/exclusions",
        headers=admin_token,
        json={
            "rule_id": 942100,
            "target_type": "args",
            "target_value": "q",
            "scope_path": exclusion_scope,
        },
    )
    assert resp.status_code == 201
    for i in range(6):
        _log(
            db,
            policy_id,
            _match(942100, "Matched Data: s&1c found within ARGS:q: o'brien"),
            uri=f"{traffic_path}?q={i}",
            ip=f"203.0.113.{i}",
            hours_ago=i + 1,
        )

    assert _analyze(client, admin_token, policy_id)["created"] == created


def test_writes_are_admin_only(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    policy_id = _create_policy(client, admin_token)
    base = f"/policies/{policy_id}/suggestions"

    assert client.get(base, headers=viewer_token).status_code == 200
    assert client.post(f"{base}/analyze", headers=viewer_token).status_code == 403
    assert client.post(f"{base}/1/reject", headers=viewer_token).status_code == 403
    assert (
        client.post(
            "/policies/999999/suggestions/analyze", headers=admin_token
        ).status_code
        == 404
    )
    assert client.post(f"{base}/999999/reject", headers=admin_token).status_code == 404


def test_nightly_job_only_learns_from_detect_only_policies(
    client: TestClient, db: Session, admin_token: dict[str, str]
) -> None:
    learning = _create_policy(client, admin_token, name="Learning")
    blocking = _create_policy(client, admin_token, name="Blocking")
    client.patch(
        f"/policies/{blocking}",
        headers=admin_token,
        json={"enforcement_mode": PolicyEnforcementMode.block.value},
    )
    _false_positive_traffic(db, learning)
    _false_positive_traffic(db, blocking)
    # Outside the one-day window.
    for i in range(3):
        _log(
            db,
            learning,
            _match(941100, "Matched Data: x found within ARGS:bio: x"),
            ip=f"198.51.100.{i}",
            hours_ago=30,
        )

    results = analyze_detect_only_policies(db, window=timedelta(days=1))

    assert set(results) == {learning}
    assert (results[learning].events_scanned, results[learning].created) == (6, 1)
