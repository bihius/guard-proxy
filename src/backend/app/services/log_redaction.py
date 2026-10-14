"""Redact secrets from a stored Coraza audit event.

The log shipper stores the whole audit event as ``raw_context`` so an admin can
investigate an event, and the audit log includes the request headers (Coraza
audit part ``B``). Those headers carry credentials the protected application
issued or received — ``Cookie``, ``Authorization``, API keys — which would then
sit in the database and in the log viewer for any authenticated user to read.

Only values are redacted, never keys, and the walk is key-name based so the
error messages the exclusion suggester parses (``messages[].error_message``)
survive untouched.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[redacted]"

# Header names that always carry a credential.
_SENSITIVE_NAMES = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-auth-token",
        "x-csrf-token",
        "x-xsrf-token",
        "x-guard-proxy-ingest-secret",
    }
)

# Name fragments that make a field a credential wherever it appears.
_SENSITIVE_FRAGMENTS = re.compile(
    r"password|passwd|secret|token|api[-_]?key|credential"
)


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return lowered in _SENSITIVE_NAMES or bool(_SENSITIVE_FRAGMENTS.search(lowered))


def redact_raw_context(value: Any) -> Any:
    """Return a copy of ``value`` with credential-bearing values replaced."""
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and _is_sensitive(key):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact_raw_context(item)
        return redacted
    if isinstance(value, list):
        return [redact_raw_context(item) for item in value]
    return value
