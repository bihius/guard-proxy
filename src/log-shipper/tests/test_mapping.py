"""Unit tests for the Coraza -> ingest payload mapping."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.mapping import coraza_event_to_ingest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_message(rule_id: str = "941100",
                   msg: str = "XSS Attack Detected via libinjection",
                   severity: str = "critical") -> str:
    """Build a realistic coraza-spoa error_message string."""
    return (
        f'[client "203.0.113.7"] Coraza: Warning. {msg} '
        f'[file "/etc/coraza/crs/rules/REQUEST-941.conf"] [line "7791"] '
        f'[id "{rule_id}"] [rev ""] [msg "{msg}"] '
        f'[data "Matched Data: ..."] [severity "{severity}"] '
        f'[ver "OWASP_CRS/4.25.0"] [hostname "example.com"] '
        f'[uri "/search?q=foo"] [unique_id "tx-123"]'
    )


def _message_entry(rule_id: str = "941100",
                   msg: str = "XSS Attack Detected via libinjection",
                   severity: str = "critical") -> dict[str, Any]:
    """Build an actual coraza-spoa v0.6.1 message dict (data is null)."""
    return {
        "actionset": "",
        "message": "",
        "error_message": _error_message(rule_id, msg, severity),
        "data": None,
    }


def _base_event(**overrides: Any) -> dict[str, Any]:
    """Minimal event that mirrors actual coraza-spoa v0.6.1 JSON output."""
    transaction: dict[str, Any] = {
        "id": "tx-123",
        # Actual format: "YYYY/MM/DD HH:MM:SS" — no ISO 8601, no timezone.
        "timestamp": "2026/05/31 13:29:17",
        "client_ip": "203.0.113.7",
        "is_interrupted": False,
        "request": {
            "method": "get",
            "uri": "/search?q=1",
            # Actual format: header values are lists.
            "headers": {"Host": ["Example.COM"]},
        },
        "response": {"status": 200},
    }
    transaction.update(overrides.pop("transaction", {}))
    event: dict[str, Any] = {
        "transaction": transaction,
        "messages": [_message_entry()],
    }
    event.update(overrides)
    return event


# ---------------------------------------------------------------------------
# Real-world event fixture (captured from actual coraza-spoa v0.6.1 output)
# ---------------------------------------------------------------------------

_REAL_EVENT: dict[str, Any] = {
    "transaction": {
        "timestamp": "2026/05/31 13:29:17",
        "unix_timestamp": 1780234157503639608,
        "id": "76d5cec7-bcbb-4742-8d78-6ab51fac2d06",
        "client_ip": "192.168.107.1",
        "client_port": 56306,
        "host_ip": "192.168.107.3",
        "host_port": 80,
        "server_id": "localhost:8080",
        "request": {
            "method": "GET",
            "protocol": "HTTP/1.1",
            "uri": "/?q=<script>alert(1)</script>",
            "http_version": "",
            "headers": {
                "accept": ["*/*"],
                "host": ["localhost:8080"],
                "user-agent": ["curl/8.7.1"],
            },
            "body": "",
            "files": None,
            "args": {},
            "length": 0,
        },
        "response": {"protocol": "", "status": 0, "headers": {}, "body": ""},
        "producer": {"connector": "", "version": "", "server": "",
                     "rule_engine": "On", "stopwatch": "", "rulesets": ["OWASP_CRS/4.25.0"]},
        "highest_severity": "",
        "is_interrupted": True,
    },
    "messages": [
        {
            "actionset": "", "message": "",
            "error_message": (
                '[client "192.168.107.1"] Coraza: Warning. XSS Attack Detected via libinjection '
                '[file "/etc/coraza/crs/rules/REQUEST-941-APPLICATION-ATTACK-XSS.conf"] '
                '[line "7791"] [id "941100"] [rev ""] [msg "XSS Attack Detected via libinjection"] '
                '[data "Matched Data: XSS data found within ARGS:q: <script>alert(1)</script>"] '
                '[severity "critical"] [ver "OWASP_CRS/4.25.0"] [maturity "0"] [accuracy "0"] '
                '[hostname "192.168.107.3"] [uri "/?q=<script>alert(1)</script>"] '
                '[unique_id "76d5cec7-bcbb-4742-8d78-6ab51fac2d06"]'
            ),
            "data": None,
        },
        {
            "actionset": "", "message": "",
            "error_message": (
                '[client "192.168.107.1"] Coraza: Access denied (phase 2). '
                'Inbound Anomaly Score Exceeded (Total Score: 20) '
                '[file "/etc/coraza/crs/rules/REQUEST-949-BLOCKING-EVALUATION.conf"] '
                '[line "11732"] [id "949110"] [rev ""] [msg "Inbound Anomaly Score Exceeded"] '
                '[data ""] [severity "emergency"] [ver "OWASP_CRS/4.25.0"] '
                '[hostname "192.168.107.3"] [uri "/?q=<script>alert(1)</script>"] '
                '[unique_id "76d5cec7-bcbb-4742-8d78-6ab51fac2d06"]'
            ),
            "data": None,
        },
    ],
}


# ---------------------------------------------------------------------------
# Tests: real-world event
# ---------------------------------------------------------------------------

def test_real_event_maps_correctly() -> None:
    p = coraza_event_to_ingest(_REAL_EVENT)
    assert p is not None
    assert p["producer_event_id"] == "76d5cec7-bcbb-4742-8d78-6ab51fac2d06"
    assert p["source_ip"] == "192.168.107.1"
    assert p["method"] == "GET"
    assert p["request_uri"] == "/?q=<script>alert(1)</script>"
    assert p["vhost"] == "localhost"           # port stripped from "localhost:8080"
    assert p["action"] == "deny"               # is_interrupted=True
    assert p["rule_id"] == 941100              # first message
    assert p["rule_message"] == "XSS Attack Detected via libinjection"
    # Score 20 (parsed from the blocking message) is far above the threshold.
    assert p["severity"] == "critical"
    assert p["status_code"] is None            # status=0 out of range
    assert p["anomaly_score"] == 20            # parsed from "(Total Score: 20)"
    assert p["raw_context"] is _REAL_EVENT


def test_real_event_at_is_iso() -> None:
    p = coraza_event_to_ingest(_REAL_EVENT)
    assert p is not None
    dt = datetime.fromisoformat(p["event_at"])
    assert dt.year == 2026


# ---------------------------------------------------------------------------
# Tests: core field mapping (error_message path)
# ---------------------------------------------------------------------------

def test_maps_core_fields() -> None:
    payload = coraza_event_to_ingest(_base_event())
    assert payload is not None
    assert payload["producer_event_id"] == "tx-123"
    assert payload["vhost"] == "example.com"   # "Example.COM" → lower + port stripped
    assert payload["source_ip"] == "203.0.113.7"
    assert payload["method"] == "GET"
    assert payload["request_uri"] == "/search?q=1"
    assert payload["status_code"] == 200
    assert payload["rule_id"] == 941100
    assert payload["rule_message"] == "XSS Attack Detected via libinjection"
    assert payload["raw_context"]["transaction"]["id"] == "tx-123"


def test_event_at_coraza_format_normalized_to_iso() -> None:
    payload = coraza_event_to_ingest(_base_event())
    assert payload is not None
    dt = datetime.fromisoformat(payload["event_at"])
    assert dt.year == 2026


def test_event_at_accepts_iso_input() -> None:
    event = _base_event(transaction={"timestamp": "2026-01-02T15:04:05Z"})
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["event_at"].startswith("2026-01-02T15:04:05")


def test_vhost_strips_port() -> None:
    event = _base_event()
    event["transaction"]["request"]["headers"] = {"host": ["mysite.com:443"]}
    p = coraza_event_to_ingest(event)
    assert p is not None
    assert p["vhost"] == "mysite.com"


def test_vhost_string_value_no_port() -> None:
    """Header value as plain string (not list) should still work."""
    event = _base_event()
    event["transaction"]["request"]["headers"] = {"host": "api.example.com"}
    p = coraza_event_to_ingest(event)
    assert p is not None
    assert p["vhost"] == "api.example.com"


# ---------------------------------------------------------------------------
# Tests: action derivation
# ---------------------------------------------------------------------------

def test_action_deny_when_interrupted() -> None:
    event = _base_event(transaction={"is_interrupted": True})
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["action"] == "deny"


def test_action_deny_when_critical_severity_string() -> None:
    event = _base_event(messages=[_message_entry(severity="critical")])
    event["transaction"]["is_interrupted"] = False
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["action"] == "deny"


def test_action_deny_when_emergency_severity_string() -> None:
    event = _base_event(messages=[_message_entry(severity="emergency")])
    event["transaction"]["is_interrupted"] = False
    p = coraza_event_to_ingest(event)
    assert p is not None
    assert p["action"] == "deny"


def test_action_allow_when_warning_severity_not_interrupted() -> None:
    event = _base_event(messages=[_message_entry(severity="warning")])
    event["transaction"]["is_interrupted"] = False
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["action"] == "allow"
    assert payload["severity"] == "warning"


# ---------------------------------------------------------------------------
# Tests: event severity derivation
# ---------------------------------------------------------------------------

def test_severity_string_buckets() -> None:
    """Event severity is derived from action + score, not copied per-rule.

    High per-rule severities imply action=deny, which maps to "error" unless
    the anomaly score is clearly above the blocking threshold; non-blocking
    events are capped at "warning".
    """
    cases = {
        "emergency": "error",    # deny without a high total score
        "alert": "error",
        "critical": "error",
        "error": "warning",      # allow, capped at warning
        "warning": "warning",
        "notice": "info",
        "info": "info",
        "debug": "info",
    }
    for sev_str, expected in cases.items():
        event = _base_event(messages=[_message_entry(severity=sev_str)])
        p = coraza_event_to_ingest(event)
        assert p is not None, f"got None for severity={sev_str!r}"
        assert p["severity"] == expected, f"severity={sev_str!r} → {p['severity']!r}, want {expected!r}"


def test_blocked_event_with_high_score_is_critical() -> None:
    event = _base_event(transaction={"is_interrupted": True})
    event["transaction"]["variables"] = {"tx": {"anomaly_score": 15}}
    p = coraza_event_to_ingest(event)
    assert p is not None
    assert p["action"] == "deny"
    assert p["severity"] == "critical"


def test_blocked_event_with_low_score_is_error() -> None:
    event = _base_event(transaction={"is_interrupted": True})
    event["transaction"]["variables"] = {"tx": {"anomaly_score": 5}}
    p = coraza_event_to_ingest(event)
    assert p is not None
    assert p["action"] == "deny"
    assert p["severity"] == "error"


def test_blocked_event_without_score_is_error() -> None:
    event = _base_event(transaction={"is_interrupted": True})
    p = coraza_event_to_ingest(event)
    assert p is not None
    assert p["action"] == "deny"
    assert p["severity"] == "error"


def test_allowed_event_with_high_score_is_critical() -> None:
    """In DetectionOnly mode nothing is ever blocked (action stays "allow"),
    but a high anomaly score must still surface as "critical" so the
    dashboard isn't blind to severe attacks under detect-only policies."""
    event = _base_event(messages=[_message_entry(severity="notice")])
    event["transaction"]["is_interrupted"] = False
    event["transaction"]["variables"] = {"tx": {"anomaly_score": 15}}
    p = coraza_event_to_ingest(event)
    assert p is not None
    assert p["action"] == "allow"
    assert p["severity"] == "critical"


def test_anomaly_score_parsed_from_blocking_message() -> None:
    """When variables are absent, the score comes from the 949110 message."""
    event = _base_event(transaction={"is_interrupted": True})
    event["messages"].append({
        "actionset": "", "message": "",
        "error_message": (
            '[client "203.0.113.7"] Coraza: Access denied (phase 2). '
            'Inbound Anomaly Score Exceeded (Total Score: 12) '
            '[id "949110"] [msg "Inbound Anomaly Score Exceeded"] '
            '[severity "emergency"]'
        ),
        "data": None,
    })
    p = coraza_event_to_ingest(event)
    assert p is not None
    assert p["anomaly_score"] == 12
    assert p["severity"] == "critical"


def test_severity_numeric_string_still_works() -> None:
    """Backward compat: if data dict is populated with numeric severity string."""
    event = _base_event()
    event["messages"][0]["data"] = {"id": "941100", "msg": "XSS", "severity": "2"}
    p = coraza_event_to_ingest(event)
    assert p is not None
    # Rule severity "2" maps to error; non-blocking events are capped at warning.
    assert p["action"] == "allow"
    assert p["severity"] == "warning"
    assert p["rule_id"] == 941100


# ---------------------------------------------------------------------------
# Tests: edge cases
# ---------------------------------------------------------------------------

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


def test_status_zero_dropped() -> None:
    """Blocked requests have status=0 in the actual event; must be mapped to None."""
    event = _base_event(transaction={"response": {"status": 0}})
    p = coraza_event_to_ingest(event)
    assert p is not None
    assert p["status_code"] is None


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


def test_absent_variables_gives_none_score_and_level() -> None:
    """transaction.variables is absent in actual coraza-spoa v0.6.1 output."""
    event = _base_event()
    # no 'variables' key at all
    event["transaction"].pop("variables", None)
    payload = coraza_event_to_ingest(event)
    assert payload is not None
    assert payload["anomaly_score"] is None
    assert payload["paranoia_level"] is None
