"""Pure Jinja2 render helpers for HAProxy and CRS configuration."""

from __future__ import annotations

from dataclasses import dataclass

from jinja2 import Environment, PackageLoader, StrictUndefined

from app.models.policy import Policy, PolicyEnforcementMode
from app.models.rule_override import RuleAction, RuleOverride


@dataclass(frozen=True)
class HaproxyBackend:
    """Backend server data used by the HAProxy template."""

    name: str
    server_name: str
    address: str


@dataclass(frozen=True)
class HaproxyRenderContext:
    """Prepared HAProxy render input with no database behavior."""

    vhost_acl_name: str
    vhost_hosts: tuple[str, ...]
    backend: HaproxyBackend


_ENVIRONMENT = Environment(
    loader=PackageLoader("app", "templates"),
    autoescape=False,
    keep_trailing_newline=True,
    undefined=StrictUndefined,
)


def render_haproxy_cfg(context: HaproxyRenderContext) -> str:
    """Render haproxy.cfg from already prepared values."""
    template = _ENVIRONMENT.get_template("haproxy.cfg.j2")
    return template.render(
        vhost_acl_name=context.vhost_acl_name,
        vhost_hosts=context.vhost_hosts,
        backend=context.backend,
    )


def render_crs_setup(policy: Policy) -> str:
    """Render CRS setup configuration for a policy."""
    template = _ENVIRONMENT.get_template("crs-setup.conf.j2")
    sec_rule_engine = (
        "DetectionOnly"
        if policy.enforcement_mode == PolicyEnforcementMode.detect_only
        else "On"
    )
    return template.render(policy=policy, sec_rule_engine=sec_rule_engine)


def render_rule_overrides(policy: Policy) -> str:
    """Render CRS rule removals for disabled policy overrides."""
    template = _ENVIRONMENT.get_template("rule-overrides.conf.j2")
    disabled_rule_overrides = _sorted_disabled_overrides(policy.rule_overrides)
    return template.render(disabled_rule_overrides=disabled_rule_overrides)


def _sorted_disabled_overrides(overrides: list[RuleOverride]) -> list[RuleOverride]:
    return sorted(
        (override for override in overrides if override.action == RuleAction.disable),
        key=lambda override: override.rule_id,
    )
