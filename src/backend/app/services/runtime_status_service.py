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
    CrsPolicyRenderContext,
    HaproxyBackend,
    HaproxyRenderContext,
    HaproxyRoute,
    RuleOverrideRenderContext,
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
        # Compute before calling _pick_active_policy so they appear in the
        # response regardless of whether generation succeeds or fails.
        unbound_vhost_domains = [
            v.domain for v in active_vhosts if v.policy_id is None
        ] or None

        try:
            active_policy, active_overrides = self._pick_active_policy(
                active_vhosts=active_vhosts,
                policies=policies,
                rule_overrides=rule_overrides,
            )
            context = self._to_haproxy_context(active_vhosts)
            haproxy_cfg = render_haproxy_cfg(context)
            crs_setup_conf = render_crs_setup(active_policy)
            rule_overrides_conf = render_rule_overrides(active_overrides)
        except Exception as error:  # pragma: no cover - defensive conversion
            return RuntimeGeneratedConfigStatus(
                can_generate=False,
                error=str(error),
                unbound_vhost_domains=unbound_vhost_domains,
            )

        return RuntimeGeneratedConfigStatus(
            can_generate=True,
            checksum=self._calculate_checksum(
                haproxy_cfg,
                crs_setup_conf,
                rule_overrides_conf,
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

    @staticmethod
    def _pick_active_policy(
        *,
        active_vhosts: list[VHost],
        policies: list[Policy],
        rule_overrides: list[RuleOverride],
    ) -> tuple[CrsPolicyRenderContext, tuple[RuleOverrideRenderContext, ...]]:
        policies_by_id = {policy.id: policy for policy in policies}
        overrides_by_policy_id: dict[int, list[RuleOverride]] = {}
        for override in rule_overrides:
            overrides_by_policy_id.setdefault(override.policy_id, []).append(override)

        effective_policy_ids: set[int] = set()
        for vhost in active_vhosts:
            if vhost.policy_id is None:
                # Policy-less vhosts are served using the default CRS context.
                # Do NOT add a sentinel 0 here — that caused "policy id 0" to
                # appear in the multiple-policy error message when mixed with
                # policy-bound vhosts.
                continue

            policy = policies_by_id.get(vhost.policy_id)
            if policy is None:
                raise ValueError(
                    f"Active vhost {vhost.domain!r} references missing policy "
                    f"{vhost.policy_id}"
                )
            if not policy.is_active:
                raise ValueError(
                    f"Active vhost {vhost.domain!r} references inactive policy "
                    f"{policy.id}"
                )
            effective_policy_ids.add(policy.id)

        if len(effective_policy_ids) > 1:
            policy_list = ", ".join(
                str(policy_id) for policy_id in sorted(effective_policy_ids)
            )
            raise ValueError(
                "Generated config supports one active CRS policy for MVP; "
                f"found effective policies: {policy_list}"
            )

        effective_policy_id = next(iter(effective_policy_ids), None)
        if effective_policy_id is None:
            # No policy-bound vhosts; use the default CRS context.
            return (
                CrsPolicyRenderContext(
                    paranoia_level=1,
                    inbound_anomaly_threshold=5,
                    outbound_anomaly_threshold=4,
                    enforcement_mode=PolicyEnforcementMode.detect_only,
                ),
                (),
            )

        policy = policies_by_id[effective_policy_id]
        return (
            RuntimeStatusService._to_crs_policy_context(policy),
            RuntimeStatusService._to_rule_override_contexts(
                overrides_by_policy_id.get(policy.id, [])
            ),
        )

    @staticmethod
    def _to_haproxy_context(active_vhosts: list[VHost]) -> HaproxyRenderContext:
        if not active_vhosts:
            return HaproxyRenderContext(
                routes=(
                    HaproxyRoute(
                        vhost_acl_name="host_app",
                        vhost_hosts=("app.local", "localhost", "127.0.0.1"),
                        backend=HaproxyBackend(
                            name="be_app",
                            server_name="app",
                            address="backend:8000",
                        ),
                    ),
                )
            )

        return HaproxyRenderContext(
            routes=tuple(
                RuntimeStatusService._to_haproxy_route(vhost)
                for vhost in active_vhosts
            )
        )

    @staticmethod
    def _to_haproxy_route(vhost: VHost) -> HaproxyRoute:
        if vhost.id is None:
            raise ValueError(f"Active vhost {vhost.domain!r} has no persisted id")
        suffix = f"vhost_{vhost.id}"
        backend_address = RuntimeStatusService._extract_backend_address(
            vhost.backend_url
        )
        return HaproxyRoute(
            vhost_acl_name=f"host_{suffix}",
            vhost_hosts=(vhost.domain,),
            backend=HaproxyBackend(
                name=f"be_{suffix}",
                server_name=f"srv_{suffix}",
                address=backend_address,
            ),
        )

    @staticmethod
    def _to_crs_policy_context(policy: Policy) -> CrsPolicyRenderContext:
        return CrsPolicyRenderContext(
            paranoia_level=policy.paranoia_level,
            inbound_anomaly_threshold=policy.inbound_anomaly_threshold,
            outbound_anomaly_threshold=policy.outbound_anomaly_threshold,
            enforcement_mode=policy.enforcement_mode,
        )

    @staticmethod
    def _to_rule_override_contexts(
        overrides: list[RuleOverride],
    ) -> tuple[RuleOverrideRenderContext, ...]:
        return tuple(
            RuleOverrideRenderContext(
                rule_id=override.rule_id,
                action=override.action,
            )
            for override in overrides
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
