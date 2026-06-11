"""Apply generated runtime config with validation, reload, and rollback."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import socket
import subprocess
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from app.config import settings
from app.services.config_generator import GeneratedConfig

logger = logging.getLogger(__name__)

# Anchored to the start of a line so common benign substrings such as
# "no error", "failover ready", or "warning: bind ... failed for ipv6,
# continuing" do not trigger false-positive failure detection.
_RELOAD_ERROR_RE = re.compile(
    r"^\s*(error|fail|denied|permission)\b",
    re.IGNORECASE | re.MULTILINE,
)


class ApplyStatus(StrEnum):
    """Outcome classes for config apply attempts."""

    success = "success"
    write_failed = "write_failed"
    state_invalid = "state_invalid"
    validation_failed = "validation_failed"
    reload_failed = "reload_failed"
    reload_failed_rolled_back = "reload_failed_rolled_back"
    rollback_failed = "rollback_failed"


@dataclass(frozen=True)
class ApplyResult:
    """Structured result for one config apply attempt."""

    status: ApplyStatus
    correlation_id: str
    checksum: str
    message: str
    candidate_path: str
    active_path: str | None
    validation_output: str | None = None
    reload_output: str | None = None
    rollback_output: str | None = None


def apply(generated: GeneratedConfig) -> ApplyResult:
    """Validate and atomically activate generated runtime config."""
    correlation_id = uuid.uuid4().hex
    checksum = _calculate_checksum(generated)
    runtime_root = Path(settings.runtime_generated_config_root).resolve()
    releases_root = runtime_root / "releases"
    candidate_dir = releases_root / correlation_id
    current_link = runtime_root / "current"

    # Clean up any orphaned temp symlinks left by a previous crash.
    _sweep_orphaned_temp_links(runtime_root)

    try:
        previous_target = _read_current_symlink(current_link)
    except RuntimeError as exc:
        logger.error(
            "config-apply state-invalid correlation_id=%s error=%s",
            correlation_id,
            exc,
        )
        return ApplyResult(
            status=ApplyStatus.state_invalid,
            correlation_id=correlation_id,
            checksum=checksum,
            message=f"Runtime directory state is invalid: {exc}",
            candidate_path=str(candidate_dir),
            active_path=str(_resolve_current(current_link)),
        )

    logger.info(
        "config-apply start correlation_id=%s checksum=%s",
        correlation_id,
        checksum,
    )

    try:
        _write_candidate(candidate_dir, generated)
    except OSError as error:
        logger.exception(
            "config-apply write failed correlation_id=%s error=%s",
            correlation_id,
            error,
        )
        return ApplyResult(
            status=ApplyStatus.write_failed,
            correlation_id=correlation_id,
            checksum=checksum,
            message=f"Failed to prepare candidate files: {error}",
            candidate_path=str(candidate_dir),
            active_path=str(_resolve_current(current_link)),
        )

    validation = _validate_haproxy(candidate_dir / "haproxy.cfg")
    if not validation.ok:
        shutil.rmtree(candidate_dir, ignore_errors=True)
        logger.warning(
            "config-apply validation failed correlation_id=%s output=%s",
            correlation_id,
            validation.output,
        )
        return ApplyResult(
            status=ApplyStatus.validation_failed,
            correlation_id=correlation_id,
            checksum=checksum,
            message="HAProxy config validation failed.",
            candidate_path=str(candidate_dir),
            active_path=str(_resolve_current(current_link)),
            validation_output=validation.output,
        )

    _swap_current_link(current_link, candidate_dir, runtime_root)

    reload_result = _reload_haproxy()
    if reload_result.ok:
        logger.info(
            "config-apply success correlation_id=%s",
            correlation_id,
        )
        return ApplyResult(
            status=ApplyStatus.success,
            correlation_id=correlation_id,
            checksum=checksum,
            message=(
                "Configuration applied. HAProxy reloaded; Coraza is reloading "
                "the updated WAF ruleset (within ~1s)."
            ),
            candidate_path=str(candidate_dir),
            active_path=str(_resolve_current(current_link)),
            validation_output=validation.output,
            reload_output=reload_result.output,
        )

    logger.error(
        "config-apply reload failed correlation_id=%s output=%s",
        correlation_id,
        reload_result.output,
    )

    if previous_target is None:
        # No previous release to roll back to. Remove the symlink and the
        # failed candidate so neither a restart nor the next apply sees broken
        # state. HAProxy is still running from whatever config it loaded at
        # container start; the symlink simply doesn't exist until the next
        # successful apply.
        try:
            current_link.unlink(missing_ok=True)
        except OSError:
            pass
        shutil.rmtree(candidate_dir, ignore_errors=True)
        logger.error(
            "config-apply reload failed, no previous release; candidate cleaned up "
            "correlation_id=%s",
            correlation_id,
        )
        return ApplyResult(
            status=ApplyStatus.reload_failed,
            correlation_id=correlation_id,
            checksum=checksum,
            message=(
                "Reload failed with no previous release to roll back to; "
                "candidate cleaned up. HAProxy is running from its startup config."
            ),
            candidate_path=str(candidate_dir),
            active_path=None,
            validation_output=validation.output,
            reload_output=reload_result.output,
        )

    # Validate previous release before attempting rollback reload — it may
    # have been edited out-of-band. If it no longer validates, skip the reload
    # and leave current pointing at the candidate (which did pass validation)
    # so that the next HAProxy restart uses a syntactically valid config.
    prev_validation = _validate_haproxy(previous_target / "haproxy.cfg")
    if not prev_validation.ok:
        logger.critical(
            "config-apply rollback skipped: previous release no longer validates "
            "correlation_id=%s",
            correlation_id,
        )
        return ApplyResult(
            status=ApplyStatus.rollback_failed,
            correlation_id=correlation_id,
            checksum=checksum,
            message=(
                "Reload failed and previous release no longer validates; "
                "current left pointing at new candidate."
            ),
            candidate_path=str(candidate_dir),
            active_path=str(_resolve_current(current_link)),
            validation_output=prev_validation.output,
            reload_output=reload_result.output,
        )

    _swap_current_link(current_link, previous_target, runtime_root)
    rollback_reload = _reload_haproxy()
    if rollback_reload.ok:
        logger.warning(
            "config-apply rolled back correlation_id=%s rollback_output=%s",
            correlation_id,
            rollback_reload.output,
        )
        return ApplyResult(
            status=ApplyStatus.reload_failed_rolled_back,
            correlation_id=correlation_id,
            checksum=checksum,
            message="Reload failed; previous release restored and reloaded.",
            candidate_path=str(candidate_dir),
            active_path=str(_resolve_current(current_link)),
            validation_output=validation.output,
            reload_output=reload_result.output,
            rollback_output=rollback_reload.output,
        )

    logger.critical(
        "config-apply rollback reload failed correlation_id=%s output=%s",
        correlation_id,
        rollback_reload.output,
    )
    return ApplyResult(
        status=ApplyStatus.rollback_failed,
        correlation_id=correlation_id,
        checksum=checksum,
        message="Reload failed and rollback reload also failed.",
        candidate_path=str(candidate_dir),
        active_path=str(_resolve_current(current_link)),
        validation_output=validation.output,
        reload_output=reload_result.output,
        rollback_output=rollback_reload.output,
    )


def seed_runtime_config(generated: GeneratedConfig) -> None:
    """Write an initial runtime release if none exists yet.

    HAProxy and Coraza both read their config from
    `<runtime_root>/current` on startup. Until the first admin "Apply
    config" runs, that symlink does not exist, so Coraza's
    `Include /runtime/current/crs-setup.conf` resolves to nothing and CRS
    fails to load. Called once during backend startup to seed `current`
    from the database state, without reloading anything (no service has
    started yet, so there is nothing to reload).
    """
    runtime_root = Path(settings.runtime_generated_config_root).resolve()
    current_link = runtime_root / "current"

    if (current_link / "crs-setup.conf").exists():
        return

    correlation_id = uuid.uuid4().hex
    candidate_dir = runtime_root / "releases" / correlation_id

    try:
        _sweep_orphaned_temp_links(runtime_root)
        _write_candidate(candidate_dir, generated)
        validation = _validate_haproxy(candidate_dir / "haproxy.cfg")
        if not validation.ok:
            logger.error(
                "config-seed validation failed correlation_id=%s output=%s",
                correlation_id,
                validation.output,
            )
            shutil.rmtree(candidate_dir, ignore_errors=True)
            return
        _swap_current_link(current_link, candidate_dir, runtime_root)
    except OSError:
        logger.exception(
            "config-seed failed correlation_id=%s",
            correlation_id,
        )
        shutil.rmtree(candidate_dir, ignore_errors=True)
        return

    logger.info(
        "config-seed wrote initial runtime config correlation_id=%s",
        correlation_id,
    )


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    output: str


def _write_candidate(candidate_dir: Path, generated: GeneratedConfig) -> None:
    candidate_dir.mkdir(parents=True, exist_ok=False)
    (candidate_dir / "haproxy.cfg").write_text(generated.haproxy_cfg, encoding="utf-8")
    (candidate_dir / "crs-setup.conf").write_text(
        generated.crs_setup_conf,
        encoding="utf-8",
    )
    (candidate_dir / "rule-overrides.conf").write_text(
        generated.rule_overrides_conf,
        encoding="utf-8",
    )
    certs_dir = candidate_dir / "certs"
    certs_dir.mkdir(exist_ok=True)
    for domain, pem in generated.certs.items():
        (certs_dir / f"{domain}.pem").write_text(pem, encoding="utf-8")
    
    # Write a default dummy cert so HAProxy doesn't fail if no certs are present
    if not generated.certs:
        dummy_cert = (
            "-----BEGIN PRIVATE KEY-----\n"
            "MC4CAQAwBQYDK2VwBCIEIKxU2vJ06X1k5d1w7tB6d/m3E9aL4jT2bI0kG9l6F7m8\n"
            "-----END PRIVATE KEY-----\n"
            "-----BEGIN CERTIFICATE-----\n"
            "MIIBBDCCAWugAwIBAgIUW6o6+vK8/J9tXf/mF0M+9qO3ZfswBQYDK2VwMDExLzAt\n"
            "BgNVBAMMJkd1YXJkIFByb3h5IERlZmF1bHQgU2VsZi1TaWduZWQgQ2VydDAeFw0y\n"
            "NDA1MTEwMDAwMDBaFw0zNDA1MDkwMDAwMDBaMDExLzAtBgNVBAMMJkd1YXJkIFBy\n"
            "b3h5IERlZmF1bHQgU2VsZi1TaWduZWQgQ2VydDAqMAUGAytlcAMhAN3fXjP8Cq7y\n"
            "K3+7yL9X4bK7f/n2X5d1w7tB6d/m3E9ao0UwQzAPBgNVHRMBAf8EBTADAQH/MA4G\n"
            "A1UdDwEB/wQEAwIChDAdBgNVHQ4EFgQU0/3fXjP8Cq7yK3+7yL9X4bK7f/n2X5d1\n"
            "MAUGAytlcANBAO/4bK7f/n2X5d1w7tB6d/m3E9aL4jT2bI0kG9l6F7m8K3+7yL9X\n"
            "4bK7f/n2X5d1w7tB6d/m3E9aL4jT2bI0kG9l6F7m8A==\n"
            "-----END CERTIFICATE-----\n"
        )
        (certs_dir / "default.pem").write_text(dummy_cert, encoding="utf-8")


def _validate_haproxy(config_path: Path) -> CommandResult:
    try:
        result = subprocess.run(
            [
                settings.haproxy_validation_binary,
                "-c",
                "-f",
                str(config_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=settings.haproxy_validation_timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return CommandResult(ok=False, output=str(error))

    output = _join_output(result.stdout, result.stderr)
    return CommandResult(ok=result.returncode == 0, output=output)


def _reload_haproxy() -> CommandResult:
    socket_path = settings.haproxy_master_socket_path
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(settings.haproxy_reload_timeout_seconds)
            client.connect(socket_path)
            client.sendall(b"reload\n")
            client.shutdown(socket.SHUT_WR)
            output_chunks: list[bytes] = []
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                output_chunks.append(chunk)
    except OSError as error:
        return CommandResult(ok=False, output=str(error))

    output = b"".join(output_chunks).decode("utf-8", errors="replace").strip()
    # Use an anchored regex so partial-word matches such as "no error" or
    # "warning: failed for ipv6, continuing" are not classified as errors.
    # An empty output (HAProxy 2.7+ returns nothing on success) is treated
    # as success.
    is_error = bool(_RELOAD_ERROR_RE.search(output))
    return CommandResult(ok=not is_error, output=output)


def _swap_current_link(current_link: Path, target: Path, runtime_root: Path) -> None:
    relative_target = os.path.relpath(target, start=runtime_root)
    temp_link = runtime_root / f".current-{uuid.uuid4().hex}.tmp"
    temp_link.symlink_to(relative_target)
    os.replace(temp_link, current_link)


def _read_current_symlink(current_link: Path) -> Path | None:
    if not current_link.exists() and not current_link.is_symlink():
        return None

    if current_link.is_symlink():
        return _resolve_current(current_link)

    # current exists but is a real directory — this is not a supported state.
    # The seed step (container init) is responsible for creating the initial
    # symlink; if it left a directory here instead, the runtime directory is
    # corrupt. Refuse to proceed so the operator is notified immediately
    # rather than silently corrupting the directory layout with a non-atomic
    # move + re-symlink.
    raise RuntimeError(
        f"{current_link} is a directory, not a symlink. "
        "Restore the runtime directory to a clean state and restart the container."
    )


def _resolve_current(current_link: Path) -> Path | None:
    if not current_link.exists() and not current_link.is_symlink():
        return None
    try:
        return current_link.resolve(strict=True)
    except OSError:
        return None


def _sweep_orphaned_temp_links(runtime_root: Path) -> None:
    """Remove any .current-*.tmp symlinks left by a previous crash."""
    for p in runtime_root.glob(".current-*.tmp"):
        try:
            p.unlink()
            logger.debug("swept orphaned temp link %s", p)
        except OSError:
            pass


def _calculate_checksum(generated: GeneratedConfig) -> str:
    digest = hashlib.sha256()
    digest.update(generated.haproxy_cfg.encode("utf-8"))
    digest.update(b"\n---\n")
    digest.update(generated.crs_setup_conf.encode("utf-8"))
    digest.update(b"\n---\n")
    digest.update(generated.rule_overrides_conf.encode("utf-8"))
    return digest.hexdigest()


def _join_output(stdout: str, stderr: str) -> str:
    combined = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    return combined or "<no output>"
