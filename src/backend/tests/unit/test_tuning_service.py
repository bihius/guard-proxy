"""Unit tests for learning-mode heuristics (issue #263)."""

import pytest

from app.services.tuning_service import common_scope_path, confidence_score


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        ({"/login"}, "/login"),
        ({"/api/users/1", "/api/users/2"}, "/api/users/"),
        ({"/api", "/api/users/2"}, "/api"),
        ({"/login", "/search"}, "/"),
        # "/api/usersX" must not fall under "/api/users/".
        ({"/api/users/1", "/api/usersX"}, "/api/"),
        ({"/login", None}, None),
    ],
)
def test_common_scope_path(paths: set[str | None], expected: str | None) -> None:
    assert common_scope_path(paths) == expected


def test_confidence_rewards_many_clients_spread_over_time() -> None:
    likely_false_positive = confidence_score(
        event_count=40, source_ip_count=25, active_hours=12, isolated_ratio=1.0
    )
    single_client_burst = confidence_score(
        event_count=40, source_ip_count=1, active_hours=1, isolated_ratio=0.0
    )

    assert likely_false_positive == 100
    assert single_client_burst < 40


def test_confidence_is_bounded() -> None:
    assert confidence_score(0, 0, 0, 0.0) == 0
    assert confidence_score(10**6, 10**6, 10**6, 1.0) == 100
