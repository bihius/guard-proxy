from app.models.policy import Policy
from app.models.rule_override import RuleAction, RuleOverride
from app.services.config_renderer import render_rule_overrides


def _policy_with_overrides(overrides: list[RuleOverride]) -> Policy:
    policy = Policy(
        name="Rule override renderer",
        paranoia_level=1,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
        is_active=True,
    )
    policy.rule_overrides = overrides
    return policy


def test_rule_overrides_template_renders_header_for_empty_policy() -> None:
    rendered = render_rule_overrides(_policy_with_overrides([]))

    assert "Guard Proxy CRS rule overrides" in rendered
    assert "SecRuleRemoveById" not in rendered


def test_rule_overrides_template_renders_disabled_rules_sorted() -> None:
    rendered = render_rule_overrides(
        _policy_with_overrides(
            [
                RuleOverride(policy_id=1, rule_id=942100, action=RuleAction.disable),
                RuleOverride(policy_id=1, rule_id=941100, action=RuleAction.disable),
            ]
        )
    )

    assert rendered.index("SecRuleRemoveById 941100") < rendered.index(
        "SecRuleRemoveById 942100"
    )


def test_rule_overrides_template_skips_enabled_rules() -> None:
    rendered = render_rule_overrides(
        _policy_with_overrides(
            [
                RuleOverride(policy_id=1, rule_id=941100, action=RuleAction.enable),
                RuleOverride(policy_id=1, rule_id=942100, action=RuleAction.disable),
            ]
        )
    )

    assert "SecRuleRemoveById 941100" not in rendered
    assert "SecRuleRemoveById 942100" in rendered
