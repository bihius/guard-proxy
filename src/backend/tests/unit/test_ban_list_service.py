"""Unit tests for the ban-list Runtime API service."""

from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.models.vhost import VHost
from app.services import ban_list_service
from app.services.ban_list_service import (
    BanListService,
    BanTableEntry,
    InvalidIpError,
    RuntimeApiError,
    _parse_show_table,
)


def _sample_policy(**overrides: object) -> Policy:
    defaults = dict(
        name="DDoS+Ban",
        ddos_protection_enabled=True,
        rate_limit_requests=100,
        rate_limit_window_seconds=10,
        max_connections_per_ip=20,
        auto_ban_enabled=True,
        ban_threshold=10,
        ban_duration_seconds=600,
    )
    defaults.update(overrides)
    return Policy(**defaults)


def _sample_vhost(policy: Policy | None, **overrides: object) -> VHost:
    defaults = dict(
        domain="app.example.com",
        backend_url="http://backend:8000",
        is_active=True,
        ssl_enabled=False,
        policy=policy,
    )
    defaults.update(overrides)
    return VHost(**defaults)


class TestParseShowTable:
    def test_parses_banned_entry(self) -> None:
        raw = (
            "# table: st_ban_vhost_1, type: ip, size:102400, used:1\n"
            "0x7f: key=192.0.2.7 use=0 exp=540000 gpc0=15\n"
        )

        entries = _parse_show_table(raw)

        assert entries == [
            BanTableEntry(ip="192.0.2.7", gpc0=15, expires_in_seconds=540)
        ]

    def test_parses_sub_threshold_tracked_entry(self) -> None:
        raw = "0x1: key=198.51.100.9 use=1 exp=1500 gpc0=2\n"

        entries = _parse_show_table(raw)

        assert entries[0].gpc0 == 2
        assert entries[0].expires_in_seconds == 2  # ceil(1500ms) -> 2s

    def test_empty_table_returns_no_entries(self) -> None:
        raw = "# table: st_ban_vhost_1, type: ip, size:102400, used:0\n"

        assert _parse_show_table(raw) == []

    def test_header_only_output_returns_no_entries(self) -> None:
        assert _parse_show_table("") == []

    def test_ignores_unparseable_lines(self) -> None:
        raw = "some unrelated garbage line\nkey=only-partial\n"

        assert _parse_show_table(raw) == []


class TestListBanned:
    def test_lists_entries_only_for_ddos_and_auto_ban_enabled_active_vhosts(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        eligible_policy = _sample_policy(name="Eligible")
        no_ban_policy = _sample_policy(name="NoBan", auto_ban_enabled=False)
        no_ddos_policy = _sample_policy(
            name="NoDdos", ddos_protection_enabled=False, auto_ban_enabled=False
        )

        eligible_vhost = _sample_vhost(eligible_policy, domain="eligible.example.com")
        no_ban_vhost = _sample_vhost(no_ban_policy, domain="noban.example.com")
        no_ddos_vhost = _sample_vhost(no_ddos_policy, domain="noddos.example.com")
        no_policy_vhost = _sample_vhost(None, domain="nopolicy.example.com")
        inactive_vhost = _sample_vhost(
            eligible_policy, domain="inactive.example.com", is_active=False
        )

        db.add_all(
            [
                eligible_policy,
                no_ban_policy,
                no_ddos_policy,
                eligible_vhost,
                no_ban_vhost,
                no_ddos_vhost,
                no_policy_vhost,
                inactive_vhost,
            ]
        )
        db.flush()

        sent_commands: list[str] = []

        def fake_send(command: str) -> str:
            sent_commands.append(command)
            return "0x1: key=203.0.113.5 use=0 exp=60000 gpc0=99\n"

        monkeypatch.setattr(ban_list_service, "_send_runtime_command", fake_send)

        service = BanListService(db)
        results = service.list_banned()

        assert sent_commands == [f"show table st_ban_vhost_{eligible_vhost.id}"]
        assert len(results) == 1
        entry = results[0]
        assert entry.ip == "203.0.113.5"
        assert entry.vhost_id == eligible_vhost.id
        assert entry.domain == "eligible.example.com"
        assert entry.gpc0 == 99
        assert entry.ban_threshold == 10
        assert entry.banned is True

    def test_marks_sub_threshold_entries_as_not_banned(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        policy = _sample_policy(ban_threshold=10)
        vhost = _sample_vhost(policy)
        db.add_all([policy, vhost])
        db.flush()

        monkeypatch.setattr(
            ban_list_service,
            "_send_runtime_command",
            lambda _cmd: "0x1: key=192.0.2.1 use=0 exp=1000 gpc0=3\n",
        )

        results = BanListService(db).list_banned()

        assert results[0].banned is False

    def test_skips_table_that_raises_and_continues_with_others(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        policy_a = _sample_policy(name="A")
        policy_b = _sample_policy(name="B")
        vhost_a = _sample_vhost(policy_a, domain="a.example.com")
        vhost_b = _sample_vhost(policy_b, domain="b.example.com")
        db.add_all([policy_a, policy_b, vhost_a, vhost_b])
        db.flush()

        def fake_send(command: str) -> str:
            if f"vhost_{vhost_a.id}" in command:
                raise RuntimeApiError("connection refused")
            return "0x1: key=192.0.2.1 use=0 exp=1000 gpc0=1\n"

        monkeypatch.setattr(ban_list_service, "_send_runtime_command", fake_send)

        results = BanListService(db).list_banned()

        assert len(results) == 1
        assert results[0].vhost_id == vhost_b.id

    def test_returns_empty_list_when_no_vhost_qualifies(self, db: Session) -> None:
        assert BanListService(db).list_banned() == []


class TestUnban:
    def test_clears_ip_from_every_active_table(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        policy_a = _sample_policy(name="A")
        policy_b = _sample_policy(name="B")
        vhost_a = _sample_vhost(policy_a, domain="a.example.com")
        vhost_b = _sample_vhost(policy_b, domain="b.example.com")
        db.add_all([policy_a, policy_b, vhost_a, vhost_b])
        db.flush()

        sent_commands: list[str] = []

        def fake_send(command: str) -> str:
            sent_commands.append(command)
            return ""

        monkeypatch.setattr(ban_list_service, "_send_runtime_command", fake_send)

        result = BanListService(db).unban("203.0.113.9")

        assert result.ip == "203.0.113.9"
        assert result.cleared == 2
        assert sent_commands == [
            f"clear table st_ban_vhost_{vhost_a.id} key 203.0.113.9",
            f"clear table st_ban_vhost_{vhost_b.id} key 203.0.113.9",
        ]

    def test_rejects_invalid_ip_without_calling_socket(self, db: Session) -> None:
        send = Mock()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(ban_list_service, "_send_runtime_command", send)
            with pytest.raises(InvalidIpError):
                BanListService(db).unban("not-an-ip")
        send.assert_not_called()

    def test_partial_table_failure_still_counts_successes(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        policy_a = _sample_policy(name="A")
        policy_b = _sample_policy(name="B")
        vhost_a = _sample_vhost(policy_a, domain="a.example.com")
        vhost_b = _sample_vhost(policy_b, domain="b.example.com")
        db.add_all([policy_a, policy_b, vhost_a, vhost_b])
        db.flush()

        def fake_send(command: str) -> str:
            if f"vhost_{vhost_a.id}" in command:
                raise RuntimeApiError("connection refused")
            return ""

        monkeypatch.setattr(ban_list_service, "_send_runtime_command", fake_send)

        result = BanListService(db).unban("203.0.113.9")

        assert result.cleared == 1

    def test_raises_runtime_api_error_when_every_table_fails(
        self, db: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        policy = _sample_policy()
        vhost = _sample_vhost(policy)
        db.add_all([policy, vhost])
        db.flush()

        def fake_send(_command: str) -> str:
            raise RuntimeApiError("connection refused")

        monkeypatch.setattr(ban_list_service, "_send_runtime_command", fake_send)

        with pytest.raises(RuntimeApiError):
            BanListService(db).unban("203.0.113.9")

    def test_returns_zero_cleared_when_no_vhost_qualifies(self, db: Session) -> None:
        result = BanListService(db).unban("203.0.113.9")

        assert result.cleared == 0
