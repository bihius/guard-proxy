"""Service layer for runtime/deployed configuration status."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.custom_rule import CustomRule
from app.models.policy import Policy
from app.models.policy_binding import PolicyBinding
from app.models.rule_exclusion import RuleExclusion
from app.models.rule_override import RuleOverride
from app.models.runtime_operation import (
    RuntimeOperation,
    RuntimeOperationStatus,
    RuntimeOperationType,
)
from app.models.vhost import VHost
from app.schemas.runtime_status import (
    DeploymentState,
    RuntimeGeneratedConfigStatus,
    RuntimeOperationSnapshot,
    RuntimeStatusResponse,
)
from app.services.config_generator import generate

_FRONTEND_CONTRACT_VERSION = "1"


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
            latest_validation=latest_validation,
            latest_reload=latest_reload,
        )

    def _build_generated_config_status(self) -> RuntimeGeneratedConfigStatus:
        vhosts = self.db.query(VHost).order_by(VHost.domain.asc()).all()
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
        # Compute before calling _pick_active_policy so they appear in the
        # response regardless of whether generation succeeds or fails.
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
            checksum=self._calculate_checksum(
                generated.haproxy_cfg,
                generated.crs_setup_conf,
                generated.rule_overrides_conf,
            ),
            generated_at=datetime.now(UTC),
            unbound_vhost_domains=unbound_vhost_domains,
        )

    def _get_latest_operation(
        self, operation_type: RuntimeOperationType
    ) -> RuntimeOperationSnapshot | None:
        record = (
            self.db.query(RuntimeOperation)
            .filter(RuntimeOperation.operation_type == operation_type)
            .order_by(RuntimeOperation.created_at.desc(), RuntimeOperation.id.desc())
            .first()
        )
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

    @staticmethod
    def _calculate_checksum(
        haproxy_cfg: str,
        crs_setup_conf: str,
        rule_overrides_conf: str,
    ) -> str:
        digest = hashlib.sha256()
        digest.update(haproxy_cfg.encode("utf-8"))
        digest.update(b"\n---\n")
        digest.update(crs_setup_conf.encode("utf-8"))
        digest.update(b"\n---\n")
        digest.update(rule_overrides_conf.encode("utf-8"))
        return digest.hexdigest()

