"""Derive draft rule exclusions from stored WAF log events (issues #264, #263)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from app.models.log import Log
from app.models.rule_exclusion import TargetType, target_error
from app.schemas.rule_exclusion import RuleExclusionSuggestion

# coraza-spoa writes each matched rule as one `error_message` of bracketed
# fields; `data` escapes embedded quotes, e.g.
#   [id "941100"] ... [data "Matched Data: XSS data found within ARGS:q: <script>"]
_ID_RE = re.compile(r'\[id "(\d+)"\]')
_DATA_RE = re.compile(r'\[data "((?:[^"\\]|\\.)*)"\]')
# `within <COLLECTION>: <value>` or `within <COLLECTION>:<name>: <value>`. The
# name ends at the first ": " — it may itself contain ":" (e.g. a JSON body
# parsed as one argument name) — or at the end when Coraza truncated the text.
# A name that itself contains ": " is cut short; such names contain a space,
# which no target value may, so in practice this yields no target rather than
# a wrong one.
_WITHIN_RE = re.compile(r"within ([A-Z_]+)(?:: |:(.*?)(?:: |$))")

# Exact variable names only. The generator emits
# `ctl:ruleRemoveTargetById=<id>;<VARIABLE>[:<name>]`, which removes exactly
# that variable: mapping e.g. ARGS_GET onto ARGS would save an exclusion
# that never takes effect.
_TARGET_TYPE_BY_VARIABLE = {
    target_type.variable: target_type for target_type in TargetType
}

_COMMENT_MAX_LENGTH = 200


@dataclass(frozen=True)
class RuleMatch:
    """One rule that fired in an event, and the variable it matched (if known)."""

    rule_id: int
    rule_message: str | None
    variable: str | None  # Coraza collection, e.g. "ARGS"
    key: str | None  # collection member, e.g. "q"

    @property
    def matched_variable(self) -> str | None:
        if self.variable is None:
            return None
        return self.variable if self.key is None else f"{self.variable}:{self.key}"


_MSG_RE = re.compile(r'\[msg "((?:[^"\\]|\\.)*)"\]')


def iter_rule_matches(raw_context: dict[str, Any] | None) -> Iterator[RuleMatch]:
    """Every rule match in a Coraza audit event, in message order."""
    messages = (raw_context or {}).get("messages")
    if not isinstance(messages, list):
        return
    for message in messages:
        error_message = (
            message.get("error_message") if isinstance(message, dict) else None
        )
        if not isinstance(error_message, str):
            continue
        id_match = _ID_RE.search(error_message)
        if id_match is None:
            continue
        msg_match = _MSG_RE.search(error_message)
        variable, key = None, None
        data_match = _DATA_RE.search(error_message)
        if data_match is not None:
            within = _WITHIN_RE.search(re.sub(r"\\(.)", r"\1", data_match.group(1)))
            if within is not None:
                variable, key = within.group(1), within.group(2) or None
        yield RuleMatch(
            rule_id=int(id_match.group(1)),
            rule_message=msg_match.group(1) if msg_match else None,
            variable=variable,
            key=key,
        )


def parse_matched_variable(
    raw_context: dict[str, Any] | None, rule_id: int
) -> tuple[str, str | None] | None:
    """Return (collection, name) that `rule_id` matched in a Coraza audit event.

    Only the message of `rule_id` itself is used: the exclusion is for that
    rule, and other rules in the same transaction may have matched different
    variables.
    """
    for match in iter_rule_matches(raw_context):
        if match.rule_id == rule_id:
            return None if match.variable is None else (match.variable, match.key)
    return None


def exclusion_target(
    variable: str, key: str | None
) -> tuple[TargetType, str | None] | None:
    """The exclusion target for a matched variable, or None if unsupported."""
    target_type = _TARGET_TYPE_BY_VARIABLE.get(variable)
    if target_type is None:
        return None
    target_value = key if target_type.takes_key else None
    if target_error(target_type, target_value) is not None:
        return None
    return target_type, target_value


def scope_path_for(request_uri: str) -> str | None:
    """Request path usable as an exclusion scope (no query string or fragment)."""
    path = request_uri.split("?", 1)[0].split("#", 1)[0]
    if path.startswith("/") and "\r" not in path and "\n" not in path:
        return path
    return None


def suggest_exclusion(
    log: Log, policy_id: int, rule_id: int
) -> RuleExclusionSuggestion:
    """Build a draft exclusion for the rule that fired in `log`."""
    matched = parse_matched_variable(log.raw_context, rule_id)
    matched_variable = None
    target = None
    if matched is not None:
        collection, name = matched
        matched_variable = collection if name is None else f"{collection}:{name}"
        target = exclusion_target(collection, name)
    target_type, target_value = target if target is not None else (None, None)
    scope_path = scope_path_for(log.request_uri)

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
