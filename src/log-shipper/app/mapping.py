"""Translate Coraza JSON audit events into ``LogIngestRequest`` payloads.

The mapping contract is documented in ``configs/coraza/README.md`` and mirrors the
``LogIngestRequest`` schema in ``src/backend/app/schemas/log.py``. This module is a
pure, defensive translator: it never raises on malformed input and returns ``None``
for events that cannot be turned into a valid ingest payload (so the shipper can
skip them instead of wedging).

## Actual coraza-spoa v0.6.1 JSON format quirks

The README mapping table was written against the expected coraza audit schema, but
the actual coraza-spoa v0.6.1 binary does not populate ``messages[].data``; that
field is always ``null``. Rule id, rule message, and severity are instead embedded
in the ``messages[].error_message`` log-formatted string, e.g.:

    [id "941100"] [msg "XSS Attack Detected"] [severity "critical"]

Similarly the timestamp uses ``"YYYY/MM/DD HH:MM:SS"`` (no timezone, implicitly
UTC) and ``transaction.variables`` is absent. The mapping handles both the
documented schema and the actual one so it does not break if a future version of
coraza-spoa populates ``data``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Any

# Regex to extract bracketed fields from coraza-spoa error_message strings.
# e.g.  [id "941100"] [msg "XSS Attack Detected"] [severity "critical"]
_BRACKET_INT = re.compile(r'\[id "(\d+)"\]')
_BRACKET_MSG = re.compile(r'\[msg "([^"]+)"\]')
_BRACKET_SEV = re.compile(r'\[severity "([\w]+)"\]')

# Severity strings Coraza writes in error_message → LogSeverity enum values.
# ModSecurity/Coraza uses: emergency, alert, critical, error, warning, notice, info, debug
_SEVERITY_STRING_MAP: dict[str, str] = {
    "emergency": "critical",
    "alert": "critical",
    "critical": "critical",
    "error": "error",
    "warning": "warning",
    "notice": "info",
    "info": "info",
    "debug": "info",
}

# Severity strings that indicate a blocking/deny action even without is_interrupted.
_DENY_SEVERITY_STRINGS = frozenset({"emergency", "alert", "critical"})

# Timestamp formats Coraza may emit in addition to ISO 8601.
_CORAZA_TS_FORMATS = (
    "%Y/%m/%d %H:%M:%S",        # actual coraza-spoa v0.6.1: "2026/05/31 13:29:17"
    "%d/%b/%Y:%H:%M:%S.%f %z",  # Apache-style with microseconds and tz
    "%d/%b/%Y:%H:%M:%S %z",     # Apache-style without microseconds
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

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
    is_interrupted = bool(transaction.get("is_interrupted"))

    # Prefer the structured data field; fall back to parsing error_message.
    primary_data = _primary_rule_data(messages)

    payload: dict[str, Any] = {
        "producer_event_id": _clean_str(transaction.get("id")),
        "event_at": _event_at(transaction.get("timestamp")),
        "vhost": _vhost(request.get("headers")),
        "action": _action(is_interrupted, primary_data),
        "source_ip": source_ip,
        "method": method.upper(),
        "request_uri": request_uri,
        "status_code": _status_code(transaction.get("response")),
        "rule_id": _rule_id(primary_data),
        "rule_message": _rule_message(primary_data),
        "anomaly_score": _anomaly_score(transaction.get("variables")),
        "paranoia_level": _paranoia_level(transaction.get("variables")),
        "severity": _severity(primary_data),
        "message": None,
        "raw_context": event,
    }
    return payload


# ---------------------------------------------------------------------------
# Rule data extraction — handles both structured data and error_message string
# ---------------------------------------------------------------------------

class _RuleData:
    """Normalised rule fields extracted from either data dict or error_message."""

    __slots__ = ("id", "msg", "severity_str")

    def __init__(self, id: str | None, msg: str | None, severity_str: str | None) -> None:
        self.id = id
        self.msg = msg
        self.severity_str = severity_str


def _primary_rule_data(messages: list[Any]) -> _RuleData | None:
    """Return the first message that carries rule information."""
    for raw in messages:
        msg = _as_dict(raw)

        # 1. Prefer structured data dict (future coraza-spoa versions may populate this).
        data = _as_dict(msg.get("data"))
        if data:
            return _RuleData(
                id=_clean_str(data.get("id")),
                msg=_clean_str(data.get("msg")),
                severity_str=_clean_str(data.get("severity")),
            )

        # 2. Fall back to parsing error_message (actual coraza-spoa v0.6.1 behaviour).
        error_msg = msg.get("error_message")
        if isinstance(error_msg, str) and error_msg.strip():
            id_match = _BRACKET_INT.search(error_msg)
            msg_match = _BRACKET_MSG.search(error_msg)
            sev_match = _BRACKET_SEV.search(error_msg)
            if id_match or msg_match or sev_match:
                return _RuleData(
                    id=id_match.group(1) if id_match else None,
                    msg=msg_match.group(1) if msg_match else None,
                    severity_str=sev_match.group(1) if sev_match else None,
                )

    return None


# ---------------------------------------------------------------------------
# Field derivation helpers
# ---------------------------------------------------------------------------

def _action(is_interrupted: bool, primary_data: _RuleData | None) -> str:
    if is_interrupted:
        return "deny"
    # Secondary check: deny when a high-severity rule fired even without interruption
    # (e.g. DetectionOnly-adjacent configs that still log critical hits).
    if primary_data is not None and primary_data.severity_str is not None:
        if primary_data.severity_str.lower() in _DENY_SEVERITY_STRINGS:
            return "deny"
    return "allow"


def _rule_id(rd: _RuleData | None) -> int | None:
    if rd is None:
        return None
    rule_id = _coerce_int(rd.id)
    return rule_id if rule_id is not None and rule_id > 0 else None


def _rule_message(rd: _RuleData | None) -> str | None:
    return rd.msg if rd is not None else None


def _severity(rd: _RuleData | None) -> str:
    if rd is None or rd.severity_str is None:
        return "info"
    key = rd.severity_str.lower()
    # Named string severity (actual coraza-spoa output).
    if key in _SEVERITY_STRING_MAP:
        return _SEVERITY_STRING_MAP[key]
    # Numeric string (documented schema assumption: "0"–"7").
    numeric = _coerce_int(rd.severity_str)
    if numeric is not None:
        if numeric <= 1:
            return "critical"
        if numeric == 2:
            return "error"
        if numeric <= 4:
            return "warning"
        return "info"
    return "info"


def _event_at(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
        # Handle ISO 8601 with or without trailing Z.
        iso = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            return datetime.fromisoformat(iso).isoformat()
        except ValueError:
            pass
        for fmt in _CORAZA_TS_FORMATS:
            try:
                dt = datetime.strptime(text, fmt)
                # Formats without timezone info are treated as UTC.
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except ValueError:
                continue
    return datetime.now(timezone.utc).isoformat()


def _vhost(headers: Any) -> str:
    headers = _as_dict(headers)
    for key, raw in headers.items():
        if isinstance(key, str) and key.lower() == "host":
            # Header values may be a list (actual coraza-spoa output).
            value = raw[0] if isinstance(raw, list) and raw else raw
            host = _clean_str(value)
            if host:
                # Strip port if present: "localhost:8080" → "localhost"
                return host.lower().split(":")[0]
    return "unknown"


def _status_code(response: Any) -> int | None:
    status = _coerce_int(_as_dict(response).get("status"))
    if status is None or not (100 <= status <= 599):
        return None
    return status


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


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

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
