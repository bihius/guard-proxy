"""Pure configuration generator from pre-fetched ORM objects."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.models.custom_rule import CustomRule
from app.models.policy import Policy, PolicyEnforcementMode
from app.models.policy_binding import PolicyBinding
from app.models.rule_exclusion import RuleExclusion
from app.models.rule_override import RuleOverride
from app.models.vhost import VHost
from app.services.config_renderer import (
    CrsPolicyRenderContext,
    CustomRuleRenderContext,
    HaproxyBackend,
    HaproxyDdos,
    HaproxyRenderContext,
    HaproxyRoute,
    HaproxyServer,
    RuleExclusionRenderContext,
    RuleOverrideRenderContext,
    render_crs_setup,
    render_haproxy_cfg_multi,
    render_rule_overrides,
)


@dataclass(frozen=True)
class GeneratedConfig:
    """All generated text files needed by the runtime stack."""

    haproxy_cfg: str
    crs_setup_conf: str
    rule_overrides_conf: str
    certs: dict[str, str]


def generate(
    vhosts: list[VHost],
    policies: list[Policy],
    rule_overrides: list[RuleOverride],
    rule_exclusions: list[RuleExclusion] | None = None,
    custom_rules: list[CustomRule] | None = None,
    policy_bindings: list[PolicyBinding] | None = None,
) -> GeneratedConfig:
    """Generate all runtime config files from already loaded objects."""
    rule_exclusions = rule_exclusions or []
    custom_rules = custom_rules or []
    policy_bindings = policy_bindings or []
    active_vhosts = sorted(
        (vhost for vhost in vhosts if vhost.is_active),
        key=lambda vhost: vhost.domain,
    )
    policies_by_id = {policy.id: policy for policy in policies}

    def _policy_for_vhost(vhost: VHost) -> Policy | None:
        if vhost.policy_id is None:
            return None
        return policies_by_id.get(vhost.policy_id)

    vhost_contexts = [
        _to_haproxy_context(vhost, _policy_for_vhost(vhost))
        for vhost in active_vhosts
    ]

    active_policy, active_overrides, active_exclusions, active_custom_rules = (
        _pick_active_policy(
            active_vhosts,
            policies,
            rule_overrides,
            rule_exclusions,
            custom_rules,
            policy_bindings,
        )
    )
    haproxy_cfg = render_haproxy_cfg_multi(vhost_contexts)
    crs_setup_conf = render_crs_setup(active_policy)
    rule_overrides_conf = render_rule_overrides(
        active_overrides,
        active_exclusions,
        active_custom_rules,
    )

    certs = {}
    for vhost in active_vhosts:
        if vhost.ssl_enabled and vhost.ssl_cert and vhost.ssl_key:
            certs[vhost.domain] = f"{vhost.ssl_cert}\n{vhost.ssl_key}"

    return GeneratedConfig(
        haproxy_cfg=haproxy_cfg,
        crs_setup_conf=crs_setup_conf,
        rule_overrides_conf=rule_overrides_conf,
        certs=certs,
    )


def _pick_active_policy(
    active_vhosts: list[VHost],
    policies: list[Policy],
    rule_overrides: list[RuleOverride],
    rule_exclusions: list[RuleExclusion] | None = None,
    custom_rules: list[CustomRule] | None = None,
    policy_bindings: list[PolicyBinding] | None = None,
) -> tuple[
    CrsPolicyRenderContext,
    tuple[RuleOverrideRenderContext, ...],
    tuple[RuleExclusionRenderContext, ...],
    tuple[CustomRuleRenderContext, ...],
]:
    rule_exclusions = rule_exclusions or []
    custom_rules = custom_rules or []
    policy_bindings = policy_bindings or []
    policies_by_id = {policy.id: policy for policy in policies}
    overrides_by_policy_id: dict[int, list[RuleOverride]] = {}
    for override in rule_overrides:
        overrides_by_policy_id.setdefault(override.policy_id, []).append(override)
    exclusions_by_policy_id: dict[int, list[RuleExclusion]] = {}
    for exclusion in rule_exclusions:
        exclusions_by_policy_id.setdefault(exclusion.policy_id, []).append(exclusion)
    custom_rules_by_policy_id: dict[int, list[CustomRule]] = {}
    for custom_rule in custom_rules:
        custom_rules_by_policy_id.setdefault(custom_rule.policy_id, []).append(
            custom_rule
        )
    bindings_by_vhost_id: dict[int, list[PolicyBinding]] = {}
    for binding in policy_bindings:
        bindings_by_vhost_id.setdefault(binding.vhost_id, []).append(binding)

    effective_policy_ids: set[int] = set()
    for vhost in active_vhosts:
        if vhost.policy_id is not None:
            _add_effective_policy_id(
                effective_policy_ids,
                policies_by_id,
                vhost.policy_id,
                f"Active vhost {vhost.domain!r}",
            )
        if vhost.id is None:
            continue
        for binding in bindings_by_vhost_id.get(vhost.id, []):
            _add_effective_policy_id(
                effective_policy_ids,
                policies_by_id,
                binding.policy_id,
                (
                    f"Path binding {binding.path_prefix!r} on active vhost "
                    f"{vhost.domain!r}"
                ),
            )

    if len(effective_policy_ids) > 1:
        policy_list = ", ".join(
            str(policy_id) for policy_id in sorted(effective_policy_ids)
        )
        raise ValueError(
            "Generated config supports one active CRS policy for MVP; "
            f"found effective policies: {policy_list}"
        )

    effective_policy_id = next(iter(effective_policy_ids), None)
    if effective_policy_id is not None:
        policy = policies_by_id[effective_policy_id]
        return (
            _to_crs_policy_context(policy),
            _to_rule_override_contexts(
                overrides_by_policy_id.get(effective_policy_id, [])
            ),
            _to_rule_exclusion_contexts(
                exclusions_by_policy_id.get(effective_policy_id, [])
            ),
            _to_custom_rule_contexts(
                custom_rules_by_policy_id.get(effective_policy_id, [])
            ),
        )

    return (
        CrsPolicyRenderContext(
            paranoia_level=1,
            inbound_anomaly_threshold=5,
            outbound_anomaly_threshold=4,
            enforcement_mode=PolicyEnforcementMode.detect_only,
        ),
        (),
        (),
        (),
    )


def _add_effective_policy_id(
    effective_policy_ids: set[int],
    policies_by_id: dict[int, Policy],
    policy_id: int,
    owner: str,
) -> None:
    policy = policies_by_id.get(policy_id)
    if policy is None:
        raise ValueError(f"{owner} references missing policy {policy_id}")
    if not policy.is_active:
        raise ValueError(f"{owner} references inactive policy {policy.id}")
    if policy.id is None:
        raise ValueError(f"{owner} references unpersisted policy")
    effective_policy_ids.add(policy.id)


def _to_haproxy_context(
    vhost: VHost, policy: Policy | None
) -> HaproxyRenderContext:
    if vhost.id is None:
        raise ValueError(f"Active vhost {vhost.domain!r} has no persisted id")
    # Use the database id as the naming suffix so that domain names that only
    # differ by '.' vs '-' (e.g. "app.local" and "app-local") never produce
    # colliding ACL or backend identifiers.  This matches the strategy used
    # by RuntimeStatusService._to_haproxy_route.
    suffix = f"vhost_{vhost.id}"
    server_payloads = _to_haproxy_servers(vhost, suffix)
    health_check_path = next(
        (
            health_check_path
            for (
                _server_name,
                _address,
                health_check_path,
                health_check_enabled,
                _interval_seconds,
                _fall,
                _rise,
            ) in server_payloads
            if health_check_enabled
        ),
        "/",
    )
    ddos = (
        HaproxyDdos(
            enabled=True,
            stick_table_name=f"st_ddos_{suffix}",
            rate_limit_requests=policy.rate_limit_requests,
            rate_limit_window_seconds=policy.rate_limit_window_seconds,
            max_connections_per_ip=policy.max_connections_per_ip,
        )
        if policy is not None and policy.ddos_protection_enabled
        else None
    )

    return HaproxyRenderContext(
        routes=(
            HaproxyRoute(
                vhost_acl_name=f"host_{suffix}",
                vhost_hosts=(vhost.domain,),
                ssl_provider=vhost.ssl_provider if vhost.ssl_enabled else "none",
                ddos=ddos,
                backend=HaproxyBackend(
                    name=f"be_{suffix}",
                    health_check_path=health_check_path,
                    servers=tuple(
                        HaproxyServer(
                            server_name=server_name,
                            address=address,
                            health_check_enabled=health_check_enabled,
                            health_check_interval_seconds=interval_seconds,
                            health_check_fall=fall,
                            health_check_rise=rise,
                        )
                        for (
                            server_name,
                            address,
                            _health_check_path,
                            health_check_enabled,
                            interval_seconds,
                            fall,
                            rise,
                        ) in server_payloads
                    ),
                ),
            ),
        )
    )


def _to_haproxy_servers(
    vhost: VHost,
    suffix: str,
) -> list[tuple[str, str, str, bool, int, int, int]]:
    all_backends = list(getattr(vhost, "backends", []))
    active_backends = [backend for backend in all_backends if backend.is_active]
    if not all_backends and vhost.backend_url:
        return [
            (
                f"srv_{suffix}",
                _extract_backend_address(vhost.backend_url),
                "/",
                True,
                5,
                3,
                2,
            )
        ]
    if not active_backends:
        raise ValueError(f"Active vhost {vhost.domain!r} has no active backends")

    health_check_paths = {
        backend.health_check_path
        for backend in active_backends
        if backend.health_check_enabled
    }
    if len(health_check_paths) > 1:
        raise ValueError(
            f"Active vhost {vhost.domain!r} has multiple health check paths; "
            "HAProxy supports one httpchk path per backend section"
        )

    return [
        (
            f"srv_{suffix}_{index}",
            _extract_backend_address(backend.url),
            backend.health_check_path,
            backend.health_check_enabled,
            backend.health_check_interval_seconds,
            backend.health_check_fall,
            backend.health_check_rise,
        )
        for index, backend in enumerate(active_backends, start=1)
    ]


def _to_crs_policy_context(policy: Policy) -> CrsPolicyRenderContext:
    return CrsPolicyRenderContext(
        paranoia_level=policy.paranoia_level,
        inbound_anomaly_threshold=policy.inbound_anomaly_threshold,
        outbound_anomaly_threshold=policy.outbound_anomaly_threshold,
        enforcement_mode=policy.enforcement_mode,
    )


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


def _to_rule_exclusion_contexts(
    exclusions: list[RuleExclusion],
) -> tuple[RuleExclusionRenderContext, ...]:
    control_rule_ids = _control_rule_ids_for_scoped_exclusions(exclusions)
    return tuple(
        RuleExclusionRenderContext(
            rule_id=exclusion.rule_id,
            target_type=exclusion.target_type,
            target_value=exclusion.target_value,
            scope_path=exclusion.scope_path,
            control_rule_id=control_rule_ids.get(id(exclusion)),
        )
        for exclusion in exclusions
    )


def _control_rule_ids_for_scoped_exclusions(
    exclusions: list[RuleExclusion],
) -> dict[int, int]:
    assigned: dict[int, int] = {}
    for exclusion in exclusions:
        if exclusion.scope_path is None:
            continue
        if exclusion.id is None:
            raise ValueError(
                "Path-scoped rule exclusion has no persisted id; "
                "control rule ids require a persisted RuleExclusion"
            )
        assigned[id(exclusion)] = 9100000 + exclusion.id
    return assigned


def _to_custom_rule_contexts(
    custom_rules: list[CustomRule],
) -> tuple[CustomRuleRenderContext, ...]:
    return tuple(
        CustomRuleRenderContext(
            rule_id=custom_rule.rule_id,
            phase=custom_rule.phase,
            variables=custom_rule.variables,
            operator=custom_rule.operator,
            operator_argument=custom_rule.operator_argument,
            actions=custom_rule.actions,
            is_active=custom_rule.is_active,
        )
        for custom_rule in custom_rules
    )


def _extract_backend_address(backend_url: str) -> str:
    parsed = urlparse(backend_url)
    
    if parsed.scheme:
        host = parsed.hostname
        if host is None:
            raise ValueError(f"Invalid backend URL {backend_url!r}: missing host")
        port = parsed.port
        if not port:
            port = 443 if parsed.scheme == "https" else 80
        address = f"{host}:{port}"
    else:
        address = parsed.path
        if ":" not in address:
            address = f"{address}:80"

    if not address or address.startswith(":"):
        raise ValueError(f"Invalid backend URL {backend_url!r}: missing host")
    if "@" in address:
        raise ValueError(
            f"Invalid backend URL {backend_url!r}: userinfo is not supported"
        )
    return address
