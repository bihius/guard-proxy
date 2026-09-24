"""Unit tests for deriving a draft rule exclusion from a Coraza audit event."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.log import Log, LogAction, LogSeverity
from app.models.rule_exclusion import TargetType
from app.schemas.rule_exclusion import RuleExclusionCreate
from app.services.exclusion_suggestion import parse_matched_variable, suggest_exclusion


def _message(rule_id: int, data: str) -> dict[str, object]:
    """One coraza-spoa 0.6.1 message, in the bracketed format it really emits."""
    return {
        "error_message": (
            f'[client "192.168.107.1"] Coraza: Warning. Rule message '
            f'[file "/etc/coraza/crs/rules/REQUEST-9XX.conf"] [line "1"] '
            f'[id "{rule_id}"] [rev ""] [msg "Rule message"] [data "{data}"] '
            f'[severity "critical"] [ver "OWASP_CRS/4.25.0"] [uri "/"]'
        ),
        "data": None,
    }


def _context(*messages: dict[str, object]) -> dict[str, object]:
    return {"transaction": {"request": {"uri": "/"}}, "messages": list(messages)}


# `data` values below are copied from real events captured on the local stack.
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            "Matched Data: XSS data found within ARGS:q: <script>alert(1)</script>",
            ("ARGS", "q"),
        ),
        (
            "Matched Data: /../ found within REQUEST_URI_RAW: "
            "/?file=../../../../etc/passwd",
            ("REQUEST_URI_RAW", None),
        ),
        (
            # A JSON body without a JSON body processor: the whole body is one
            # argument name, containing quotes (escaped by Coraza) and colons.
            'Matched Data: ,\\"password\\":\\" found within ARGS_NAMES:'
            '{\\"email\\":\\"user@example.com\\"}: '
            '{\\"email\\":\\"user@example.com\\"}',
            ("ARGS_NAMES", '{"email":"user@example.com"}'),
        ),
        (
            "Matched Data: sqlmap found within REQUEST_HEADERS:User-Agent: sqlmap/1.8",
            ("REQUEST_HEADERS", "User-Agent"),
        ),
    ],
)
def test_parse_matched_variable_reads_collection_and_name(
    data: str, expected: tuple[str, str | None]
) -> None:
    assert parse_matched_variable(_context(_message(941100, data)), 941100) == expected


def test_parse_matched_variable_uses_only_the_requested_rule() -> None:
    context = _context(
        _message(
            930100, "Matched Data: /../ found within REQUEST_URI_RAW: /?file=../x"
        ),
        _message(
            930120, "Matched Data: etc/passwd found within ARGS:file: ../etc/passwd"
        ),
    )

    assert parse_matched_variable(context, 930120) == ("ARGS", "file")
    assert parse_matched_variable(context, 942100) is None


def test_parse_matched_variable_tolerates_missing_or_empty_data() -> None:
    assert parse_matched_variable(None, 949110) is None
    assert parse_matched_variable({"messages": "oops"}, 949110) is None
    assert parse_matched_variable(_context(_message(949110, "")), 949110) is None


def _log(
    raw_context: dict[str, object] | None, request_uri: str = "/search?q=1"
) -> Log:
    return Log(
        id=7,
        event_at=datetime(2026, 9, 24, 15, 57),
        vhost="juice.local",
        action=LogAction.deny,
        source_ip="192.168.107.1",
        method="GET",
        request_uri=request_uri,
        rule_id=941100,
        rule_message="XSS Attack Detected via libinjection",
        severity=LogSeverity.critical,
        raw_context=raw_context,
    )


def test_suggestion_is_a_valid_exclusion_for_a_named_argument() -> None:
    log = _log(_context(_message(941100, "Matched Data: XSS found within ARGS:q: <b>")))

    suggestion = suggest_exclusion(log, policy_id=3, rule_id=941100)

    assert suggestion.target_type == TargetType.ARGS
    assert suggestion.target_value == "q"
    assert suggestion.scope_path == "/search"
    assert suggestion.matched_variable == "ARGS:q"
    RuleExclusionCreate.model_validate(suggestion.model_dump())


def test_suggestion_leaves_target_empty_when_it_would_not_take_effect() -> None:
    """REQUEST_URI_RAW is not REQUEST_URI: removing the latter would not help."""
    log = _log(
        _context(
            _message(941100, "Matched Data: /../ found within REQUEST_URI_RAW: /?f=..")
        ),
        request_uri="/?f=..",
    )

    suggestion = suggest_exclusion(log, policy_id=3, rule_id=941100)

    assert suggestion.target_type is None
    assert suggestion.target_value is None
    assert suggestion.matched_variable == "REQUEST_URI_RAW"
    assert suggestion.scope_path == "/"


def test_suggestion_leaves_target_empty_for_an_unrenderable_name() -> None:
    log = _log(
        _context(
            _message(
                941100,
                'Matched Data: x found within ARGS_NAMES:{\\"a\\":1}: {\\"a\\":1}',
            )
        )
    )

    suggestion = suggest_exclusion(log, policy_id=3, rule_id=941100)

    assert suggestion.target_type is None
    assert suggestion.matched_variable == 'ARGS_NAMES:{"a":1}'


def test_suggestion_without_raw_context_keeps_rule_and_path() -> None:
    suggestion = suggest_exclusion(_log(None), policy_id=3, rule_id=941100)

    assert (suggestion.rule_id, suggestion.scope_path) == (941100, "/search")
    assert suggestion.target_type is None
    assert (
        suggestion.comment
        == "Created from log #7: XSS Attack Detected via libinjection"
    )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("target_value", '{"email":"x"}', "may only contain"),
        ("target_value", "user agent", "may only contain"),
        ("scope_path", "api/login", "must start with /"),
        ("scope_path", "/api\nlogin", "line breaks"),
    ],
)
def test_create_rejects_values_the_config_generator_cannot_render(
    field: str, value: str, error: str
) -> None:
    body = {
        "rule_id": 942100,
        "target_type": "args",
        "target_value": "token",
        field: value,
    }

    with pytest.raises(ValidationError, match=error):
        RuleExclusionCreate.model_validate(body)
