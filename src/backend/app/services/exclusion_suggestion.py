"""Derive a draft rule exclusion from a stored WAF log event (issue #264)."""

from __future__ import annotations

import re
from typing import Any

from app.models.log import Log
from app.models.rule_exclusion import TARGET_VALUE_PATTERN, TargetType
from app.schemas.rule_exclusion import RuleExclusionSuggestion

# coraza-spoa writes each matched rule as one `error_message` of bracketed
# fields; `data` escapes embedded quotes, e.g.
#   [id "941100"] ... [data "Matched Data: XSS data found within ARGS:q: <script>"]
_ID_RE = re.compile(r'\[id "(\d+)"\]')
_DATA_RE = re.compile(r'\[data "((?:[^"\\]|\\.)*)"\]')
# `within <COLLECTION>: <value>` or `within <COLLECTION>:<name>: <value>`. The
# name ends at the first ": " — it may itself contain ":" (e.g. a JSON body
# parsed as one argument name) — or at the end when Coraza truncated the text.
_WITHIN_RE = re.compile(r"within ([A-Z_]+)(?:: |:(.*?)(?:: |$))")

# Exact collection names only. The generator emits
# `ctl:ruleRemoveTargetById=<id>;<COLLECTION>[:<name>]`, which removes exactly
# that variable: mapping e.g. REQUEST_URI_RAW or ARGS_GET onto a neighbouring
# target type would save an exclusion that never takes effect.
_TARGET_TYPE_BY_COLLECTION = {
    "ARGS": TargetType.ARGS,
    "ARGS_NAMES": TargetType.ARGS_NAMES,
    "REQUEST_HEADERS": TargetType.REQUEST_HEADERS,
    "REQUEST_URI": TargetType.REQUEST_URI,
}

_COMMENT_MAX_LENGTH = 200


def parse_matched_variable(
    raw_context: dict[str, Any] | None, rule_id: int
) -> tuple[str, str | None] | None:
    """Return (collection, name) that `rule_id` matched in a Coraza audit event.

    Only the message of `rule_id` itself is used: the exclusion is for that
    rule, and other rules in the same transaction may have matched different
    variables.
    """
    messages = (raw_context or {}).get("messages")
    if not isinstance(messages, list):
        return None
    for message in messages:
        error_message = (
            message.get("error_message") if isinstance(message, dict) else None
        )
        if not isinstance(error_message, str):
            continue
        id_match = _ID_RE.search(error_message)
        if id_match is None or int(id_match.group(1)) != rule_id:
            continue
        data_match = _DATA_RE.search(error_message)
        if data_match is None:
            return None
        data = re.sub(r"\\(.)", r"\1", data_match.group(1))
        within = _WITHIN_RE.search(data)
        if within is None:
            return None
        return within.group(1), within.group(2) or None
    return None


def suggest_exclusion(
    log: Log, policy_id: int, rule_id: int
) -> RuleExclusionSuggestion:
    """Build a draft exclusion for the rule that fired in `log`."""
    matched = parse_matched_variable(log.raw_context, rule_id)
    matched_variable = None
    target_type = None
    target_value = None
    if matched is not None:
        collection, name = matched
        matched_variable = collection if name is None else f"{collection}:{name}"
        target_type = _TARGET_TYPE_BY_COLLECTION.get(collection)
        if target_type == TargetType.REQUEST_URI:
            # The generator ignores the value for REQUEST_URI but still
            # requires a renderable one.
            target_value = "REQUEST_URI"
        elif target_type is not None and name and TARGET_VALUE_PATTERN.match(name):
            target_value = name
        else:
            target_type = None

    path = log.request_uri.split("?", 1)[0].split("#", 1)[0]
    scope_path = (
        path if path.startswith("/") and "\r" not in path and "\n" not in path else None
    )

    comment = f"Created from log #{log.id}"
    if log.rule_message:
        comment = f"{comment}: {log.rule_message}"[:_COMMENT_MAX_LENGTH]

    return RuleExclusionSuggestion(
        policy_id=policy_id,
        rule_id=rule_id,
        target_type=target_type,
        target_value=target_value,
        scope_path=scope_path,
        comment=comment,
        matched_variable=matched_variable,
    )
