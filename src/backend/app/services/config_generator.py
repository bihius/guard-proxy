"""Pure configuration generator from pre-fetched ORM objects."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.models.policy import Policy, PolicyEnforcementMode
from app.models.rule_override import RuleOverride
from app.models.vhost import VHost
from app.services.config_renderer import (
    CrsPolicyRenderContext,
    HaproxyBackend,
    HaproxyRenderContext,
    HaproxyRoute,
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
) -> GeneratedConfig:
    """Generate all runtime config files from already loaded objects."""
    active_vhosts = sorted(
        (vhost for vhost in vhosts if vhost.is_active),
        key=lambda vhost: vhost.domain,
    )
    vhost_contexts = [_to_haproxy_context(vhost) for vhost in active_vhosts]

    active_policy, active_overrides = _pick_active_policy(
        active_vhosts, policies, rule_overrides
    )
    haproxy_cfg = render_haproxy_cfg_multi(vhost_contexts)
    crs_setup_conf = render_crs_setup(active_policy)
    rule_overrides_conf = render_rule_overrides(active_overrides)

    certs = {}
    for vhost in active_vhosts:
        if vhost.ssl_provider != "none" and vhost.ssl_cert and vhost.ssl_key:
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
) -> tuple[CrsPolicyRenderContext, tuple[RuleOverrideRenderContext, ...]]:
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
        return (
            _to_crs_policy_context(policy),
            _to_rule_override_contexts(overrides_by_policy_id.get(policy.id, [])),
        )

    return (
        CrsPolicyRenderContext(
            paranoia_level=1,
            inbound_anomaly_threshold=5,
            outbound_anomaly_threshold=4,
            enforcement_mode=PolicyEnforcementMode.detect_only,
        ),
        (),
    )


def _to_haproxy_context(vhost: VHost) -> HaproxyRenderContext:
    if vhost.id is None:
        raise ValueError(f"Active vhost {vhost.domain!r} has no persisted id")
    # Use the database id as the naming suffix so that domain names that only
    # differ by '.' vs '-' (e.g. "app.local" and "app-local") never produce
    # colliding ACL or backend identifiers.  This matches the strategy used
    # by RuntimeStatusService._to_haproxy_route.
    suffix = f"vhost_{vhost.id}"
    backend_address = _extract_backend_address(vhost.backend_url)
    return HaproxyRenderContext(
        routes=(
            HaproxyRoute(
        vhost_acl_name=f"host_{suffix}",
                vhost_hosts=(vhost.domain,),
                ssl_provider=vhost.ssl_provider,
                backend=HaproxyBackend(
                    name=f"be_{suffix}",
                    server_name=f"srv_{suffix}",
                    address=backend_address,
                ),
            ),
        )
    )


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


def _extract_backend_address(backend_url: str) -> str:
    parsed = urlparse(backend_url)
    if parsed.scheme:
        address = parsed.netloc
    else:
        address = parsed.path

    if not address:
        raise ValueError(f"Invalid backend URL {backend_url!r}: missing host")
    if "@" in address:
        raise ValueError(
            f"Invalid backend URL {backend_url!r}: userinfo is not supported"
        )
    return address
