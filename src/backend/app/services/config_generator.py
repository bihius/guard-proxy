"""Pure configuration generator from pre-fetched ORM objects."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.models.policy import Policy, PolicyEnforcementMode
from app.models.rule_override import RuleOverride
from app.models.vhost import VHost
from app.services.config_renderer import (
    HaproxyBackend,
    HaproxyRenderContext,
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

    active_policy = _pick_active_policy(active_vhosts, policies, rule_overrides)
    haproxy_cfg = render_haproxy_cfg_multi(vhost_contexts)
    crs_setup_conf = render_crs_setup(active_policy)
    rule_overrides_conf = render_rule_overrides(active_policy)

    return GeneratedConfig(
        haproxy_cfg=haproxy_cfg,
        crs_setup_conf=crs_setup_conf,
        rule_overrides_conf=rule_overrides_conf,
    )


def _pick_active_policy(
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


def _to_haproxy_context(vhost: VHost) -> HaproxyRenderContext:
    domain_slug = _slug(vhost.domain)
    backend_address = _extract_backend_address(vhost.backend_url)
    return HaproxyRenderContext(
        vhost_acl_name=f"host_{domain_slug}",
        vhost_hosts=(vhost.domain,),
        backend=HaproxyBackend(
            name=f"be_{domain_slug}",
            server_name=f"srv_{domain_slug}",
            address=backend_address,
        ),
    )


def _slug(value: str) -> str:
    return value.replace(".", "_").replace("-", "_")


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
