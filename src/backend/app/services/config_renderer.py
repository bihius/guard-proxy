"""Pure Jinja2 render helpers for HAProxy and CRS configuration."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from jinja2 import Environment, PackageLoader, StrictUndefined

from app.models.policy import PolicyEnforcementMode
from app.models.rule_override import RuleAction

# HAProxy identifiers (ACL names, backend names, server names): letters, digits,
# hyphens, and underscores only.  No whitespace, newlines, or shell-special chars.
_HAPROXY_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# HAProxy host values used in ACL conditions: bare hostname characters only.
# The HAProxy template strips the request port before matching.
_HAPROXY_HOST_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# HAProxy backend address (host:port): same allowlist as host values.
_HAPROXY_ADDRESS_RE = re.compile(r"^[A-Za-z0-9._:-]+$")


def _validate_haproxy_identifier(value: str, field: str) -> None:
    if not value:
        raise ValueError(f"{field} must not be empty")
    if not _HAPROXY_IDENTIFIER_RE.match(value):
        raise ValueError(
            f"{field} {value!r} contains characters unsafe for HAProxy config; "
            "only letters, digits, hyphens, and underscores are allowed"
        )


def _validate_haproxy_host(value: str, field: str) -> None:
    if not value:
        raise ValueError(f"{field} must not be empty")
    if not _HAPROXY_HOST_RE.match(value):
        raise ValueError(
            f"{field} {value!r} contains characters unsafe for HAProxy config; "
            "only hostname chars (letters, digits, dots, hyphens, underscores) "
            "are allowed"
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
        if not self.address:
            raise ValueError("HaproxyBackend.address must not be empty")
        if not _HAPROXY_ADDRESS_RE.match(self.address):
            raise ValueError(
                f"HaproxyBackend.address {self.address!r} contains characters that are "
                "unsafe for HAProxy config; only host:port characters are allowed"
            )


@dataclass(frozen=True)
class HaproxyRoute:
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
        if not self.vhost_hosts:
            raise ValueError("HaproxyRenderContext.vhost_hosts must not be empty")
        for host in self.vhost_hosts:
            _validate_haproxy_host(host, "HaproxyRenderContext.vhost_hosts")


@dataclass(frozen=True)
class HaproxyRenderContext:
    """Prepared HAProxy render input for all active virtual hosts."""

    routes: tuple[HaproxyRoute, ...]

    def __post_init__(self) -> None:
        if not self.routes:
            raise ValueError("HaproxyRenderContext.routes must not be empty")
        _ensure_unique(
            (route.vhost_acl_name for route in self.routes),
            "HaproxyRenderContext.routes.vhost_acl_name",
        )
        _ensure_unique(
            (route.backend.name for route in self.routes),
            "HaproxyRenderContext.routes.backend.name",
        )
        _ensure_unique(
            (route.backend.server_name for route in self.routes),
            "HaproxyRenderContext.routes.backend.server_name",
        )


@dataclass(frozen=True)
class CrsPolicyRenderContext:
    """Policy fields needed to render CRS setup without an ORM object."""

    paranoia_level: int
    inbound_anomaly_threshold: int
    outbound_anomaly_threshold: int
    enforcement_mode: PolicyEnforcementMode


@dataclass(frozen=True)
class RuleOverrideRenderContext:
    """Rule override fields needed to render CRS removals."""

    rule_id: int
    action: RuleAction


_ENVIRONMENT = Environment(
    loader=PackageLoader("app", "templates"),
    autoescape=False,
    keep_trailing_newline=True,
    undefined=StrictUndefined,
)


def render_haproxy_cfg(context: HaproxyRenderContext) -> str:
    """Render haproxy.cfg for a single vhost context."""
    return _render_haproxy_routes(context.routes)


def render_haproxy_cfg_multi(vhost_contexts: list[HaproxyRenderContext]) -> str:
    """Render haproxy.cfg from one or many prepared vhost contexts.

    Raises ValueError if any ACL name, backend name, or server name is
    duplicated across the merged set of contexts.  Each HaproxyRenderContext
    only validates uniqueness within itself; this function performs the
    cross-context check.
    """
    routes = tuple(route for context in vhost_contexts for route in context.routes)
    _ensure_unique(
        (route.vhost_acl_name for route in routes),
        "render_haproxy_cfg_multi routes.vhost_acl_name",
    )
    _ensure_unique(
        (route.backend.name for route in routes),
        "render_haproxy_cfg_multi routes.backend.name",
    )
    _ensure_unique(
        (route.backend.server_name for route in routes),
        "render_haproxy_cfg_multi routes.backend.server_name",
    )
    return _render_haproxy_routes(routes)


def _render_haproxy_routes(routes: tuple[HaproxyRoute, ...]) -> str:
    template = _ENVIRONMENT.get_template("haproxy.cfg.j2")
    return template.render(
        routes=routes,
        default_backend=routes[0].backend if routes else None,
    )


def render_crs_setup(policy: CrsPolicyRenderContext) -> str:
    """Render CRS setup configuration for a policy."""
    template = _ENVIRONMENT.get_template("crs-setup.conf.j2")
    sec_rule_engine = (
        "DetectionOnly"
        if policy.enforcement_mode == PolicyEnforcementMode.detect_only
        else "On"
    )
    return template.render(policy=policy, sec_rule_engine=sec_rule_engine)


def render_rule_overrides(overrides: tuple[RuleOverrideRenderContext, ...]) -> str:
    """Render CRS rule removals for disabled policy overrides."""
    template = _ENVIRONMENT.get_template("rule-overrides.conf.j2")
    disabled_rule_overrides = _sorted_disabled_overrides(overrides)
    return template.render(disabled_rule_overrides=disabled_rule_overrides)


def _sorted_disabled_overrides(
    overrides: tuple[RuleOverrideRenderContext, ...],
) -> list[RuleOverrideRenderContext]:
    return sorted(
        (override for override in overrides if override.action == RuleAction.disable),
        key=lambda override: override.rule_id,
    )


def _ensure_unique(values: Iterable[str], field: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"{field} contains duplicate HAProxy identifier {value!r}")
        seen.add(value)
