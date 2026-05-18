from app.models.rule_override import RuleAction
from app.services.config_renderer import (
    RuleOverrideRenderContext,
    render_rule_overrides,
)


def _overrides(
    overrides: list[RuleOverrideRenderContext],
) -> tuple[RuleOverrideRenderContext, ...]:
    return tuple(overrides)


def test_rule_overrides_template_renders_header_for_empty_policy() -> None:
    rendered = render_rule_overrides(_overrides([]))

    assert "Guard Proxy CRS rule overrides" in rendered
    assert "SecRuleRemoveById" not in rendered


def test_rule_overrides_template_renders_disabled_rules_sorted() -> None:
    rendered = render_rule_overrides(
        _overrides(
            [
                RuleOverrideRenderContext(
                    rule_id=942100,
                    action=RuleAction.disable,
                ),
                RuleOverrideRenderContext(
                    rule_id=941100,
                    action=RuleAction.disable,
                ),
            ]
        )
    )

    assert rendered.index("SecRuleRemoveById 941100") < rendered.index(
        "SecRuleRemoveById 942100"
    )


def test_rule_overrides_template_skips_enabled_rules() -> None:
    rendered = render_rule_overrides(
        _overrides(
            [
                RuleOverrideRenderContext(
                    rule_id=941100,
                    action=RuleAction.enable,
                ),
                RuleOverrideRenderContext(
                    rule_id=942100,
                    action=RuleAction.disable,
                ),
            ]
        )
    )

    assert "SecRuleRemoveById 941100" not in rendered
    assert "SecRuleRemoveById 942100" in rendered
