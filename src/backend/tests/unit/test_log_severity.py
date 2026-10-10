"""Unit tests for event severity relative to a policy inbound threshold."""

from app.models.log import LogAction, LogSeverity
from app.services.log_severity import classify_severity

# Non-default so a hardcoded fallback of 5 cannot satisfy these boundaries.
_THRESHOLD = 20


def test_score_exactly_twice_the_threshold_is_high() -> None:
    assert (
        classify_severity(LogAction.allow, _THRESHOLD * 2, _THRESHOLD)
        == LogSeverity.high
    )


def test_score_one_below_twice_the_threshold_with_deny_is_medium() -> None:
    assert (
        classify_severity(LogAction.deny, _THRESHOLD * 2 - 1, _THRESHOLD)
        == LogSeverity.medium
    )


def test_monitor_without_a_score_is_medium() -> None:
    assert (
        classify_severity(LogAction.monitor, None, _THRESHOLD) == LogSeverity.medium
    )


def test_allow_below_the_threshold_is_low() -> None:
    assert (
        classify_severity(LogAction.allow, _THRESHOLD - 1, _THRESHOLD)
        == LogSeverity.low
    )


def test_allow_with_no_score_is_low() -> None:
    assert classify_severity(LogAction.allow, None, _THRESHOLD) == LogSeverity.low


def test_allow_at_the_threshold_is_medium() -> None:
    assert (
        classify_severity(LogAction.allow, _THRESHOLD, _THRESHOLD)
        == LogSeverity.medium
    )
