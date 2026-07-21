import shutil
import subprocess
from pathlib import Path

import pytest

from app.models.custom_rule import CustomRule, RuleOperator, RulePhase
from app.models.policy import Policy, PolicyEnforcementMode
from app.models.policy_binding import PolicyBinding
from app.models.rule_exclusion import RuleExclusion, TargetType
from app.models.rule_override import RuleAction, RuleOverride
from app.models.vhost import VHost
from app.models.vhost_backend import VHostBackend
from app.services.config_generator import generate
from app.services.config_renderer import (
    HaproxyBackend,
    HaproxyRenderContext,
    HaproxyRoute,
    HaproxyServer,
    render_haproxy_cfg_multi,
)


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "configs/haproxy/coraza.cfg").is_file():
            return candidate
    raise RuntimeError("Could not locate repository root")


def test_generate_empty_db() -> None:
    generated = generate(vhosts=[], policies=[], rule_overrides=[])

    assert "global" in generated.haproxy_cfg
    assert "defaults" in generated.haproxy_cfg
    assert "backend coraza-spoa" in generated.haproxy_cfg
    assert "backend be_" not in generated.haproxy_cfg
    assert "SecRuleEngine DetectionOnly" in generated.crs_setup_conf
    assert "Guard Proxy generated CRS policy tuning" in generated.rule_overrides_conf


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


def test_generate_one_vhost_with_two_active_backends() -> None:
    vhost = VHost(
        id=1,
        domain="app.local",
        backend_url="http://backend-a:8000",
        is_active=True,
        ssl_enabled=False,
        policy_id=None,
    )
    vhost.backends = [
        VHostBackend(
            id=10,
            url="http://backend-a:8000",
            is_active=True,
            health_check_enabled=True,
            health_check_path="/ready",
            health_check_interval_seconds=2,
            health_check_fall=2,
            health_check_rise=3,
        ),
        VHostBackend(
            id=11,
            url="http://backend-b:8000",
            is_active=True,
            health_check_enabled=True,
            health_check_path="/ready",
            health_check_interval_seconds=5,
            health_check_fall=3,
            health_check_rise=2,
        ),
    ]

    generated = generate(vhosts=[vhost], policies=[], rule_overrides=[])

    assert "backend be_vhost_1" in generated.haproxy_cfg
    assert "option httpchk GET /ready" in generated.haproxy_cfg
    assert (
        "server srv_vhost_1_1 backend-a:8000 check inter 2s fall 2 rise 3"
        in generated.haproxy_cfg
    )
    assert (
        "server srv_vhost_1_2 backend-b:8000 check inter 5s fall 3 rise 2"
        in generated.haproxy_cfg
    )


def test_generate_rejects_mixed_health_check_paths() -> None:
    vhost = VHost(
        id=1,
        domain="app.local",
        backend_url="http://backend-a:8000",
        is_active=True,
        ssl_enabled=False,
        policy_id=None,
    )
    vhost.backends = [
        VHostBackend(
            id=10,
            url="http://backend-a:8000",
            is_active=True,
            health_check_enabled=True,
            health_check_path="/ready",
            health_check_interval_seconds=2,
            health_check_fall=2,
            health_check_rise=3,
        ),
        VHostBackend(
            id=11,
            url="http://backend-b:8000",
            is_active=True,
            health_check_enabled=True,
            health_check_path="/healthz",
            health_check_interval_seconds=5,
            health_check_fall=3,
            health_check_rise=2,
        ),
    ]

    with pytest.raises(ValueError, match="multiple health check paths"):
        generate(vhosts=[vhost], policies=[], rule_overrides=[])


def test_generate_rejects_active_vhost_with_only_inactive_backends() -> None:
    vhost = VHost(
        id=1,
        domain="app.local",
        backend_url="http://legacy-backend:8000",
        is_active=True,
        ssl_enabled=False,
        policy_id=None,
    )
    vhost.backends = [
        VHostBackend(
            id=10,
            url="http://backend-a:8000",
            is_active=False,
            health_check_enabled=True,
            health_check_path="/",
            health_check_interval_seconds=5,
            health_check_fall=3,
            health_check_rise=2,
        )
    ]

    with pytest.raises(ValueError, match="no active backends"):
        generate(vhosts=[vhost], policies=[], rule_overrides=[])


def test_generated_haproxy_cfg_validates_with_haproxy(tmp_path: Path) -> None:
    haproxy = shutil.which("haproxy")
    if haproxy is None:
        pytest.skip("haproxy binary is not installed")
    vhost = VHost(
        id=1,
        domain="app.local",
        backend_url="http://backend:8000",
        is_active=True,
        ssl_enabled=False,
        policy_id=None,
    )
    generated = generate(vhosts=[vhost], policies=[], rule_overrides=[])
    config_path = tmp_path / "haproxy.cfg"
    repo_coraza_cfg = _repo_root() / "configs/haproxy/coraza.cfg"
    config_path.write_text(
        generated.haproxy_cfg.replace(
            "/usr/local/etc/haproxy/coraza.cfg",
            str(repo_coraza_cfg),
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [haproxy, "-c", "-f", str(config_path)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_generate_rejects_backend_url_with_scheme_but_no_host() -> None:
    vhost = VHost(
        id=1,
        domain="broken.example.com",
        backend_url="http://",
        is_active=True,
        ssl_enabled=False,
        policy_id=None,
    )

    with pytest.raises(ValueError, match="missing host"):
        generate(vhosts=[vhost], policies=[], rule_overrides=[])


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

    assert (
        "acl host_vhost_5 hdr(host),field(1,:) -i api.example.com"
        in generated.haproxy_cfg
    )
    assert "use_backend be_vhost_5 if host_vhost_5" in generated.haproxy_cfg
    assert "SecRuleEngine On" in generated.crs_setup_conf
    assert "setvar:tx.blocking_paranoia_level=2" in generated.crs_setup_conf


def test_generate_one_vhost_with_ddos_protection_enabled() -> None:
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
        ddos_protection_enabled=True,
        rate_limit_requests=50,
        rate_limit_window_seconds=5,
        max_connections_per_ip=10,
    )

    generated = generate(vhosts=[vhost], policies=[policy], rule_overrides=[])

    assert "backend st_ddos_vhost_5" in generated.haproxy_cfg
    assert (
        "stick-table type ipv6 size 100k expire 5s store "
        "http_req_rate(5s),conn_cur" in generated.haproxy_cfg
    )
    assert (
        "http-request track-sc0 src table st_ddos_vhost_5 if host_vhost_5"
        in generated.haproxy_cfg
    )
    assert (
        "http-request deny deny_status 429 if host_vhost_5 "
        "{ sc_http_req_rate(0,st_ddos_vhost_5) gt 50 }" in generated.haproxy_cfg
    )
    assert (
        "http-request deny deny_status 429 if host_vhost_5 "
        "{ sc_conn_cur(0,st_ddos_vhost_5) gt 10 }" in generated.haproxy_cfg
    )


def test_generate_one_vhost_with_ddos_protection_disabled_emits_nothing() -> None:
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
        ddos_protection_enabled=False,
    )

    generated = generate(vhosts=[vhost], policies=[policy], rule_overrides=[])

    assert "stick-table" not in generated.haproxy_cfg
    assert "track-sc0" not in generated.haproxy_cfg
    assert "deny_status 429" not in generated.haproxy_cfg


def test_generated_haproxy_cfg_with_ddos_validates_with_haproxy(
    tmp_path: Path,
) -> None:
    haproxy = shutil.which("haproxy")
    if haproxy is None:
        pytest.skip("haproxy binary is not installed")
    vhost = VHost(
        id=1,
        domain="app.local",
        backend_url="http://backend:8000",
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
        ddos_protection_enabled=True,
        rate_limit_requests=100,
        rate_limit_window_seconds=10,
        max_connections_per_ip=20,
    )
    generated = generate(vhosts=[vhost], policies=[policy], rule_overrides=[])
    config_path = tmp_path / "haproxy.cfg"
    repo_coraza_cfg = _repo_root() / "configs/haproxy/coraza.cfg"
    config_path.write_text(
        generated.haproxy_cfg.replace(
            "/usr/local/etc/haproxy/coraza.cfg",
            str(repo_coraza_cfg),
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [haproxy, "-c", "-f", str(config_path)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


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


def test_generate_one_vhost_with_policy_exclusion_and_custom_rule() -> None:
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
    exclusion = RuleExclusion(
        id=42,
        policy_id=10,
        rule_id=942100,
        target_type=TargetType.ARGS,
        target_value="token",
        scope_path="/api/login",
    )
    custom_rule = CustomRule(
        id=100,
        policy_id=10,
        rule_id=9000001,
        phase=RulePhase.REQUEST_HEADERS,
        variables="REQUEST_HEADERS:User-Agent",
        operator=RuleOperator.RX,
        operator_argument="(?i)curl",
        actions="deny,status:403,log",
        is_active=True,
    )

    generated = generate(
        vhosts=[vhost],
        policies=[policy],
        rule_overrides=[],
        rule_exclusions=[exclusion],
        custom_rules=[custom_rule],
    )

    assert (
        'SecRule REQUEST_URI "@beginsWith /api/login" '
        '"id:9100042,phase:1,pass,nolog,'
        'ctl:ruleRemoveTargetById=942100;ARGS:token"'
    ) in generated.rule_overrides_conf
    assert (
        'SecRule REQUEST_HEADERS:User-Agent "@rx (?i)curl" '
        '"id:9000001,phase:1,deny,status:403,log"'
    ) in generated.rule_overrides_conf


def test_generate_uses_policy_from_path_binding() -> None:
    vhost = VHost(
        id=1,
        domain="api.example.com",
        backend_url="http://api-backend:9000",
        is_active=True,
        ssl_enabled=False,
        policy_id=None,
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
    binding = PolicyBinding(
        id=20,
        vhost_id=1,
        policy_id=10,
        path_prefix="/api",
        priority=10,
    )
    override = RuleOverride(
        id=100,
        policy_id=10,
        rule_id=942100,
        action=RuleAction.disable,
    )

    generated = generate(
        vhosts=[vhost],
        policies=[policy],
        rule_overrides=[override],
        policy_bindings=[binding],
    )

    assert "SecRuleEngine On" in generated.crs_setup_conf
    assert "SecRuleRemoveById 942100" in generated.rule_overrides_conf


def test_generate_rejects_multiple_effective_path_policies() -> None:
    vhost = VHost(
        id=1,
        domain="api.example.com",
        backend_url="http://api-backend:9000",
        is_active=True,
        ssl_enabled=False,
        policy_id=10,
    )
    first_policy = Policy(
        id=10,
        name="Strict",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=4,
        enforcement_mode=PolicyEnforcementMode.block,
        is_active=True,
    )
    second_policy = Policy(
        id=11,
        name="Monitor",
        paranoia_level=1,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=4,
        enforcement_mode=PolicyEnforcementMode.detect_only,
        is_active=True,
    )
    binding = PolicyBinding(
        id=20,
        vhost_id=1,
        policy_id=11,
        path_prefix="/monitor",
        priority=10,
    )

    with pytest.raises(ValueError, match="one active CRS policy"):
        generate(
            vhosts=[vhost],
            policies=[first_policy, second_policy],
            rule_overrides=[],
            policy_bindings=[binding],
        )


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


def _make_single_route_context(
    acl_name: str,
    backend_name: str,
) -> HaproxyRenderContext:
    return HaproxyRenderContext(
        routes=(
            HaproxyRoute(
                vhost_acl_name=acl_name,
                vhost_hosts=("example.com",),
                ssl_provider="none",
                backend=HaproxyBackend(
                    name=backend_name,
                    servers=(
                        HaproxyServer(
                            server_name=f"srv_{acl_name}",
                            address="backend:8000",
                        ),
                    ),
                ),
            ),
        )
    )


def test_render_haproxy_cfg_multi_raises_on_duplicate_acl_name_across_contexts() -> None:  # noqa: E501
    ctx_a = _make_single_route_context("host_a", "be_a")
    ctx_b = _make_single_route_context("host_a", "be_b")  # duplicate ACL name

    with pytest.raises(ValueError, match="duplicate HAProxy identifier"):
        render_haproxy_cfg_multi([ctx_a, ctx_b])


def test_render_haproxy_cfg_multi_raises_on_duplicate_backend_name_across_contexts() -> None:  # noqa: E501
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
