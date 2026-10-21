"""Service layer for runtime/deployed configuration status."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.constants.versions import CRS_VERSION
from app.models.custom_rule import CustomRule
from app.models.policy import Policy
from app.models.policy_binding import PolicyBinding
from app.models.rule_exclusion import RuleExclusion
from app.models.rule_override import RuleOverride
from app.models.runtime_operation import (
    RuntimeOperationStatus,
    RuntimeOperationType,
    get_latest_operation,
)
from app.models.vhost import VHost
from app.schemas.runtime_status import (
    ActiveRuntimeConfig,
    CorazaConfigSource,
    DeploymentState,
    HaproxyConfigSource,
    RuntimeGeneratedConfigStatus,
    RuntimeOperationSnapshot,
    RuntimeStatusResponse,
    VersionAgreement,
)
from app.services.config_apply import (
    CORAZA_SPOA_YAML,
    SEED_RELEASE_NAME,
    calculate_checksum,
)
from app.services.config_generator import generate
from app.services.config_version import (
    check_seed_config,
    configured_image_tag,
    image_tag_warning,
)
from app.version import APP_VERSION

_FRONTEND_CONTRACT_VERSION = "1"


def classify_active_release(
    current_link: Path,
) -> tuple[HaproxyConfigSource, CorazaConfigSource]:
    """Return `(haproxy_source, coraza_source)` for the active runtime release.

    `haproxy_source` is `seed` while HAProxy serves the checked-in demo config
    (the `releases/seed` placeholder) and `missing` when no release is
    deployed. `coraza_source` is `fallback` while the active release has no
    generated `coraza-spoa.yaml`, which is what makes Coraza use the single
    application baked into its image.
    """
    absent: tuple[HaproxyConfigSource, CorazaConfigSource] = ("missing", "fallback")
    try:
        release = current_link.resolve(strict=True)
    except OSError:
        return absent
    if not release.is_dir():
        return absent
    haproxy_source: HaproxyConfigSource = (
        "seed" if release.name == SEED_RELEASE_NAME else "generated"
    )
    coraza_source: CorazaConfigSource = (
        "generated" if (release / CORAZA_SPOA_YAML).is_file() else "fallback"
    )
    return haproxy_source, coraza_source


def _active_config_warning(
    haproxy_source: HaproxyConfigSource,
    coraza_source: CorazaConfigSource,
    seed_config_detail: str | None = None,
) -> str | None:
    parts: list[str] = []
    if haproxy_source == "seed":
        parts.append(
            "HAProxy is serving the demo seed configuration, not a configuration "
            "generated from the database."
        )
    elif haproxy_source == "missing":
        parts.append(
            "No release is deployed; HAProxy is serving its startup configuration."
        )
    if coraza_source == "fallback":
        parts.append(
            "Coraza is running the single application baked into its image: every "
            "request is inspected at paranoia level 1 in detect-only mode and "
            "per-policy settings are ignored."
        )
    if seed_config_detail is not None:
        parts.append(seed_config_detail)
    return " ".join(parts) or None


class RuntimeStatusService:
    """Read-only status assembly for runtime and deployed configuration."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_runtime_status(self) -> RuntimeStatusResponse:
        """Return status payload used by the backend API and frontend dashboard."""
        latest_validation = self._get_latest_operation(RuntimeOperationType.validation)
        latest_reload = self._get_latest_operation(RuntimeOperationType.reload)
        generated_config = self._build_generated_config_status()
        deployment_state = self._derive_deployment_state(latest_reload)

        return RuntimeStatusResponse(
            frontend_contract_version=_FRONTEND_CONTRACT_VERSION,
            deployment_state=deployment_state,
            generated_config=generated_config,
            active_config=self._build_active_config_status(),
            version_agreement=VersionAgreement(
                app_version=APP_VERSION,
                configured_image_tag=configured_image_tag(),
                crs_version=CRS_VERSION,
                warning=image_tag_warning(),
            ),
            latest_validation=latest_validation,
            latest_reload=latest_reload,
        )

    def _build_active_config_status(self) -> ActiveRuntimeConfig:
        """Report which config HAProxy and Coraza are actually running from.

        Read from the runtime volume, so this reflects the active release, not
        what a running process loaded earlier. A process that loaded the seed
        before the backend replaced it stays on the old config until the next
        reload.
        """
        current_link = Path(settings.runtime_generated_config_root) / "current"
        haproxy_source, coraza_source = classify_active_release(current_link)
        seed_config_detail = check_seed_config().detail
        degraded = (
            haproxy_source != "generated"
            or coraza_source != "generated"
            or seed_config_detail is not None
        )
        return ActiveRuntimeConfig(
            haproxy_source=haproxy_source,
            coraza_source=coraza_source,
            degraded=degraded,
            warning=_active_config_warning(
                haproxy_source, coraza_source, seed_config_detail
            ),
        )

    def _build_generated_config_status(self) -> RuntimeGeneratedConfigStatus:
        vhosts = (
            self.db.query(VHost)
            .options(selectinload(VHost.backends))
            .order_by(VHost.domain.asc())
            .all()
        )
        policies = self.db.query(Policy).order_by(Policy.id.asc()).all()
        rule_overrides = (
            self.db.query(RuleOverride).order_by(RuleOverride.id.asc()).all()
        )
        rule_exclusions = (
            self.db.query(RuleExclusion).order_by(RuleExclusion.id.asc()).all()
        )
        custom_rules = self.db.query(CustomRule).order_by(CustomRule.id.asc()).all()
        policy_bindings = (
            self.db.query(PolicyBinding).order_by(PolicyBinding.id.asc()).all()
        )
        active_vhosts = [vhost for vhost in vhosts if vhost.is_active]
        # Compute before calling generate() so they appear in the response
        # regardless of whether generation succeeds or fails.
        unbound_vhost_domains = [
            v.domain for v in active_vhosts if v.policy_id is None
        ] or None

        try:
            generated = generate(
                vhosts,
                policies,
                rule_overrides,
                rule_exclusions,
                custom_rules,
                policy_bindings,
            )
        except Exception as error:  # pragma: no cover - defensive conversion
            return RuntimeGeneratedConfigStatus(
                can_generate=False,
                error=str(error),
                unbound_vhost_domains=unbound_vhost_domains,
            )

        return RuntimeGeneratedConfigStatus(
            can_generate=True,
            checksum=calculate_checksum(generated),
            generated_at=datetime.now(UTC),
            unbound_vhost_domains=unbound_vhost_domains,
        )

    def _get_latest_operation(
        self, operation_type: RuntimeOperationType
    ) -> RuntimeOperationSnapshot | None:
        record = get_latest_operation(self.db, operation_type)
        if record is None:
            return None

        return RuntimeOperationSnapshot.model_validate(record, from_attributes=True)

    def _derive_deployment_state(
        self,
        latest_reload: RuntimeOperationSnapshot | None,
    ) -> DeploymentState:
        if latest_reload is None:
            # No reload has ever been attempted via the API.
            return "never_deployed"
        if latest_reload.status == RuntimeOperationStatus.success:
            return "deployed"
        # Latest reload was not successful. Whether or not a prior apply ever
        # succeeded, the current state is "failed" — not "never_deployed".
        # Returning "never_deployed" here was incorrect because a reload WAS
        # attempted; it just failed.
        return "failed"
