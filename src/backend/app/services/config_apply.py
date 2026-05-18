"""Apply generated runtime config with validation, reload, and rollback."""

from __future__ import annotations

import hashlib
import logging
import os
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


class ApplyStatus(StrEnum):
    """Outcome classes for config apply attempts."""

    success = "success"
    write_failed = "write_failed"
    validation_failed = "validation_failed"
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
    previous_target = _read_current_symlink(current_link)

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
        logger.info("config-apply success correlation_id=%s", correlation_id)
        return ApplyResult(
            status=ApplyStatus.success,
            correlation_id=correlation_id,
            checksum=checksum,
            message="Configuration applied and HAProxy reloaded successfully.",
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
        return ApplyResult(
            status=ApplyStatus.rollback_failed,
            correlation_id=correlation_id,
            checksum=checksum,
            message="Reload failed and no previous release exists for rollback.",
            candidate_path=str(candidate_dir),
            active_path=str(_resolve_current(current_link)),
            validation_output=validation.output,
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
    output_lower = output.lower()
    _error_keywords = ("error", "fail", "denied", "permission")
    is_error = any(kw in output_lower for kw in _error_keywords)
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

    backup_dir = current_link.with_name(f"current-backup-{uuid.uuid4().hex}")
    shutil.move(str(current_link), str(backup_dir))
    current_link.symlink_to(os.path.relpath(backup_dir, start=current_link.parent))
    return backup_dir.resolve()


def _resolve_current(current_link: Path) -> Path | None:
    if not current_link.exists() and not current_link.is_symlink():
        return None
    try:
        return current_link.resolve(strict=True)
    except OSError:
        return None


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
