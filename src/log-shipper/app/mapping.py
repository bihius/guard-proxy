"""Translate Coraza JSON audit events into ``LogIngestRequest`` payloads.

The mapping contract is documented in ``configs/coraza/README.md`` and mirrors the
``LogIngestRequest`` schema in ``src/backend/app/schemas/log.py``. This module is a
pure, defensive translator: it never raises on malformed input and returns ``None``
for events that cannot be turned into a valid ingest payload (so the shipper can
skip them instead of wedging).
"""

from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Any

# Coraza/ModSecurity numeric severities run 0 (emergency) .. 7 (debug). The backend
# enum only has four buckets; this collapses the scale per configs/coraza/README.md.
_DENY_SEVERITY_THRESHOLD = 2

# Apache-style timestamp Coraza emits when it is not already ISO 8601.
_CORAZA_TS_FORMATS = (
    "%d/%b/%Y:%H:%M:%S.%f %z",
    "%d/%b/%Y:%H:%M:%S %z",
)


def coraza_event_to_ingest(event: dict[str, Any]) -> dict[str, Any] | None:
    """Map one Coraza audit event to an ingest payload, or ``None`` to skip it."""

    transaction = _as_dict(event.get("transaction"))
    if not transaction:
        return None

    request = _as_dict(transaction.get("request"))
    method = _clean_str(request.get("method"))
    request_uri = _clean_str(request.get("uri"))
    source_ip = _valid_ip(transaction.get("client_ip"))

    # These three are required by the backend; without them the event can never be
    # accepted, so skipping avoids a poison-pill that would block the pipeline.
    if not method or not request_uri or source_ip is None:
        return None

    messages = event.get("messages")
    messages = messages if isinstance(messages, list) else []
    primary = _as_dict(messages[0].get("data")) if messages else {}

    severity_value = _coerce_int(primary.get("severity"))
    is_interrupted = bool(transaction.get("is_interrupted"))

    payload: dict[str, Any] = {
        "producer_event_id": _clean_str(transaction.get("id")),
        "event_at": _event_at(transaction.get("timestamp")),
        "vhost": _vhost(request.get("headers")),
        "action": _action(is_interrupted, messages),
        "source_ip": source_ip,
        "method": method.upper(),
        "request_uri": request_uri,
        "status_code": _status_code(transaction.get("response")),
        "rule_id": _rule_id(primary.get("id")),
        "rule_message": _clean_str(primary.get("msg")),
        "anomaly_score": _anomaly_score(transaction.get("variables")),
        "paranoia_level": _paranoia_level(transaction.get("variables")),
        "severity": _severity(severity_value),
        "message": None,
        "raw_context": event,
    }
    return payload


def _action(is_interrupted: bool, messages: list[Any]) -> str:
    if is_interrupted:
        return "deny"
    for message in messages:
        data = _as_dict(_as_dict(message).get("data"))
        severity = _coerce_int(data.get("severity"))
        if severity is not None and severity < _DENY_SEVERITY_THRESHOLD:
            return "deny"
    return "allow"


def _severity(value: int | None) -> str:
    if value is None:
        return "info"
    if value <= 1:
        return "critical"
    if value == 2:
        return "error"
    if value <= 4:
        return "warning"
    return "info"


def _event_at(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
        iso = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            return datetime.fromisoformat(iso).isoformat()
        except ValueError:
            pass
        for fmt in _CORAZA_TS_FORMATS:
            try:
                return datetime.strptime(text, fmt).isoformat()
            except ValueError:
                continue
    return datetime.now(timezone.utc).isoformat()


def _vhost(headers: Any) -> str:
    headers = _as_dict(headers)
    for key, raw in headers.items():
        if isinstance(key, str) and key.lower() == "host":
            value = raw[0] if isinstance(raw, list) and raw else raw
            host = _clean_str(value)
            if host:
                return host.lower()
    return "unknown"


def _status_code(response: Any) -> int | None:
    status = _coerce_int(_as_dict(response).get("status"))
    if status is None or not (100 <= status <= 599):
        return None
    return status


def _rule_id(value: Any) -> int | None:
    rule_id = _coerce_int(value)
    return rule_id if rule_id is not None and rule_id > 0 else None


def _anomaly_score(variables: Any) -> int | None:
    score = _coerce_int(_tx_variable(variables, "anomaly_score"))
    return score if score is not None and score >= 0 else None


def _paranoia_level(variables: Any) -> int | None:
    level = _coerce_int(_tx_variable(variables, "paranoia_level"))
    return level if level is not None and 1 <= level <= 4 else None


def _tx_variable(variables: Any, name: str) -> Any:
    tx = _as_dict(_as_dict(variables).get("tx"))
    for key, value in tx.items():
        if isinstance(key, str) and key.lower() == name:
            return value
    return None


def _as_dict(value: Any) -> dict[Any, Any]:
    return value if isinstance(value, dict) else {}


def _clean_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _valid_ip(value: Any) -> str | None:
    text = _clean_str(value)
    if text is None:
        return None
    try:
        return str(ip_address(text))
    except ValueError:
        return None
