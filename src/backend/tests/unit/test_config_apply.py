from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.config import settings
from app.services.config_apply import (
    _RELOAD_ERROR_RE,
    ApplyStatus,
    CommandResult,
    _ensure_default_cert,
    _read_current_symlink,
    _write_candidate,
    apply,
    calculate_checksum,
    seed_runtime_config,
)
from app.services.config_generator import CorazaAppConfig, GeneratedConfig


def _sample_generated(policy_tuning: str = "# no overrides\n") -> GeneratedConfig:
    return GeneratedConfig(
        haproxy_cfg="global\n",
        coraza_spoa_yaml="applications: []\n",
        coraza_apps=(
            CorazaAppConfig(
                name="default",
                crs_setup_conf="SecRuleEngine DetectionOnly\n",
                rule_overrides_conf="# no overrides\n",
            ),
            CorazaAppConfig(
                name="policy_7",
                crs_setup_conf="SecRuleEngine On\n",
                rule_overrides_conf=policy_tuning,
            ),
        ),
        certs={},
    )


def _seed_current_release(
    runtime_root: Path,
    *,
    name: str = "previous",
    generated: GeneratedConfig | None = None,
) -> Path:
    release_dir = runtime_root / "releases" / name
    _write_candidate(
        release_dir,
        generated or _sample_generated("# seed\n"),
        runtime_root / "certs",
    )
    current = runtime_root / "current"
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
    assert (active_dir / "coraza-spoa.yaml").read_text(
        encoding="utf-8"
    ) == "applications: []\n"
    assert (active_dir / "coraza/default/crs-setup.conf").read_text(
        encoding="utf-8"
    ) == "SecRuleEngine DetectionOnly\n"
    assert (active_dir / "coraza/policy_7/crs-setup.conf").read_text(
        encoding="utf-8"
    ) == "SecRuleEngine On\n"
    assert (active_dir / "coraza/policy_7/rule-overrides.conf").read_text(
        encoding="utf-8"
    ) == "# no overrides\n"


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


def _generated_with_apps(*names: str) -> GeneratedConfig:
    return GeneratedConfig(
        haproxy_cfg="global\n",
        coraza_spoa_yaml="applications: []\n",
        coraza_apps=tuple(
            CorazaAppConfig(
                name=name,
                crs_setup_conf=f"# {name}\n",
                rule_overrides_conf="# no overrides\n",
            )
            for name in names
        ),
        certs={},
    )


def _active_app_names(runtime_root: Path) -> set[str]:
    return {p.name for p in (runtime_root / "current/coraza").iterdir()}


def _record_runtime_steps(monkeypatch, runtime_root: Path, *, coraza_ok: bool = True):
    """Record Coraza waits and HAProxy reloads with the apps `current` holds."""
    steps: list[tuple[str, object]] = []
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: CommandResult(ok=True, output="valid"),
    )

    def wait(app_names: set[str]) -> CommandResult:
        steps.append(("coraza-wait", (set(app_names), _active_app_names(runtime_root))))
        return CommandResult(ok=coraza_ok, output="coraza did not load policy_9")

    def reload() -> CommandResult:
        steps.append(("haproxy-reload", _active_app_names(runtime_root)))
        return CommandResult(ok=True, output="reloaded")

    monkeypatch.setattr("app.services.config_apply._wait_for_coraza_apps", wait)
    monkeypatch.setattr("app.services.config_apply._reload_haproxy", reload)
    return steps


def test_apply_waits_for_coraza_to_load_new_policies_before_haproxy_reload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """HAProxy must not send an application name Coraza has not loaded yet."""
    runtime_root = tmp_path / "generated"
    _seed_current_release(runtime_root, generated=_generated_with_apps("default"))
    steps = _record_runtime_steps(monkeypatch, runtime_root)

    result = apply(_generated_with_apps("default", "policy_9"))

    assert result.status == ApplyStatus.success
    assert steps == [
        ("coraza-wait", ({"policy_9"}, {"default", "policy_9"})),
        ("haproxy-reload", {"default", "policy_9"}),
    ]


def test_apply_reloads_haproxy_without_waiting_when_no_policy_is_new(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    _seed_current_release(
        runtime_root, generated=_generated_with_apps("default", "policy_9")
    )
    steps = _record_runtime_steps(monkeypatch, runtime_root)

    result = apply(_generated_with_apps("default"))

    assert result.status == ApplyStatus.success
    assert steps == [("haproxy-reload", {"default"})]


def test_apply_keeps_dropped_policies_in_coraza_until_haproxy_reloads(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A vhost moving to a new policy: the old one stays loaded during the swap."""
    runtime_root = tmp_path / "generated"
    _seed_current_release(
        runtime_root, generated=_generated_with_apps("default", "policy_3")
    )
    steps = _record_runtime_steps(monkeypatch, runtime_root)

    result = apply(_generated_with_apps("default", "policy_9"))

    assert result.status == ApplyStatus.success
    bridge_apps = {"default", "policy_3", "policy_9"}
    assert steps == [
        ("coraza-wait", ({"policy_9"}, bridge_apps)),
        ("haproxy-reload", bridge_apps),
    ]
    active_dir = (runtime_root / "current").resolve()
    assert active_dir == Path(result.active_path)
    assert _active_app_names(runtime_root) == {"default", "policy_9"}
    assert list((runtime_root / "releases").glob("*-bridge")) == []


def test_apply_restores_previous_release_when_coraza_does_not_load_new_policy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    previous = _seed_current_release(
        runtime_root, generated=_generated_with_apps("default", "policy_3")
    )
    steps = _record_runtime_steps(monkeypatch, runtime_root, coraza_ok=False)

    result = apply(_generated_with_apps("default", "policy_9"))

    assert result.status == ApplyStatus.coraza_reload_failed
    assert "policy_9" in (result.reload_output or "")
    assert [step for step, _ in steps] == ["coraza-wait"]
    assert (runtime_root / "current").resolve() == previous.resolve()
    assert sorted(p.name for p in (runtime_root / "releases").iterdir()) == ["previous"]


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


# ---------------------------------------------------------------------------
# seed_runtime_config — backend startup must populate /runtime/current so
# Coraza's includes under /runtime/current resolve on first boot.
# ---------------------------------------------------------------------------


def test_seed_runtime_config_writes_current_when_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: CommandResult(ok=True, output="valid"),
    )

    returned_checksum = seed_runtime_config(_sample_generated())

    current = runtime_root / "current"
    assert current.is_symlink()
    assert (current / "coraza/policy_7/crs-setup.conf").read_text(
        encoding="utf-8"
    ) == "SecRuleEngine On\n"
    assert returned_checksum == calculate_checksum(_sample_generated())


def test_seed_runtime_config_replaces_entrypoint_stub_release(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The shell entrypoint seeds crs-setup.conf without haproxy.cfg; the
    Python seeder must replace that stub with the full rendered release so
    CRS rule 901001 does not keep firing."""
    runtime_root = tmp_path / "generated"
    stub_dir = runtime_root / "releases" / "seed"
    stub_dir.mkdir(parents=True)
    (stub_dir / "crs-setup.conf").write_text("SecRuleEngine On\n", encoding="utf-8")
    (stub_dir / "rule-overrides.conf").write_text("# stub\n", encoding="utf-8")
    (runtime_root / "current").symlink_to("releases/seed")
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: CommandResult(ok=True, output="valid"),
    )

    returned_checksum = seed_runtime_config(_sample_generated())

    current = runtime_root / "current"
    assert current.resolve() != stub_dir.resolve()
    assert (current / "haproxy.cfg").exists()
    assert (current / "coraza/policy_7/crs-setup.conf").read_text(
        encoding="utf-8"
    ) == "SecRuleEngine On\n"
    assert returned_checksum == calculate_checksum(_sample_generated())


def test_seed_runtime_config_is_noop_when_current_already_exists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    previous = _seed_current_release(runtime_root)
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: (_ for _ in ()).throw(AssertionError("should not validate")),
    )

    returned_checksum = seed_runtime_config(_sample_generated())

    assert (runtime_root / "current").resolve() == previous.resolve()
    # The pre-existing release's own content, not the (unused) candidate.
    assert returned_checksum == calculate_checksum(_sample_generated("# seed\n"))
    assert returned_checksum != calculate_checksum(_sample_generated())


def test_seed_runtime_config_keeps_a_release_from_before_per_policy_apps(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """An upgrade must not deploy unapplied DB changes on its own.

    The old single-policy release stays active until an admin applies; its
    checksum is unknown so the panel shows the configuration as pending.
    """
    runtime_root = tmp_path / "generated"
    old_release = runtime_root / "releases" / "old"
    old_release.mkdir(parents=True)
    (old_release / "haproxy.cfg").write_text("global\n", encoding="utf-8")
    (old_release / "crs-setup.conf").write_text("SecRuleEngine On\n", encoding="utf-8")
    (old_release / "rule-overrides.conf").write_text("# old\n", encoding="utf-8")
    (runtime_root / "current").symlink_to("releases/old")
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: (_ for _ in ()).throw(AssertionError("should not validate")),
    )

    returned_checksum = seed_runtime_config(_sample_generated())

    assert (runtime_root / "current").resolve() == old_release.resolve()
    assert returned_checksum is None


def test_seed_runtime_config_does_not_swap_current_when_validation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: CommandResult(ok=False, output="parse error"),
    )

    returned_checksum = seed_runtime_config(_sample_generated())

    assert not (runtime_root / "current").exists()
    assert not (runtime_root / "current").is_symlink()
    assert returned_checksum is None


# ---------------------------------------------------------------------------
# Certificate handling — a vhost may enable SSL before its real certificate is
# provisioned (e.g. a freshly added Let's Encrypt domain). HAProxy's
# `bind ... ssl crt <dir>` then needs a loadable fallback or `haproxy -c`
# rejects the whole config. Certificates also live in a single shared directory
# so the absolute cert path in haproxy.cfg resolves identically during backend
# validation and at HAProxy runtime.
# ---------------------------------------------------------------------------


def test_ensure_default_cert_generates_a_loadable_certificate(tmp_path: Path) -> None:
    """The fallback default.pem must parse as a real certificate + key, not a
    placeholder string that haproxy -c would reject with 'too long'."""
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.x509 import load_pem_x509_certificate

    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()

    _ensure_default_cert(certs_dir)

    pem = (certs_dir / "default.pem").read_bytes()
    # Both a certificate and a private key must be present and parseable.
    load_pem_x509_certificate(pem)
    load_pem_private_key(pem, password=None)


def test_ensure_default_cert_is_idempotent(tmp_path: Path) -> None:
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()

    _ensure_default_cert(certs_dir)
    first = (certs_dir / "default.pem").read_bytes()
    _ensure_default_cert(certs_dir)
    second = (certs_dir / "default.pem").read_bytes()

    assert first == second, "default cert must not be regenerated when present"


def test_write_candidate_writes_certs_to_shared_dir_not_per_release(
    tmp_path: Path,
) -> None:
    """Certificates must land in the shared certs dir, with a default fallback,
    so the absolute crt path in haproxy.cfg resolves for validation and runtime."""
    runtime_root = tmp_path / "generated"
    candidate_dir = runtime_root / "releases" / "abc123"
    shared_certs = runtime_root / "certs"
    generated = GeneratedConfig(
        haproxy_cfg="global\n",
        coraza_spoa_yaml="applications: []\n",
        coraza_apps=(),
        certs={"example.com": "PEMDATA\n"},
    )

    _write_candidate(candidate_dir, generated, shared_certs)

    # Per-release dir holds only the rendered config, not certs.
    assert not (candidate_dir / "certs").exists()
    # Shared dir holds the domain cert plus a fallback default.
    assert (shared_certs / "example.com.pem").read_text(encoding="utf-8") == "PEMDATA\n"
    assert (shared_certs / "default.pem").exists()


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


# ---------------------------------------------------------------------------
# GeoIP stub map file (issue #175) — must exist so `haproxy -c` never fails
# on a missing map, including right after upgrading an existing deployment.
# ---------------------------------------------------------------------------


def test_apply_creates_geoip_stub_map_file(
    tmp_path: Path,
    monkeypatch,
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

    apply(_sample_generated())

    geoip_map = runtime_root / "geoip" / "country.map"
    assert geoip_map.exists()
    assert "192.0.2.0/24 ZZ" in geoip_map.read_text(encoding="utf-8")


def test_seed_runtime_config_creates_geoip_stub_map_file_when_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "generated"
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: CommandResult(ok=True, output="valid"),
    )

    seed_runtime_config(_sample_generated())

    geoip_map = runtime_root / "geoip" / "country.map"
    assert geoip_map.exists()
    assert "192.0.2.0/24 ZZ" in geoip_map.read_text(encoding="utf-8")


def test_seed_runtime_config_creates_geoip_stub_map_file_on_early_return(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Regression: existing deployments upgrading into this feature must get
    the stub map even when `current` already points at a release, since
    seed_runtime_config's early-return path used to skip _ensure_geoip_map_file."""
    runtime_root = tmp_path / "generated"
    _seed_current_release(runtime_root)
    monkeypatch.setattr(settings, "runtime_generated_config_root", str(runtime_root))
    monkeypatch.setattr(
        "app.services.config_apply._validate_haproxy",
        lambda _: (_ for _ in ()).throw(AssertionError("should not validate")),
    )

    seed_runtime_config(_sample_generated())

    geoip_map = runtime_root / "geoip" / "country.map"
    assert geoip_map.exists()
    assert "192.0.2.0/24 ZZ" in geoip_map.read_text(encoding="utf-8")


def test_ensure_geoip_map_file_swallows_oserror(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A read-only or missing runtime dir must not break a config apply.

    The GeoIP map stub is a convenience so `haproxy -c` never trips over a
    missing map path; failing to write it is worth a warning, not an aborted
    apply.
    """
    from app.services import geoip_service
    from app.services.config_apply import _ensure_geoip_map_file

    def _raise() -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(geoip_service, "ensure_map_file_exists", _raise)

    with caplog.at_level(logging.WARNING):
        _ensure_geoip_map_file()

    assert "failed to ensure GeoIP map file exists" in caplog.text
