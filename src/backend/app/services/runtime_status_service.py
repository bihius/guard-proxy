"""Service layer for runtime/deployed configuration status."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.policy import Policy, PolicyEnforcementMode
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
from app.services.config_renderer import (
    HaproxyBackend,
    HaproxyRenderContext,
    render_crs_setup,
    render_haproxy_cfg,
    render_rule_overrides,
)

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
        active_vhosts = [vhost for vhost in vhosts if vhost.is_active]

        try:
            active_policy = self._pick_active_policy(
                active_vhosts=active_vhosts,
                policies=policies,
                rule_overrides=rule_overrides,
            )
            context = (
                self._to_haproxy_context(active_vhosts[0]) if active_vhosts else None
            )
            haproxy_cfg = (
                render_haproxy_cfg(context)
                if context is not None
                else render_haproxy_cfg(
                    HaproxyRenderContext(
                        vhost_acl_name="host_app",
                        vhost_hosts=("app.local",),
                        backend=HaproxyBackend(
                            name="be_app",
                            server_name="app",
                            address="backend:8000",
                        ),
                    )
                )
            )
            crs_setup_conf = render_crs_setup(active_policy)
            rule_overrides_conf = render_rule_overrides(active_policy)
        except Exception as error:  # pragma: no cover - defensive conversion
            return RuntimeGeneratedConfigStatus(
                can_generate=False,
                error=str(error),
            )

        return RuntimeGeneratedConfigStatus(
            can_generate=True,
            checksum=self._calculate_checksum(
                haproxy_cfg,
                crs_setup_conf,
                rule_overrides_conf,
            ),
            generated_at=datetime.now(UTC),
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
            return "never_deployed"
        if latest_reload.status == RuntimeOperationStatus.success:
            return "deployed"

        latest_successful_reload = (
            self.db.query(RuntimeOperation.id)
            .filter(RuntimeOperation.operation_type == RuntimeOperationType.reload)
            .filter(RuntimeOperation.status == RuntimeOperationStatus.success)
            .first()
        )
        if latest_successful_reload is None:
            return "never_deployed"
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

    @staticmethod
    def _pick_active_policy(
        *,
        active_vhosts: list[VHost],
        policies: list[Policy],
        rule_overrides: list[RuleOverride],
    ) -> Policy:
        policies_by_id = {policy.id: policy for policy in policies}
        overrides_by_policy_id: dict[int, list[RuleOverride]] = {}
        for override in rule_overrides:
            overrides_by_policy_id.setdefault(override.policy_id, []).append(override)

        for vhost in active_vhosts:
            if vhost.policy_id is None:
                continue
            policy = policies_by_id.get(vhost.policy_id)
            if policy is None or not policy.is_active:
                continue
            policy.rule_overrides = overrides_by_policy_id.get(policy.id, [])
            return policy

        default_policy = Policy(
            id=0,
            name="default-detect-only",
            description="Auto-generated default policy",
            paranoia_level=1,
            inbound_anomaly_threshold=5,
            outbound_anomaly_threshold=4,
            enforcement_mode=PolicyEnforcementMode.detect_only,
            is_active=True,
        )
        default_policy.rule_overrides = []
        return default_policy

    @staticmethod
    def _to_haproxy_context(vhost: VHost) -> HaproxyRenderContext:
        domain_slug = vhost.domain.replace(".", "_").replace("-", "_")
        backend_address = RuntimeStatusService._extract_backend_address(
            vhost.backend_url
        )
        return HaproxyRenderContext(
            vhost_acl_name=f"host_{domain_slug}",
            vhost_hosts=(vhost.domain,),
            backend=HaproxyBackend(
                name=f"be_{domain_slug}",
                server_name=f"srv_{domain_slug}",
                address=backend_address,
            ),
        )

    @staticmethod
    def _extract_backend_address(backend_url: str) -> str:
        parsed = urlparse(backend_url)
        address = parsed.netloc if parsed.scheme else parsed.path
        if not address:
            raise ValueError(f"Invalid backend URL {backend_url!r}: missing host")
        if "@" in address:
            raise ValueError(
                f"Invalid backend URL {backend_url!r}: userinfo is not supported"
            )
        return address
