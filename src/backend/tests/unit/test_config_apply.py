from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from app.services.config_apply import (
    ApplyStatus,
    CommandResult,
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
