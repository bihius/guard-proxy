"""Pure configuration generator from pre-fetched ORM objects."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import settings
from app.models.custom_rule import CustomRule
from app.models.policy import Policy, PolicyEnforcementMode, PolicyGeoipMode
from app.models.policy_binding import PolicyBinding
from app.models.rule_exclusion import RuleExclusion
from app.models.rule_override import RuleOverride
from app.models.vhost import VHost
from app.services.config_renderer import (
    CORAZA_DEFAULT_APP,
    SCOPE_MATCHERS_PER_EXCLUSION,
    CrsPolicyRenderContext,
    CustomRuleRenderContext,
    HaproxyBackend,
    HaproxyDdos,
    HaproxyGeoip,
    HaproxyRenderContext,
    HaproxyRoute,
    HaproxyServer,
    RuleExclusionRenderContext,
    RuleOverrideRenderContext,
    render_coraza_spoa_yaml,
    render_crs_setup,
    render_haproxy_cfg_multi,
    render_rule_overrides,
)

# Stable, non-versioned path on the shared `generated_config` volume. The
# backend writes it at <runtime_root>/geoip/country.map; HAProxy reads the
# same file through /etc/haproxy/generated. Deliberately outside
# releases/<id>/ because the map is refreshed on its own daily schedule.
HAPROXY_GEOIP_MAP_PATH = "/etc/haproxy/generated/geoip/country.map"

logger = logging.getLogger(__name__)


# CRS settings for vhosts without a policy: CRS defaults, log only.
_UNASSIGNED_CRS_POLICY = CrsPolicyRenderContext(
    paranoia_level=1,
    inbound_anomaly_threshold=5,
    outbound_anomaly_threshold=4,
    enforcement_mode=PolicyEnforcementMode.detect_only,
)


@dataclass(frozen=True)
class CorazaAppConfig:
    """Generated files of one Coraza application (one WAF instance)."""

    name: str
    crs_setup_conf: str
    rule_overrides_conf: str


@dataclass(frozen=True)
class GeneratedConfig:
    """All generated text files needed by the runtime stack."""

    haproxy_cfg: str
    coraza_spoa_yaml: str
    # The default application first, then one per policy in policy id order.
    coraza_apps: tuple[CorazaAppConfig, ...]
    certs: dict[str, str]


def coraza_app_name(policy: Policy | None) -> str:
    """Coraza application that enforces `policy` (None: unassigned vhosts)."""
    return CORAZA_DEFAULT_APP if policy is None else f"policy_{policy.id}"


def generate(
    vhosts: list[VHost],
    policies: list[Policy],
    rule_overrides: list[RuleOverride],
    rule_exclusions: list[RuleExclusion] | None = None,
    custom_rules: list[CustomRule] | None = None,
    policy_bindings: list[PolicyBinding] | None = None,
) -> GeneratedConfig:
    """Generate all runtime config files from already loaded objects.

    Every policy assigned to an active vhost becomes its own Coraza
    application, so each vhost is inspected only with its own policy's CRS
    settings, rule overrides, exclusions, and custom rules.
    """
    active_vhosts = sorted(
        (vhost for vhost in vhosts if vhost.is_active),
        key=lambda vhost: vhost.domain,
    )
    policies_by_id = {policy.id: policy for policy in policies}
    policy_by_vhost_id = {
        vhost.id: _vhost_policy(vhost, policies_by_id) for vhost in active_vhosts
    }
    _reject_path_scoped_policies(active_vhosts, policy_bindings or [])

    vhost_contexts = [
        _to_haproxy_context(vhost, policy_by_vhost_id[vhost.id])
        for vhost in active_vhosts
    ]
    effective_policies = sorted(
        {
            policy.id: policy
            for policy in policy_by_vhost_id.values()
            if policy is not None
        }.values(),
        key=lambda policy: policy.id,
    )
    overrides_by_policy_id = _group_by_policy_id(rule_overrides)
    exclusions_by_policy_id = _group_by_policy_id(rule_exclusions or [])
    custom_rules_by_policy_id = _group_by_policy_id(custom_rules or [])
    coraza_apps = (
        CorazaAppConfig(
            name=CORAZA_DEFAULT_APP,
            crs_setup_conf=render_crs_setup(_UNASSIGNED_CRS_POLICY),
            rule_overrides_conf=render_rule_overrides(()),
        ),
        *(
            _to_coraza_app(
                policy,
                overrides_by_policy_id.get(policy.id, []),
                exclusions_by_policy_id.get(policy.id, []),
                custom_rules_by_policy_id.get(policy.id, []),
            )
            for policy in effective_policies
        ),
    )

    certs = {}
    for vhost in active_vhosts:
        if vhost.ssl_enabled and vhost.ssl_cert and vhost.ssl_key:
            certs[vhost.domain] = f"{vhost.ssl_cert}\n{vhost.ssl_key}"

    return GeneratedConfig(
        haproxy_cfg=render_haproxy_cfg_multi(vhost_contexts),
        coraza_spoa_yaml=render_coraza_spoa_yaml(
            tuple(app.name for app in coraza_apps),
            settings.coraza_log_level,
        ),
        coraza_apps=coraza_apps,
        certs=certs,
    )


def _group_by_policy_id[Row: (RuleOverride, RuleExclusion, CustomRule)](
    rows: list[Row],
) -> dict[int, list[Row]]:
    grouped: dict[int, list[Row]] = {}
    for row in rows:
        grouped.setdefault(row.policy_id, []).append(row)
    return grouped


def _vhost_policy(vhost: VHost, policies_by_id: dict[int, Policy]) -> Policy | None:
    if vhost.policy_id is None:
        return None
    owner = f"Active vhost {vhost.domain!r}"
    policy = policies_by_id.get(vhost.policy_id)
    if policy is None:
        raise ValueError(f"{owner} references missing policy {vhost.policy_id}")
    if not policy.is_active:
        raise ValueError(f"{owner} references inactive policy {policy.id}")
    if policy.id is None:
        raise ValueError(f"{owner} references unpersisted policy")
    return policy


def _reject_path_scoped_policies(
    active_vhosts: list[VHost], policy_bindings: list[PolicyBinding]
) -> None:
    """Refuse bindings that would need a different policy on part of a vhost.

    HAProxy selects the Coraza application per vhost only. Rendering such a
    binding with the vhost's policy would silently drop what it asks for,
    and WAF events are attributed to the vhost's policy, so learning mode and
    exclusions-from-log would target the wrong policy.
    """
    policy_id_by_vhost_id = {vhost.id: vhost.policy_id for vhost in active_vhosts}
    domain_by_vhost_id = {vhost.id: vhost.domain for vhost in active_vhosts}
    for binding in policy_bindings:
        if binding.vhost_id not in policy_id_by_vhost_id:
            continue
        if binding.policy_id != policy_id_by_vhost_id[binding.vhost_id]:
            raise ValueError(
                f"Path binding {binding.path_prefix!r} on active vhost "
                f"{domain_by_vhost_id[binding.vhost_id]!r} selects policy "
                f"{binding.policy_id}, but WAF policies apply to a whole vhost; "
                "assign the policy to the vhost or delete the binding"
            )


def _to_coraza_app(
    policy: Policy,
    rule_overrides: list[RuleOverride],
    rule_exclusions: list[RuleExclusion],
    custom_rules: list[CustomRule],
) -> CorazaAppConfig:
    return CorazaAppConfig(
        name=coraza_app_name(policy),
        crs_setup_conf=render_crs_setup(_to_crs_policy_context(policy)),
        rule_overrides_conf=render_rule_overrides(
            _to_rule_override_contexts(rule_overrides),
            _to_rule_exclusion_contexts(rule_exclusions),
            _to_custom_rule_contexts(custom_rules),
        ),
    )


def _to_haproxy_context(vhost: VHost, policy: Policy | None) -> HaproxyRenderContext:
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
            auto_ban_enabled=policy.auto_ban_enabled,
            ban_stick_table_name=f"st_ban_{suffix}",
            ban_threshold=policy.ban_threshold,
            ban_duration_seconds=policy.ban_duration_seconds,
        )
        if policy is not None and policy.ddos_protection_enabled
        else None
    )
    # settings is imported only for geoip_fail_open; this is the only
    # settings read in this module.
    geoip = (
        HaproxyGeoip(
            mode=policy.geoip_mode.value,
            countries=tuple(policy.geoip_countries),
            map_path=HAPROXY_GEOIP_MAP_PATH,
            fail_open=settings.geoip_fail_open,
        )
        if policy is not None
        and policy.geoip_mode != PolicyGeoipMode.off
        and policy.geoip_countries
        else None
    )

    return HaproxyRenderContext(
        routes=(
            HaproxyRoute(
                vhost_acl_name=f"host_{suffix}",
                vhost_hosts=(vhost.domain,),
                ssl_provider=vhost.ssl_provider if vhost.ssl_enabled else "none",
                ddos=ddos,
                geoip=geoip,
                waf_app=coraza_app_name(policy),
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
    contexts: list[RuleExclusionRenderContext] = []
    for exclusion in exclusions:
        try:
            contexts.append(
                RuleExclusionRenderContext(
                    rule_id=exclusion.rule_id,
                    target_type=exclusion.target_type,
                    target_value=exclusion.target_value,
                    scope_path=exclusion.scope_path,
                    control_rule_id=control_rule_ids.get(id(exclusion)),
                )
            )
        except ValueError as error:
            # Rows saved before write-time validation existed can hold values
            # the generator cannot render. Failing here would block every
            # config apply until someone deletes the row; skipping it only
            # leaves that one rule inspecting the target (fail-safe).
            logger.warning(
                "Skipping rule exclusion %s of policy %s: %s",
                exclusion.id,
                exclusion.policy_id,
                error,
            )
    return tuple(contexts)


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
        # Each exclusion owns a block of SCOPE_MATCHERS_PER_EXCLUSION ids, so
        # control rules of different exclusions never collide. Ids start
        # above the custom rule range (9000000-9099999).
        assigned[id(exclusion)] = 9100000 + exclusion.id * SCOPE_MATCHERS_PER_EXCLUSION
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
