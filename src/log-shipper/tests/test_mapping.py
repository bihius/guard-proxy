"""Unit tests for the Coraza -> ingest payload mapping."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.mapping import coraza_event_to_ingest


def _base_event(**overrides: Any) -> dict[str, Any]:
    transaction: dict[str, Any] = {
        "id": "tx-123",
        "timestamp": "02/Jan/2026:15:04:05 +0000",
        "client_ip": "203.0.113.7",
        "is_interrupted": False,
        "request": {
            "method": "get",
            "uri": "/search?q=1",
            "headers": {"Host": "Example.COM"},
        },
        "response": {"status": 200},
        "variables": {"tx": {"anomaly_score": "5", "paranoia_level": "1"}},
    }
    transaction.update(overrides.pop("transaction", {}))
    event: dict[str, Any] = {
        "transaction": transaction,
        "messages": [
            {"data": {"id": "941100", "msg": "XSS Attack Detected", "severity": "2"}}
        ],
    }
    event.update(overrides)
    return event


def test_maps_core_fields() -> None:
    payload = coraza_event_to_ingest(_base_event())
    assert payload is not None
    assert payload["producer_event_id"] == "tx-123"
    assert payload["vhost"] == "example.com"
    assert payload["source_ip"] == "203.0.113.7"
    assert payload["method"] == "GET"
    assert payload["request_uri"] == "/search?q=1"
    assert payload["status_code"] == 200
    assert payload["rule_id"] == 941100
    assert payload["rule_message"] == "XSS Attack Detected"
    assert payload["anomaly_score"] == 5
    assert payload["paranoia_level"] == 1
    assert payload["raw_context"]["transaction"]["id"] == "tx-123"


def test_event_at_normalized_to_iso() -> None:
    payload = coraza_event_to_ingest(_base_event())
    assert payload is not None
    # Re-parseable as ISO 8601.
    datetime.fromisoformat(payload["event_at"])


def test_event_at_accepts_iso_input() -> None:
    event = _base_event(transaction={"timestamp": "2026-01-02T15:04:05Z"})
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["event_at"].startswith("2026-01-02T15:04:05")


def test_action_deny_when_interrupted() -> None:
    event = _base_event(transaction={"is_interrupted": True})
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["action"] == "deny"


def test_action_deny_when_high_severity() -> None:
    event = _base_event()
    event["messages"][0]["data"]["severity"] = "1"
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["action"] == "deny"
    assert payload["severity"] == "critical"


def test_action_allow_when_not_interrupted_and_low_severity() -> None:
    event = _base_event()
    event["messages"][0]["data"]["severity"] = "4"
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["action"] == "allow"
    assert payload["severity"] == "warning"


def test_severity_buckets() -> None:
    cases = {"0": "critical", "2": "error", "3": "warning", "5": "info"}
    for raw, expected in cases.items():
        event = _base_event()
        event["messages"][0]["data"]["severity"] = raw
        payload = coraza_event_to_ingest(event)
        assert payload is not None
        assert payload["severity"] == expected


def test_missing_messages_defaults_to_info_and_allow() -> None:
    event = _base_event(messages=[])
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["severity"] == "info"
    assert payload["action"] == "allow"
    assert payload["rule_id"] is None


def test_missing_response_yields_no_status() -> None:
    event = _base_event()
    del event["transaction"]["response"]
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["status_code"] is None


def test_out_of_range_status_dropped() -> None:
    event = _base_event(transaction={"response": {"status": 999}})
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["status_code"] is None


def test_missing_host_defaults_to_unknown() -> None:
    event = _base_event()
    event["transaction"]["request"]["headers"] = {}
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["vhost"] == "unknown"


def test_skips_event_without_client_ip() -> None:
    event = _base_event()
    del event["transaction"]["client_ip"]
    assert coraza_event_to_ingest(event) is None


def test_skips_event_with_invalid_client_ip() -> None:
    event = _base_event(transaction={"client_ip": "not-an-ip"})
    assert coraza_event_to_ingest(event) is None


def test_skips_event_without_method_or_uri() -> None:
    event = _base_event()
    event["transaction"]["request"]["method"] = ""
    assert coraza_event_to_ingest(event) is None


def test_skips_event_without_transaction() -> None:
    assert coraza_event_to_ingest({"messages": []}) is None


def test_absent_anomaly_score_is_none() -> None:
    event = _base_event(transaction={"variables": {}})
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["anomaly_score"] is None
    assert payload["paranoia_level"] is None
