from pathlib import Path

import pytest

from app.models.policy import Policy, PolicyEnforcementMode
from app.services.config_renderer import render_crs_setup


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate

    raise FileNotFoundError(
        f"Could not locate repository root from {start}; expected .git directory"
    )


REPO_ROOT = _find_repo_root(Path(__file__).resolve().parent)


def _normalise_config(config: str) -> str:
    return "\n".join(line.rstrip() for line in config.splitlines() if line.strip())


def _policy(
    *,
    paranoia_level: int = 1,
    inbound_anomaly_threshold: int = 5,
    outbound_anomaly_threshold: int = 5,
    enforcement_mode: PolicyEnforcementMode = PolicyEnforcementMode.block,
) -> Policy:
    return Policy(
        name="Renderer policy",
        paranoia_level=paranoia_level,
        inbound_anomaly_threshold=inbound_anomaly_threshold,
        outbound_anomaly_threshold=outbound_anomaly_threshold,
        enforcement_mode=enforcement_mode,
        is_active=True,
    )


@pytest.mark.parametrize("paranoia_level", [1, 2, 3, 4])
def test_crs_setup_template_renders_paranoia_levels(paranoia_level: int) -> None:
    rendered = render_crs_setup(_policy(paranoia_level=paranoia_level))

    assert f"setvar:tx.blocking_paranoia_level={paranoia_level}" in rendered
    assert f"setvar:tx.detection_paranoia_level={paranoia_level}" in rendered


def test_crs_setup_template_renders_anomaly_thresholds() -> None:
    rendered = render_crs_setup(
        _policy(inbound_anomaly_threshold=7, outbound_anomaly_threshold=9)
    )

    assert "setvar:tx.inbound_anomaly_score_threshold=7" in rendered
    assert "setvar:tx.outbound_anomaly_score_threshold=9" in rendered


def test_crs_setup_template_renders_blocking_engine_mode() -> None:
    rendered = render_crs_setup(_policy(enforcement_mode=PolicyEnforcementMode.block))

    assert "SecRuleEngine On" in rendered


def test_crs_setup_template_renders_detection_only_engine_mode() -> None:
    rendered = render_crs_setup(
        _policy(enforcement_mode=PolicyEnforcementMode.detect_only)
    )

    assert "SecRuleEngine DetectionOnly" in rendered


def test_crs_setup_pl1_baseline_matches_reference_modulo_engine_line() -> None:
    rendered = render_crs_setup(_policy())
    reference = (REPO_ROOT / "configs/coraza/crs-setup.conf").read_text()

    rendered_without_engine = rendered.replace("SecRuleEngine On\n\n", "")
    assert _normalise_config(rendered_without_engine) == _normalise_config(reference)
