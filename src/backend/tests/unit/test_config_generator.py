from app.models.policy import Policy, PolicyEnforcementMode
from app.models.rule_override import RuleAction, RuleOverride
from app.models.vhost import VHost
from app.services.config_generator import generate


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

    assert "acl host_app_local hdr(host) -i app.local" in generated.haproxy_cfg
    assert "use_backend be_app_local if host_app_local" in generated.haproxy_cfg
    assert "server srv_app_local backend:8000 check" in generated.haproxy_cfg
    assert "SecRuleEngine DetectionOnly" in generated.crs_setup_conf


def test_generate_one_vhost_with_policy() -> None:
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

    generated = generate(vhosts=[vhost], policies=[policy], rule_overrides=[])

    assert "acl host_api_example_com hdr(host) -i api.example.com" in generated.haproxy_cfg
    assert "use_backend be_api_example_com if host_api_example_com" in generated.haproxy_cfg
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
