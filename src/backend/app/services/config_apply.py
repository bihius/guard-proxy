"""Apply generated runtime config with validation, reload, and rollback."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import socket
import subprocess
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.config import settings
from app.services import coraza_probe
from app.services.config_generator import CorazaAppConfig, GeneratedConfig
from app.services.config_renderer import render_coraza_spoa_yaml

# Release layout read by Coraza (see the generated coraza-spoa.yaml):
#   coraza-spoa.yaml
#   coraza/<application>/crs-setup.conf
#   coraza/<application>/rule-overrides.conf
CORAZA_SPOA_YAML = "coraza-spoa.yaml"
CORAZA_APPS_DIR = "coraza"

logger = logging.getLogger(__name__)

# Serialises everything that mutates the live HAProxy runtime: full applies
# and the standalone reload the GeoIP map refresh performs. Reentrant so an
# apply can still call the internal reload helper while holding it.
_apply_lock = threading.RLock()

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
    coraza_reload_failed = "coraza_reload_failed"
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
    with _apply_lock:
        return _apply_locked(generated)


def _apply_locked(generated: GeneratedConfig) -> ApplyResult:
    _ensure_geoip_map_file()
    correlation_id = uuid.uuid4().hex
    checksum = calculate_checksum(generated)
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
        _write_candidate(candidate_dir, generated, runtime_root / "certs")
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

    # HAProxy picks the Coraza application per vhost and coraza-spoa fails
    # closed (503) on a name it does not know, so the two must switch in an
    # order where every name HAProxy sends is loaded in Coraza:
    # - new names: Coraza loads them first, then HAProxy is reloaded;
    # - dropped names: HAProxy stops sending them first, Coraza drops them
    #   when it picks up the release (HAProxy reloads synchronously, Coraza
    #   only on its supervisor's next poll).
    # When a release does both, Coraza first loads a bridge release that also
    # keeps the dropped applications, then the final release once HAProxy no
    # longer references them.
    previous_apps = _release_app_names(previous_target)
    new_apps = {app.name for app in generated.coraza_apps}
    added_apps = new_apps - previous_apps
    retired_apps = previous_apps - new_apps
    bridge_dir: Path | None = None
    if added_apps and retired_apps and previous_target is not None:
        bridge_dir = releases_root / f"{correlation_id}-bridge"
        try:
            _write_bridge(bridge_dir, candidate_dir, previous_target, retired_apps)
        except (OSError, ValueError) as error:
            shutil.rmtree(candidate_dir, ignore_errors=True)
            shutil.rmtree(bridge_dir, ignore_errors=True)
            logger.exception(
                "config-apply bridge write failed correlation_id=%s",
                correlation_id,
            )
            return ApplyResult(
                status=ApplyStatus.write_failed,
                correlation_id=correlation_id,
                checksum=checksum,
                message=f"Failed to prepare candidate files: {error}",
                candidate_path=str(candidate_dir),
                active_path=str(_resolve_current(current_link)),
            )

    _swap_current_link(current_link, bridge_dir or candidate_dir, runtime_root)

    if added_apps:
        coraza_wait = _wait_for_coraza_apps(added_apps)
        if not coraza_wait.ok:
            logger.error(
                "config-apply coraza did not load new applications "
                "correlation_id=%s output=%s",
                correlation_id,
                coraza_wait.output,
            )
            # HAProxy was not reloaded, so restoring the previous release is
            # enough: Coraza picks it up again on its next poll.
            if previous_target is None:
                current_link.unlink(missing_ok=True)
            else:
                _swap_current_link(current_link, previous_target, runtime_root)
            shutil.rmtree(candidate_dir, ignore_errors=True)
            if bridge_dir is not None:
                shutil.rmtree(bridge_dir, ignore_errors=True)
            return ApplyResult(
                status=ApplyStatus.coraza_reload_failed,
                correlation_id=correlation_id,
                checksum=checksum,
                message=(
                    "Coraza did not load the new WAF policies; the previous "
                    "release is still active. Check the coraza container logs."
                ),
                candidate_path=str(candidate_dir),
                active_path=str(_resolve_current(current_link)),
                validation_output=validation.output,
                reload_output=coraza_wait.output,
            )

    reload_result = _reload_haproxy()
    if bridge_dir is not None:
        # Also on reload failure: the rollback below expects `current` to
        # point at the candidate, and the bridge directory is removed.
        _swap_current_link(current_link, candidate_dir, runtime_root)
        shutil.rmtree(bridge_dir, ignore_errors=True)
    if reload_result.ok:
        logger.info(
            "config-apply success correlation_id=%s",
            correlation_id,
        )
        return ApplyResult(
            status=ApplyStatus.success,
            correlation_id=correlation_id,
            checksum=checksum,
            message="Configuration applied.",
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


def seed_runtime_config(generated: GeneratedConfig) -> str | None:
    """Write an initial runtime release if none exists yet.

    HAProxy and Coraza both read their config from
    `<runtime_root>/current` on startup. Until the first admin "Apply
    config" runs, that symlink does not exist, so Coraza's includes under
    `/runtime/current` resolve to nothing and CRS fails to load. Called on
    every backend startup to seed `current` from
    the database state, without reloading anything (no service has started
    yet, so there is nothing to reload).

    Returns the checksum of whatever release is active in `current` once
    this returns (freshly written or pre-existing), or `None` if there is
    no valid active release — the caller uses this to reconcile the
    `RuntimeOperation` log so the "pending changes" comparison in
    `RuntimeStatusService` reflects what's actually deployed, not just what
    was deployed via the last `POST /config/apply` before the most recent
    restart.
    """
    # Must run before the "release already exists" early return below,
    # otherwise an existing deployment upgrading into the GeoIP feature would
    # never get the stub map file that keeps `haproxy -c` passing.
    _ensure_geoip_map_file()
    runtime_root = Path(settings.runtime_generated_config_root).resolve()
    current_link = runtime_root / "current"

    # A real release always contains haproxy.cfg. The container entrypoint
    # seeds a minimal CRS stub (without haproxy.cfg) so Coraza can start
    # before the backend; that stub must be replaced with the full rendered
    # config here, so only skip seeding when a real release is active.
    if (current_link / "haproxy.cfg").exists():
        return _read_active_checksum(current_link)

    correlation_id = uuid.uuid4().hex
    candidate_dir = runtime_root / "releases" / correlation_id

    try:
        _sweep_orphaned_temp_links(runtime_root)
        _write_candidate(candidate_dir, generated, runtime_root / "certs")
        validation = _validate_haproxy(candidate_dir / "haproxy.cfg")
        if not validation.ok:
            logger.error(
                "config-seed validation failed correlation_id=%s output=%s",
                correlation_id,
                validation.output,
            )
            shutil.rmtree(candidate_dir, ignore_errors=True)
            return None
        _swap_current_link(current_link, candidate_dir, runtime_root)
    except OSError:
        logger.exception(
            "config-seed failed correlation_id=%s",
            correlation_id,
        )
        shutil.rmtree(candidate_dir, ignore_errors=True)
        return None

    logger.info(
        "config-seed wrote initial runtime config correlation_id=%s",
        correlation_id,
    )
    return calculate_checksum(generated)


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    output: str


def _ensure_geoip_map_file() -> None:
    """Best-effort stub-write so a read-only/missing runtime dir cannot break apply."""
    from app.services import geoip_service

    try:
        geoip_service.ensure_map_file_exists()
    except OSError as error:
        logger.warning("failed to ensure GeoIP map file exists: %s", error)


def reload_haproxy() -> CommandResult:
    """Reload HAProxy without rewriting the release. Used by the GeoIP map refresh.

    Takes the same lock as `apply()`. The GeoIP refresh runs on its own
    schedule and is serialised by a different lock in the router, so without
    this a refresh could reload HAProxy midway through an apply's
    validate/swap/rollback sequence and activate a release that apply is in
    the middle of reverting.
    """
    with _apply_lock:
        return _reload_haproxy()


def _write_candidate(
    candidate_dir: Path, generated: GeneratedConfig, certs_dir: Path
) -> None:
    _ensure_geoip_map_file()
    candidate_dir.mkdir(parents=True, exist_ok=False)
    (candidate_dir / "haproxy.cfg").write_text(generated.haproxy_cfg, encoding="utf-8")
    (candidate_dir / CORAZA_SPOA_YAML).write_text(
        generated.coraza_spoa_yaml,
        encoding="utf-8",
    )
    for app in generated.coraza_apps:
        app_dir = candidate_dir / CORAZA_APPS_DIR / app.name
        app_dir.mkdir(parents=True)
        (app_dir / "crs-setup.conf").write_text(app.crs_setup_conf, encoding="utf-8")
        (app_dir / "rule-overrides.conf").write_text(
            app.rule_overrides_conf,
            encoding="utf-8",
        )

    # Certificates live in a single shared directory (not per-release) so the
    # absolute `crt` path baked into haproxy.cfg resolves to the same files
    # during backend validation and at HAProxy runtime. The backend reaches it
    # via its runtime root; HAProxy reaches the same volume directory through
    # the `/etc/haproxy/generated/certs` path referenced in the template.
    certs_dir.mkdir(parents=True, exist_ok=True)
    for domain, pem in generated.certs.items():
        (certs_dir / f"{domain}.pem").write_text(pem, encoding="utf-8")
    _ensure_default_cert(certs_dir)


def _ensure_default_cert(certs_dir: Path) -> None:
    """Ensure a loadable fallback certificate exists in the shared certs dir.

    HAProxy's `bind ... ssl crt <dir>` rejects the whole config if the directory
    contains no parseable certificate. When an SSL vhost is enabled before its
    real certificate is provisioned (e.g. a freshly added Let's Encrypt domain),
    no per-domain PEM exists yet, so without a valid fallback `haproxy -c` fails.
    A self-signed certificate is generated once and reused; SNI selects the real
    certificate when present and falls back to this one otherwise.
    """
    default_pem = certs_dir / "default.pem"
    if default_pem.exists():
        return

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "guard-proxy-default")]
    )
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
        .sign(key, hashes.SHA256())
    )
    pem = certificate.public_bytes(serialization.Encoding.PEM) + key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    default_pem.write_bytes(pem)


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


def _wait_for_coraza_apps(app_names: set[str]) -> CommandResult:
    """Wait until coraza-spoa serves every application in `app_names`."""
    missing = coraza_probe.wait_until_served(
        app_names,
        host=settings.coraza_spoa_host,
        port=settings.coraza_spoa_port,
        timeout_seconds=settings.coraza_reload_timeout_seconds,
    )
    if missing:
        return CommandResult(
            ok=False,
            output=(
                f"coraza-spoa at {settings.coraza_spoa_host}:"
                f"{settings.coraza_spoa_port} did not load "
                f"{', '.join(sorted(missing))} within "
                f"{settings.coraza_reload_timeout_seconds}s"
            ),
        )
    return CommandResult(
        ok=True, output=f"coraza-spoa serves {', '.join(sorted(app_names))}"
    )


def _release_app_names(release_dir: Path | None) -> set[str]:
    """Coraza applications of a release (empty for none or a pre-#305 release).

    A release without per-policy applications runs on the image's fallback
    config, whose default_application accepts any name, so it has nothing
    HAProxy could lose.
    """
    if release_dir is None:
        return set()
    apps_dir = release_dir / CORAZA_APPS_DIR
    if not apps_dir.is_dir():
        return set()
    return {entry.name for entry in apps_dir.iterdir() if entry.is_dir()}


def _write_bridge(
    bridge_dir: Path,
    candidate_dir: Path,
    previous_dir: Path,
    retired_apps: set[str],
) -> None:
    """Candidate release plus the previous release's retired applications."""
    shutil.copytree(candidate_dir, bridge_dir)
    for name in retired_apps:
        shutil.copytree(
            previous_dir / CORAZA_APPS_DIR / name,
            bridge_dir / CORAZA_APPS_DIR / name,
        )
    app_names = _release_app_names(candidate_dir) | retired_apps
    (bridge_dir / CORAZA_SPOA_YAML).write_text(
        render_coraza_spoa_yaml(tuple(sorted(app_names)), settings.coraza_log_level),
        encoding="utf-8",
    )


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


def calculate_checksum(generated: GeneratedConfig) -> str:
    """Digest used to detect drift between DB-generated and deployed config.

    Shared by `apply()` here and by `RuntimeStatusService` (which computes it
    for the current DB state on every `/runtime/status` call) so there is a
    single source of truth for what "the same config" means.
    """
    digest = hashlib.sha256()
    digest.update(generated.haproxy_cfg.encode("utf-8"))
    digest.update(b"\n---\n")
    digest.update(generated.coraza_spoa_yaml.encode("utf-8"))
    for app in sorted(generated.coraza_apps, key=lambda app: app.name):
        digest.update(f"\n--- {app.name}\n".encode())
        digest.update(app.crs_setup_conf.encode("utf-8"))
        digest.update(b"\n---\n")
        digest.update(app.rule_overrides_conf.encode("utf-8"))
    return digest.hexdigest()


def _read_active_checksum(current_link: Path) -> str | None:
    """Checksum of whatever release `current` actually points to, if any.

    None for releases written before per-policy Coraza applications existed:
    they differ from anything generated now, so they show as pending changes.
    """
    active_dir = _resolve_current(current_link)
    if active_dir is None:
        return None
    try:
        haproxy_cfg = (active_dir / "haproxy.cfg").read_text(encoding="utf-8")
        coraza_spoa_yaml = (active_dir / CORAZA_SPOA_YAML).read_text(encoding="utf-8")
        coraza_apps = tuple(
            CorazaAppConfig(
                name=app_dir.name,
                crs_setup_conf=(app_dir / "crs-setup.conf").read_text(
                    encoding="utf-8"
                ),
                rule_overrides_conf=(app_dir / "rule-overrides.conf").read_text(
                    encoding="utf-8"
                ),
            )
            for app_dir in (active_dir / CORAZA_APPS_DIR).iterdir()
        )
    except OSError:
        return None
    return calculate_checksum(
        GeneratedConfig(
            haproxy_cfg=haproxy_cfg,
            coraza_spoa_yaml=coraza_spoa_yaml,
            coraza_apps=coraza_apps,
            certs={},
        )
    )


def _join_output(stdout: str, stderr: str) -> str:
    combined = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    return combined or "<no output>"
