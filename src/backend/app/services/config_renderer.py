"""Pure Jinja2 render helpers for HAProxy and CRS configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass

from jinja2 import Environment, PackageLoader, StrictUndefined

from app.models.policy import Policy, PolicyEnforcementMode
from app.models.rule_override import RuleAction, RuleOverride

# HAProxy identifiers (ACL names, backend names, server names): letters, digits,
# hyphens, and underscores only.  No whitespace, newlines, or shell-special chars.
_HAPROXY_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# HAProxy host values used in ACL conditions: hostname characters plus colon
# (for optional port) and dots.  No whitespace or newlines.
_HAPROXY_HOST_RE = re.compile(r"^[A-Za-z0-9._:-]+$")

# HAProxy backend address (host:port): same allowlist as host values.
_HAPROXY_ADDRESS_RE = re.compile(r"^[A-Za-z0-9._:-]+$")


def _validate_haproxy_identifier(value: str, field: str) -> None:
    if not _HAPROXY_IDENTIFIER_RE.match(value):
        raise ValueError(
            f"{field} {value!r} contains characters unsafe for HAProxy config; "
            "only letters, digits, hyphens, and underscores are allowed"
        )


def _validate_haproxy_host(value: str, field: str) -> None:
    if not _HAPROXY_HOST_RE.match(value):
        raise ValueError(
            f"{field} {value!r} contains characters unsafe for HAProxy config; "
            "only hostname chars (letters, digits, dots, hyphens, colons) are allowed"
        )


@dataclass(frozen=True)
class HaproxyBackend:
    """Backend server data used by the HAProxy template.

    All fields are validated on construction to reject characters that could
    allow HAProxy config injection (e.g. newlines, spaces, shell-special chars).
    """

    name: str
    server_name: str
    address: str

    def __post_init__(self) -> None:
        _validate_haproxy_identifier(self.name, "HaproxyBackend.name")
        _validate_haproxy_identifier(self.server_name, "HaproxyBackend.server_name")
        if not _HAPROXY_ADDRESS_RE.match(self.address):
            raise ValueError(
                f"HaproxyBackend.address {self.address!r} contains characters that are "
                "unsafe for HAProxy config; only host:port characters are allowed"
            )


@dataclass(frozen=True)
class HaproxyRenderContext:
    """Prepared HAProxy render input with no database behavior.

    All fields are validated on construction to reject characters that could
    allow HAProxy config injection (e.g. newlines, spaces, shell-special chars).
    The ``backend`` is validated independently inside :class:`HaproxyBackend`.
    """

    vhost_acl_name: str
    vhost_hosts: tuple[str, ...]
    backend: HaproxyBackend

    def __post_init__(self) -> None:
        _validate_haproxy_identifier(
            self.vhost_acl_name, "HaproxyRenderContext.vhost_acl_name"
        )
        for host in self.vhost_hosts:
            _validate_haproxy_host(host, "vhost_hosts entry")


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
