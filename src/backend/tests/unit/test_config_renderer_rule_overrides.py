import pytest

from app.models.custom_rule import RuleOperator, RulePhase
from app.models.rule_exclusion import TargetType
from app.models.rule_override import RuleAction
from app.services.config_renderer import (
    CustomRuleRenderContext,
    RuleExclusionRenderContext,
    RuleOverrideRenderContext,
    render_rule_overrides,
)


def _overrides(
    overrides: list[RuleOverrideRenderContext],
) -> tuple[RuleOverrideRenderContext, ...]:
    return tuple(overrides)


def test_rule_overrides_template_renders_header_for_empty_policy() -> None:
    rendered = render_rule_overrides(_overrides([]))

    assert rendered == (
        "# Guard Proxy generated CRS policy tuning.\n"
        "#\n"
        "# Rules are enabled by default through the CRS include. This file"
        " applies the\n"
        "# selected policy's disabled rules, target exclusions, scoped"
        " exclusions, and\n"
        "# administrator-authored custom rules.\n"
        "\n"
        "# Disabled CRS rules.\n"
        "\n"
        "\n"
        "# Global target exclusions.\n"
        "\n"
        "\n"
        "# Path-scoped target exclusions.\n"
        "\n"
        "\n"
        "# Custom rules.\n"
        "\n"
    )


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


def test_rule_overrides_template_renders_global_exclusions_sorted() -> None:
    rendered = render_rule_overrides(
        _overrides([]),
        exclusions=(
            RuleExclusionRenderContext(
                rule_id=942100,
                target_type=TargetType.REQUEST_HEADERS,
                target_value="X-Api-Token",
            ),
            RuleExclusionRenderContext(
                rule_id=941100,
                target_type=TargetType.ARGS,
                target_value="comment",
            ),
        ),
    )

    first = "SecRuleRemoveTargetById 941100 ARGS:comment"
    second = "SecRuleRemoveTargetById 942100 REQUEST_HEADERS:X-Api-Token"
    assert first in rendered
    assert second in rendered
    assert rendered.index(first) < rendered.index(second)


def test_rule_overrides_template_renders_path_scoped_exclusion() -> None:
    rendered = render_rule_overrides(
        _overrides([]),
        exclusions=(
            RuleExclusionRenderContext(
                rule_id=942100,
                target_type=TargetType.ARGS,
                target_value="token",
                scope_path="/api/login",
                control_rule_id=9100042,
            ),
        ),
    )

    assert (
        'SecRule REQUEST_URI "@beginsWith /api/login" '
        '"id:9100042,phase:1,pass,nolog,'
        'ctl:ruleRemoveTargetById=942100;ARGS:token"'
    ) in rendered


def test_rule_overrides_template_requires_control_id_for_scoped_exclusion() -> None:
    with pytest.raises(ValueError, match="control_rule_id is required"):
        RuleExclusionRenderContext(
            rule_id=942100,
            target_type=TargetType.ARGS,
            target_value="token",
            scope_path="/api/login",
        )


def test_rule_overrides_template_renders_active_custom_rules_sorted() -> None:
    rendered = render_rule_overrides(
        _overrides([]),
        custom_rules=(
            CustomRuleRenderContext(
                rule_id=9000002,
                phase=RulePhase.REQUEST_BODY,
                variables="ARGS:comment",
                operator=RuleOperator.CONTAINS,
                operator_argument="blocked",
                actions="deny,status:403,log",
                is_active=True,
            ),
            CustomRuleRenderContext(
                rule_id=9000001,
                phase=RulePhase.REQUEST_HEADERS,
                variables="REQUEST_HEADERS:User-Agent",
                operator=RuleOperator.RX,
                operator_argument="(?i)curl",
                actions="deny,status:403,log",
                is_active=True,
            ),
            CustomRuleRenderContext(
                rule_id=9000003,
                phase=RulePhase.REQUEST_HEADERS,
                variables="REQUEST_HEADERS:X-Test",
                operator=RuleOperator.STREQ,
                operator_argument="inactive",
                actions="deny,status:403,log",
                is_active=False,
            ),
        ),
    )

    first = (
        'SecRule REQUEST_HEADERS:User-Agent "@rx (?i)curl" '
        '"id:9000001,phase:1,deny,status:403,log"'
    )
    second = (
        'SecRule ARGS:comment "@contains blocked" '
        '"id:9000002,phase:2,deny,status:403,log"'
    )
    assert first in rendered
    assert second in rendered
    assert "9000003" not in rendered
    assert rendered.index(first) < rendered.index(second)


def test_custom_rule_context_rejects_line_break_in_operator_argument() -> None:
    with pytest.raises(ValueError, match="line breaks"):
        CustomRuleRenderContext(
            rule_id=9000001,
            phase=RulePhase.REQUEST_HEADERS,
            variables="REQUEST_HEADERS:User-Agent",
            operator=RuleOperator.RX,
            operator_argument="curl\nSecRule ARGS",
            actions="deny,status:403,log",
            is_active=True,
        )
