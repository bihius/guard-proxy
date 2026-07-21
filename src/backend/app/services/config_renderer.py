"""Pure Jinja2 render helpers for HAProxy and CRS configuration."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from jinja2 import Environment, PackageLoader, StrictUndefined

from app.models.custom_rule import RuleOperator, RulePhase
from app.models.policy import PolicyEnforcementMode
from app.models.rule_exclusion import TargetType
from app.models.rule_override import RuleAction

# HAProxy identifiers (ACL names, backend names, server names): letters, digits,
# hyphens, and underscores only.  No whitespace, newlines, or shell-special chars.
_HAPROXY_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# HAProxy host values used in ACL conditions: bare hostname characters only.
# The HAProxy template strips the request port before matching.
_HAPROXY_HOST_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# HAProxy backend address (host:port): same allowlist as host values.
_HAPROXY_ADDRESS_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
_HAPROXY_HEALTH_PATH_RE = re.compile(r"^[A-Za-z0-9_./:-]+$")
_MODSEC_LINE_BREAK_RE = re.compile(r"[\r\n]")
_MODSEC_TARGET_VALUE_RE = re.compile(r"^[A-Za-z0-9_.:/@-]+$")
_MODSEC_VARIABLES_RE = re.compile(r"^[A-Za-z0-9_.:|@-]+$")

_PHASE_BY_RULE_PHASE = {
    RulePhase.REQUEST_HEADERS: 1,
    RulePhase.REQUEST_BODY: 2,
    RulePhase.RESPONSE_HEADERS: 3,
    RulePhase.RESPONSE_BODY: 4,
    RulePhase.LOGGING: 5,
}

_OPERATOR_BY_RULE_OPERATOR = {
    RuleOperator.RX: "rx",
    RuleOperator.STREQ: "streq",
    RuleOperator.CONTAINS: "contains",
    RuleOperator.BEGINS_WITH: "beginsWith",
    RuleOperator.ENDS_WITH: "endsWith",
    RuleOperator.EQ: "eq",
    RuleOperator.GE: "ge",
    RuleOperator.GT: "gt",
    RuleOperator.LE: "le",
    RuleOperator.LT: "lt",
    RuleOperator.PM: "pm",
    RuleOperator.WITHIN: "within",
    RuleOperator.IP_MATCH: "ipMatch",
}

_TARGET_BY_TARGET_TYPE = {
    TargetType.REQUEST_URI: "REQUEST_URI",
    TargetType.ARGS: "ARGS",
    TargetType.ARGS_NAMES: "ARGS_NAMES",
    TargetType.REQUEST_HEADERS: "REQUEST_HEADERS",
}


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
class HaproxyServer:
    """One HAProxy server line inside a backend section.

    All fields are validated on construction to reject characters that could
    allow HAProxy config injection (e.g. newlines, spaces, shell-special chars).
    """

    server_name: str
    address: str
    health_check_enabled: bool = True
    health_check_interval_seconds: int = 5
    health_check_fall: int = 3
    health_check_rise: int = 2

    def __post_init__(self) -> None:
        _validate_haproxy_identifier(self.server_name, "HaproxyServer.server_name")
        if not self.address:
            raise ValueError("HaproxyServer.address must not be empty")
        if not _HAPROXY_ADDRESS_RE.match(self.address):
            raise ValueError(
                f"HaproxyServer.address {self.address!r} contains characters that are "
                "unsafe for HAProxy config; only host:port characters are allowed"
            )
        if self.health_check_interval_seconds <= 0:
            raise ValueError(
                "HaproxyServer.health_check_interval_seconds must be positive"
            )
        if self.health_check_fall <= 0:
            raise ValueError("HaproxyServer.health_check_fall must be positive")
        if self.health_check_rise <= 0:
            raise ValueError("HaproxyServer.health_check_rise must be positive")


@dataclass(frozen=True)
class HaproxyBackend:
    """HAProxy backend section data used by the template."""

    name: str
    servers: tuple[HaproxyServer, ...]
    health_check_path: str = "/"

    def __post_init__(self) -> None:
        _validate_haproxy_identifier(self.name, "HaproxyBackend.name")
        if not self.servers:
            raise ValueError("HaproxyBackend.servers must not be empty")
        _ensure_unique(
            (server.server_name for server in self.servers),
            "HaproxyBackend.servers.server_name",
        )
        if not self.health_check_path.startswith("/"):
            raise ValueError("HaproxyBackend.health_check_path must start with /")
        if not _HAPROXY_HEALTH_PATH_RE.match(self.health_check_path):
            raise ValueError(
                "HaproxyBackend.health_check_path contains characters that are "
                "unsafe for HAProxy config"
            )


@dataclass(frozen=True)
class HaproxyDdos:
    """Per-vhost DDoS protection settings (rate limiting + connection throttling).

    All fields are validated on construction; ``stick_table_name`` is derived
    from the vhost's existing ACL suffix so it is guaranteed to be a safe and
    unique HAProxy identifier.
    """

    enabled: bool
    stick_table_name: str
    rate_limit_requests: int
    rate_limit_window_seconds: int
    max_connections_per_ip: int

    def __post_init__(self) -> None:
        _validate_haproxy_identifier(
            self.stick_table_name, "HaproxyDdos.stick_table_name"
        )
        if self.rate_limit_requests < 1:
            raise ValueError("HaproxyDdos.rate_limit_requests must be positive")
        if not 1 <= self.rate_limit_window_seconds <= 3600:
            raise ValueError(
                "HaproxyDdos.rate_limit_window_seconds must be between 1 and 3600"
            )
        if self.max_connections_per_ip < 1:
            raise ValueError("HaproxyDdos.max_connections_per_ip must be positive")


@dataclass(frozen=True)
class HaproxyRoute:
    """Prepared HAProxy render input with no database behavior.

    All fields are validated on construction to reject characters that could
    allow HAProxy config injection (e.g. newlines, spaces, shell-special chars).
    The ``backend`` is validated independently inside :class:`HaproxyBackend`.
    """

    vhost_acl_name: str
    vhost_hosts: tuple[str, ...]
    ssl_provider: str
    backend: HaproxyBackend
    ddos: HaproxyDdos | None = None

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
            (
                server.server_name
                for route in self.routes
                for server in route.backend.servers
            ),
            "HaproxyRenderContext.routes.backend.server_name",
        )
        _ensure_unique(
            (
                route.ddos.stick_table_name
                for route in self.routes
                if route.ddos is not None
            ),
            "HaproxyRenderContext.routes.ddos.stick_table_name",
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


@dataclass(frozen=True)
class RuleExclusionRenderContext:
    """Rule exclusion fields needed to render CRS target removals."""

    rule_id: int
    target_type: TargetType
    target_value: str
    scope_path: str | None = None
    control_rule_id: int | None = None

    def __post_init__(self) -> None:
        if self.rule_id <= 0:
            raise ValueError("RuleExclusionRenderContext.rule_id must be positive")
        _validate_modsec_target_value(
            self.target_value,
            "RuleExclusionRenderContext.target_value",
        )
        if self.scope_path is not None:
            _validate_modsec_quoted_value(
                self.scope_path,
                "RuleExclusionRenderContext.scope_path",
            )
            if not self.scope_path.startswith("/"):
                raise ValueError(
                    "RuleExclusionRenderContext.scope_path must start with /"
                )
            if self.control_rule_id is None:
                raise ValueError(
                    "RuleExclusionRenderContext.control_rule_id is required for "
                    "path-scoped exclusions"
                )
            if self.control_rule_id <= 0:
                raise ValueError(
                    "RuleExclusionRenderContext.control_rule_id must be positive"
                )

    @property
    def target(self) -> str:
        variable = _TARGET_BY_TARGET_TYPE[self.target_type]
        if self.target_type == TargetType.REQUEST_URI:
            return variable
        return f"{variable}:{self.target_value}"

    @property
    def quoted_scope_path(self) -> str:
        if self.scope_path is None:
            raise ValueError("scope_path is required")
        return _quote_modsec(self.scope_path)


@dataclass(frozen=True)
class CustomRuleRenderContext:
    """Custom rule fields needed to render a Coraza SecRule."""

    rule_id: int
    phase: RulePhase
    variables: str
    operator: RuleOperator
    operator_argument: str
    actions: str
    is_active: bool

    def __post_init__(self) -> None:
        if self.rule_id <= 0:
            raise ValueError("CustomRuleRenderContext.rule_id must be positive")
        _validate_modsec_variables(
            self.variables,
            "CustomRuleRenderContext.variables",
        )
        _validate_modsec_quoted_value(
            self.operator_argument,
            "CustomRuleRenderContext.operator_argument",
        )
        _validate_modsec_quoted_value(
            self.actions,
            "CustomRuleRenderContext.actions",
        )

    @property
    def phase_number(self) -> int:
        return _PHASE_BY_RULE_PHASE[self.phase]

    @property
    def operator_token(self) -> str:
        return _OPERATOR_BY_RULE_OPERATOR[self.operator]

    @property
    def quoted_operator_argument(self) -> str:
        return _quote_modsec(self.operator_argument)

    @property
    def quoted_actions(self) -> str:
        return _quote_modsec(self.actions)


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
        (
            server.server_name
            for route in routes
            for server in route.backend.servers
        ),
        "render_haproxy_cfg_multi routes.backend.server_name",
    )
    return _render_haproxy_routes(routes)


def _render_haproxy_routes(routes: tuple[HaproxyRoute, ...]) -> str:
    template = _ENVIRONMENT.get_template("haproxy.cfg.j2")
    return template.render(routes=routes)


def render_crs_setup(policy: CrsPolicyRenderContext) -> str:
    """Render CRS setup configuration for a policy."""
    template = _ENVIRONMENT.get_template("crs-setup.conf.j2")
    sec_rule_engine = (
        "DetectionOnly"
        if policy.enforcement_mode == PolicyEnforcementMode.detect_only
        else "On"
    )
    return template.render(policy=policy, sec_rule_engine=sec_rule_engine)


def render_rule_overrides(
    overrides: tuple[RuleOverrideRenderContext, ...],
    exclusions: tuple[RuleExclusionRenderContext, ...] = (),
    custom_rules: tuple[CustomRuleRenderContext, ...] = (),
) -> str:
    """Render generated CRS tuning for the selected policy."""
    template = _ENVIRONMENT.get_template("rule-overrides.conf.j2")
    disabled_rule_overrides = _sorted_disabled_overrides(overrides)
    global_exclusions, scoped_exclusions = _sorted_exclusions(exclusions)
    active_custom_rules = _sorted_active_custom_rules(custom_rules)
    return template.render(
        disabled_rule_overrides=disabled_rule_overrides,
        global_exclusions=global_exclusions,
        scoped_exclusions=scoped_exclusions,
        active_custom_rules=active_custom_rules,
    )


def _sorted_disabled_overrides(
    overrides: tuple[RuleOverrideRenderContext, ...],
) -> list[RuleOverrideRenderContext]:
    return sorted(
        (override for override in overrides if override.action == RuleAction.disable),
        key=lambda override: override.rule_id,
    )


def _sorted_exclusions(
    exclusions: tuple[RuleExclusionRenderContext, ...],
) -> tuple[list[RuleExclusionRenderContext], list[RuleExclusionRenderContext]]:
    sorted_exclusions = sorted(
        exclusions,
        key=lambda exclusion: (
            exclusion.scope_path or "",
            exclusion.rule_id,
            exclusion.target_type.value,
            exclusion.target_value,
        ),
    )
    global_exclusions = [
        exclusion for exclusion in sorted_exclusions if exclusion.scope_path is None
    ]
    scoped_exclusions = [
        exclusion for exclusion in sorted_exclusions if exclusion.scope_path is not None
    ]
    return global_exclusions, scoped_exclusions


def _sorted_active_custom_rules(
    custom_rules: tuple[CustomRuleRenderContext, ...],
) -> list[CustomRuleRenderContext]:
    return sorted(
        (rule for rule in custom_rules if rule.is_active),
        key=lambda rule: rule.rule_id,
    )


def _ensure_unique(values: Iterable[str], field: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"{field} contains duplicate HAProxy identifier {value!r}")
        seen.add(value)


def _validate_modsec_target_value(value: str, field: str) -> None:
    if not value:
        raise ValueError(f"{field} must not be empty")
    if not _MODSEC_TARGET_VALUE_RE.match(value):
        raise ValueError(
            f"{field} {value!r} contains characters unsafe for generated "
            "Coraza target syntax"
        )


def _validate_modsec_variables(value: str, field: str) -> None:
    if not value:
        raise ValueError(f"{field} must not be empty")
    if not _MODSEC_VARIABLES_RE.match(value):
        raise ValueError(
            f"{field} {value!r} contains characters unsafe for generated "
            "Coraza variable syntax"
        )


def _validate_modsec_quoted_value(value: str, field: str) -> None:
    if not value:
        raise ValueError(f"{field} must not be empty")
    if _MODSEC_LINE_BREAK_RE.search(value):
        raise ValueError(f"{field} must not contain line breaks")


def _quote_modsec(value: str) -> str:
    _validate_modsec_quoted_value(value, "quoted Coraza value")
    return value.replace("\\", "\\\\").replace('"', '\\"')
