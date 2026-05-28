import pytest

from app.models.policy import Policy, PolicyEnforcementMode
from app.models.rule_override import RuleAction, RuleOverride
from app.models.vhost import VHost
from app.services.config_generator import generate
from app.services.config_renderer import HaproxyBackend, HaproxyRenderContext, HaproxyRoute, render_haproxy_cfg_multi


def test_generate_empty_db() -> None:
    generated = generate(vhosts=[], policies=[], rule_overrides=[])

    assert "global" in generated.haproxy_cfg
    assert "defaults" in generated.haproxy_cfg
    assert "backend coraza-spoa" in generated.haproxy_cfg
    assert "backend be_" not in generated.haproxy_cfg
    assert "SecRuleEngine DetectionOnly" in generated.crs_setup_conf
    assert generated.rule_overrides_conf.strip() == "# Guard Proxy CRS rule overrides.\n#\n# Rules are enabled by default through the CRS include. Disabled overrides remove\n# selected CRS rule IDs for the rendered policy."


def test_generate_one_vhost_no_policy() -> None:
    vhost = VHost(
        id=1,
        domain="app.local",
        backend_url="http://backend:8000",
        is_active=True,
        ssl_enabled=False,
        policy_id=None,
    )

    generated = generate(vhosts=[vhost], policies=[], rule_overrides=[])

    # Identifiers are based on vhost.id, not domain slug, to avoid collisions
    # between domains that only differ in '.' vs '-'.
    assert "acl host_vhost_1 hdr(host),field(1,:) -i app.local" in generated.haproxy_cfg
    assert "use_backend be_vhost_1 if host_vhost_1" in generated.haproxy_cfg
    assert "server srv_vhost_1 backend:8000 check" in generated.haproxy_cfg
    assert "SecRuleEngine DetectionOnly" in generated.crs_setup_conf


def test_generate_one_vhost_with_policy() -> None:
    vhost = VHost(
        id=5,
        domain="api.example.com",
        backend_url="http://api-backend:9000",
        is_active=True,
        ssl_enabled=False,
        policy_id=10,
    )
    policy = Policy(
        id=10,
        name="Strict",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=4,
        enforcement_mode=PolicyEnforcementMode.block,
        is_active=True,
    )

    generated = generate(vhosts=[vhost], policies=[policy], rule_overrides=[])

    assert "acl host_vhost_5 hdr(host),field(1,:) -i api.example.com" in generated.haproxy_cfg
    assert "use_backend be_vhost_5 if host_vhost_5" in generated.haproxy_cfg
    assert "SecRuleEngine On" in generated.crs_setup_conf
    assert "setvar:tx.blocking_paranoia_level=2" in generated.crs_setup_conf


def test_generate_one_vhost_with_policy_and_overrides() -> None:
    vhost = VHost(
        id=1,
        domain="api.example.com",
        backend_url="http://api-backend:9000",
        is_active=True,
        ssl_enabled=False,
        policy_id=10,
    )
    policy = Policy(
        id=10,
        name="Strict",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=4,
        enforcement_mode=PolicyEnforcementMode.block,
        is_active=True,
    )
    override = RuleOverride(
        id=100,
        policy_id=10,
        rule_id=942100,
        action=RuleAction.disable,
    )

    generated = generate(vhosts=[vhost], policies=[policy], rule_overrides=[override])

    assert "SecRuleRemoveById 942100" in generated.rule_overrides_conf


# ---------------------------------------------------------------------------
# MED M9 — domain slug collision: app.local vs app-local must not collide
# ---------------------------------------------------------------------------


def test_generate_dot_dash_domain_siblings_do_not_collide() -> None:
    """Domains that only differ in '.' vs '-' must get distinct identifiers.

    Previously _slug() replaced both with '_', making 'app.local' and
    'app-local' both produce 'app_local' and collide.  With id-based naming
    they are distinct as long as they have different database ids.
    """
    vhost_dot = VHost(
        id=3,
        domain="app.local",
        backend_url="http://dot-backend:8000",
        is_active=True,
        ssl_enabled=False,
        policy_id=None,
    )
    vhost_dash = VHost(
        id=7,
        domain="app-local",
        backend_url="http://dash-backend:8000",
        is_active=True,
        ssl_enabled=False,
        policy_id=None,
    )

    generated = generate(vhosts=[vhost_dot, vhost_dash], policies=[], rule_overrides=[])

    assert generated.haproxy_cfg is not None
    assert "host_vhost_3" in generated.haproxy_cfg
    assert "host_vhost_7" in generated.haproxy_cfg
    assert "be_vhost_3" in generated.haproxy_cfg
    assert "be_vhost_7" in generated.haproxy_cfg


# ---------------------------------------------------------------------------
# MED M8 — cross-context uniqueness: render_haproxy_cfg_multi must validate
# ---------------------------------------------------------------------------


def _make_single_route_context(acl_name: str, backend_name: str) -> HaproxyRenderContext:
    return HaproxyRenderContext(
        routes=(
            HaproxyRoute(
                vhost_acl_name=acl_name,
                vhost_hosts=("example.com",),
                backend=HaproxyBackend(
                    name=backend_name,
                    server_name=f"srv_{acl_name}",
                    address="backend:8000",
                ),
            ),
        )
    )


def test_render_haproxy_cfg_multi_raises_on_duplicate_acl_name_across_contexts() -> None:
    ctx_a = _make_single_route_context("host_a", "be_a")
    ctx_b = _make_single_route_context("host_a", "be_b")  # duplicate ACL name

    with pytest.raises(ValueError, match="duplicate HAProxy identifier"):
        render_haproxy_cfg_multi([ctx_a, ctx_b])


def test_render_haproxy_cfg_multi_raises_on_duplicate_backend_name_across_contexts() -> None:
    ctx_a = _make_single_route_context("host_a", "be_shared")
    ctx_b = _make_single_route_context("host_b", "be_shared")  # duplicate backend name

    with pytest.raises(ValueError, match="duplicate HAProxy identifier"):
        render_haproxy_cfg_multi([ctx_a, ctx_b])


def test_render_haproxy_cfg_multi_succeeds_with_distinct_contexts() -> None:
    ctx_a = _make_single_route_context("host_a", "be_a")
    ctx_b = _make_single_route_context("host_b", "be_b")

    result = render_haproxy_cfg_multi([ctx_a, ctx_b])

    assert "host_a" in result
    assert "host_b" in result
