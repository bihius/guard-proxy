from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from app.services.config_apply import (
    ApplyStatus,
    CommandResult,
    _RELOAD_ERROR_RE,
    _read_current_symlink,
    apply,
)
from app.services.config_generator import GeneratedConfig


def _sample_generated() -> GeneratedConfig:
    return GeneratedConfig(
        haproxy_cfg="global\n",
        crs_setup_conf="SecRuleEngine On\n",
        rule_overrides_conf="# no overrides\n",
    )


def _seed_current_release(runtime_root: Path, *, name: str = "previous") -> Path:
    releases = runtime_root / "releases"
    release_dir = releases / name
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "haproxy.cfg").write_text("global\n", encoding="utf-8")
    (release_dir / "crs-setup.conf").write_text("SecRuleEngine On\n", encoding="utf-8")
    (release_dir / "rule-overrides.conf").write_text("# seed\n", encoding="utf-8")
    current = runtime_root / "current"
    current.parent.mkdir(parents=True, exist_ok=True)
    current.symlink_to("releases/" + name)
    return release_dir


def test_apply_success_writes_files_and_switches_current(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: CommandResult(ok=True, output="Configuration file is valid"),
    )
    monkeypatch.setattr(
        "app.services.config_apply._reload_haproxy",
        lambda: CommandResult(ok=True, output="Reload succeeded"),
    )

    result = apply(_sample_generated())

    assert result.status == ApplyStatus.success
    assert len(result.correlation_id) == 32

    current = runtime_root / "current"
    assert current.is_symlink()
    active_dir = current.resolve()
    assert active_dir == Path(result.active_path)
    assert (active_dir / "haproxy.cfg").read_text(encoding="utf-8") == "global\n"
    assert (
        (active_dir / "crs-setup.conf").read_text(encoding="utf-8")
        == "SecRuleEngine On\n"
    )


def test_apply_validation_failure_keeps_current_unchanged(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    previous = _seed_current_release(runtime_root)
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: CommandResult(ok=False, output="line 42 parse error"),
    )
    monkeypatch.setattr(
        "app.services.config_apply._reload_haproxy",
        lambda: CommandResult(ok=True, output="should not run"),
    )

    result = apply(_sample_generated())

    assert result.status == ApplyStatus.validation_failed
    assert "parse error" in (result.validation_output or "")
    assert (runtime_root / "current").resolve() == previous.resolve()


def test_apply_reload_failure_rolls_back_to_previous_release(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    previous = _seed_current_release(runtime_root)
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: CommandResult(ok=True, output="valid"),
    )

    reload_results = iter(
        [
            CommandResult(ok=False, output="reload failed"),
            CommandResult(ok=True, output="rollback reload ok"),
        ]
    )
    monkeypatch.setattr(
        "app.services.config_apply._reload_haproxy",
        lambda: next(reload_results),
    )

    result = apply(_sample_generated())

    assert result.status == ApplyStatus.reload_failed_rolled_back
    assert (runtime_root / "current").resolve() == previous.resolve()
    assert "reload failed" in (result.reload_output or "")
    assert "rollback reload ok" in (result.rollback_output or "")


def test_apply_reports_rollback_failed_when_second_reload_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    previous = _seed_current_release(runtime_root)
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: CommandResult(ok=True, output="valid"),
    )

    reload_results = iter(
        [
            CommandResult(ok=False, output="reload failed"),
            CommandResult(ok=False, output="rollback reload failed"),
        ]
    )
    monkeypatch.setattr(
        "app.services.config_apply._reload_haproxy",
        lambda: next(reload_results),
    )

    result = apply(_sample_generated())

    assert result.status == ApplyStatus.rollback_failed
    assert (runtime_root / "current").resolve() == previous.resolve()
    assert "rollback reload failed" in (result.rollback_output or "")


def test_apply_write_failure_returns_write_failed_and_leaves_current_unchanged(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    previous = _seed_current_release(runtime_root)
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._write_candidate",
        lambda *_: (_ for _ in ()).throw(OSError("disk full")),
    )

    result = apply(_sample_generated())

    assert result.status == ApplyStatus.write_failed
    assert "disk full" in result.message
    assert (runtime_root / "current").resolve() == previous.resolve()


def test_apply_logs_attempt_with_correlation_id(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    runtime_root = tmp_path / "generated"
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: CommandResult(ok=True, output="valid"),
    )
    monkeypatch.setattr(
        "app.services.config_apply._reload_haproxy",
        lambda: CommandResult(ok=True, output="reload ok"),
    )
    caplog.set_level(logging.INFO, logger="app.services.config_apply")

    result = apply(_sample_generated())

    start_record = next(
        (record for record in caplog.records if "config-apply start" in record.message),
        None,
    )
    assert start_record is not None
    assert result.correlation_id in start_record.message


# ---------------------------------------------------------------------------
# HIGH #2 — first-apply reload failure must clean up candidate and symlink
# ---------------------------------------------------------------------------


def test_apply_reload_failure_with_no_previous_cleans_up_and_returns_reload_failed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """When there is no previous release and reload fails, the candidate directory
    and current symlink must be removed so the next restart uses the startup config."""
    runtime_root = tmp_path / "generated"
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: CommandResult(ok=True, output="valid"),
    )
    monkeypatch.setattr(
        "app.services.config_apply._reload_haproxy",
        lambda: CommandResult(ok=False, output="reload failed"),
    )

    result = apply(_sample_generated())

    assert result.status == ApplyStatus.reload_failed
    assert result.active_path is None
    # Candidate dir must be cleaned up
    releases_root = runtime_root / "releases"
    remaining = list(releases_root.iterdir()) if releases_root.exists() else []
    assert remaining == [], f"Expected no leftover candidate dirs, found: {remaining}"
    # current symlink must not exist
    assert not (runtime_root / "current").exists()
    assert not (runtime_root / "current").is_symlink()


# ---------------------------------------------------------------------------
# MED M1 — reload error regex must not false-positive on benign substrings
# ---------------------------------------------------------------------------


def test_reload_error_regex_does_not_match_benign_strings() -> None:
    benign_outputs = [
        # Common HAProxy success responses to the master socket reload command.
        "[1] (SIGTERM->MASTER)",
        "Success=1 Failure=0",
        # Mid-sentence occurrences that are not line-leading error keywords.
        "no error",
        "failover ready",
        # IPv6 warning during bind — often emitted but non-fatal; the "failed"
        # substring is not at the start of the line.
        "warning: bind to 0.0.0.0:80 failed for ipv6, continuing",
        "",
    ]
    for output in benign_outputs:
        assert not _RELOAD_ERROR_RE.search(output), (
            f"Regex incorrectly matched benign output: {output!r}"
        )


def test_reload_error_regex_matches_error_lines() -> None:
    error_outputs = [
        "error connecting to backend",
        "fail to bind",
        "denied by rule",
        "permission denied",
        "  error: something went wrong",
    ]
    for output in error_outputs:
        assert _RELOAD_ERROR_RE.search(output), (
            f"Regex did not match expected error output: {output!r}"
        )


# ---------------------------------------------------------------------------
# MED M3 — non-symlink current directory must raise RuntimeError
# ---------------------------------------------------------------------------


def test_read_current_symlink_raises_for_plain_directory(tmp_path: Path) -> None:
    """A real directory at runtime/current is an invalid state and must raise."""
    current = tmp_path / "current"
    current.mkdir()
    (current / "haproxy.cfg").write_text("global\n", encoding="utf-8")

    import pytest
    with pytest.raises(RuntimeError, match="is a directory"):
        _read_current_symlink(current)


def test_apply_returns_state_invalid_when_current_is_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    runtime_root.mkdir(parents=True)
    current = runtime_root / "current"
    current.mkdir()
    (current / "haproxy.cfg").write_text("global\n", encoding="utf-8")
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))

    result = apply(_sample_generated())

    assert result.status == ApplyStatus.state_invalid
    assert "directory" in result.message.lower()


# ---------------------------------------------------------------------------
# MED M4 — rollback path must validate previous release before reloading
# ---------------------------------------------------------------------------


def test_apply_skips_rollback_reload_when_previous_no_longer_validates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """If the previous release fails haproxy -c, skip the rollback reload and
    leave current pointing at the candidate (which passed validation)."""
    runtime_root = tmp_path / "generated"
    _seed_current_release(runtime_root)
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))

    call_count = {"n": 0}

    def _validate_stub(config_path: Path) -> CommandResult:
        call_count["n"] += 1
        # First call: candidate validation — succeeds.
        # Second call: previous release validation in rollback path — fails.
        if call_count["n"] == 1:
            return CommandResult(ok=True, output="valid")
        return CommandResult(ok=False, output="previous config parse error")

    monkeypatch.setattr("app.services.config_apply._validate_haproxy", _validate_stub)
    monkeypatch.setattr(
        "app.services.config_apply._reload_haproxy",
        lambda: CommandResult(ok=False, output="reload failed"),
    )

    result = apply(_sample_generated())

    assert result.status == ApplyStatus.rollback_failed
    assert "no longer validates" in result.message
    # current must still point at the candidate (not the invalid previous)
    current_resolved = (runtime_root / "current").resolve()
    releases_root = runtime_root / "releases"
    candidates = [
        p for p in releases_root.iterdir()
        if p.name != "previous" and p.resolve() == current_resolved
    ]
    assert candidates, "current should point at the new candidate after rollback skipped"
