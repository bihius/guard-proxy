"""Integration tests for POST /logs/{log_id}/suggest-exclusion (issue #264)."""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.log import Log, LogAction, LogSeverity

_XSS_MESSAGE = (
    '[client "192.168.107.1"] Coraza: Warning. XSS Attack Detected via libinjection '
    '[id "941100"] [rev ""] [msg "XSS Attack Detected via libinjection"] '
    '[data "Matched Data: XSS data found within ARGS:q: <script>alert(1)</script>"] '
    '[severity "critical"]'
)


def _create_policy(client: TestClient, headers: dict[str, str]) -> int:
    resp = client.post(
        "/policies",
        headers=headers,
        json={
            "name": "Suggestion policy",
            "paranoia_level": 1,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 4,
        },
    )
    assert resp.status_code == 201
    return int(resp.json()["id"])


def _create_log(
    db: Session,
    *,
    policy_id: int | None,
    rule_id: int | None = 941100,
) -> Log:
    log = Log(
        event_at=datetime(2026, 9, 24, 15, 57),
        vhost="juice.local",
        action=LogAction.deny,
        source_ip="192.168.107.1",
        method="GET",
        request_uri="/search?q=<script>alert(1)</script>",
        rule_id=rule_id,
        rule_message="XSS Attack Detected via libinjection",
        severity=LogSeverity.critical,
        raw_context={"messages": [{"error_message": _XSS_MESSAGE, "data": None}]},
        policy_id=policy_id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def test_suggestion_can_be_saved_as_an_exclusion(
    client: TestClient, db: Session, admin_token: dict[str, str]
) -> None:
    """Full flow: event -> suggestion -> exclusion created under the event's policy."""
    policy_id = _create_policy(client, admin_token)
    log = _create_log(db, policy_id=policy_id)

    resp = client.post(f"/logs/{log.id}/suggest-exclusion", headers=admin_token)

    assert resp.status_code == 200
    suggestion = resp.json()
    assert suggestion == {
        "policy_id": policy_id,
        "rule_id": 941100,
        "target_type": "args",
        "target_value": "q",
        "scope_path": "/search",
        "comment": f"Created from log #{log.id}: XSS Attack Detected via libinjection",
        "matched_variable": "ARGS:q",
    }

    body = {
        k: suggestion[k]
        for k in ("rule_id", "target_type", "target_value", "scope_path", "comment")
    }
    created = client.post(
        f"/policies/{policy_id}/exclusions", headers=admin_token, json=body
    )
    assert created.status_code == 201
    listed = client.get(f"/policies/{policy_id}/exclusions", headers=admin_token).json()
    assert [(e["rule_id"], e["target_value"]) for e in listed] == [(941100, "q")]


def test_suggest_exclusion_is_admin_only(
    client: TestClient,
    db: Session,
    admin_token: dict[str, str],
    viewer_token: dict[str, str],
) -> None:
    log = _create_log(db, policy_id=_create_policy(client, admin_token))

    assert (
        client.post(
            f"/logs/{log.id}/suggest-exclusion", headers=viewer_token
        ).status_code
        == 403
    )
    assert client.post(f"/logs/{log.id}/suggest-exclusion").status_code == 401


def test_suggest_exclusion_unknown_log_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    assert (
        client.post("/logs/999999/suggest-exclusion", headers=admin_token).status_code
        == 404
    )


def test_suggest_exclusion_requires_a_rule_and_a_policy(
    client: TestClient, db: Session, admin_token: dict[str, str]
) -> None:
    policy_id = _create_policy(client, admin_token)
    without_rule = _create_log(db, policy_id=policy_id, rule_id=None)
    without_policy = _create_log(db, policy_id=None)

    no_rule = client.post(
        f"/logs/{without_rule.id}/suggest-exclusion", headers=admin_token
    )
    no_policy = client.post(
        f"/logs/{without_policy.id}/suggest-exclusion", headers=admin_token
    )

    assert no_rule.status_code == 422
    assert "no matched rule" in no_rule.json()["detail"]
    assert no_policy.status_code == 422
    assert "no policy" in no_policy.json()["detail"]
