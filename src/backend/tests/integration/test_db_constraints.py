"""Database-level constraint tests for policy and vhost invariants."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.custom_rule import CustomRule, RuleOperator, RulePhase
from app.models.policy import Policy
from app.models.policy_binding import PolicyBinding
from app.models.rule_exclusion import RuleExclusion, TargetType
from app.models.vhost import VHost


def test_policy_paranoia_level_above_max_raises_integrity_error(db: Session) -> None:
    """DB must reject paranoia levels outside the 1..4 range."""
    db.add(
        Policy(
            name="invalid-paranoia-level",
            paranoia_level=5,
            inbound_anomaly_threshold=5,
            outbound_anomaly_threshold=5,
            is_active=True,
        )
    )

    with pytest.raises(
        IntegrityError,
        match="ck_policies_paranoia_level|CHECK constraint failed",
    ):
        db.commit()
    db.rollback()


def test_policy_negative_inbound_anomaly_threshold_raises_integrity_error(
    db: Session,
) -> None:
    """DB must reject negative inbound anomaly thresholds."""
    db.add(
        Policy(
            name="invalid-anomaly-threshold",
            paranoia_level=2,
            inbound_anomaly_threshold=-1,
            outbound_anomaly_threshold=5,
            is_active=True,
        )
    )

    with pytest.raises(
        IntegrityError,
        match="ck_policies_inbound_anomaly_threshold|CHECK constraint failed",
    ):
        db.commit()
    db.rollback()


def test_policy_negative_outbound_anomaly_threshold_raises_integrity_error(
    db: Session,
) -> None:
    """DB must reject negative outbound anomaly thresholds."""
    db.add(
        Policy(
            name="invalid-outbound-anomaly-threshold",
            paranoia_level=2,
            inbound_anomaly_threshold=5,
            outbound_anomaly_threshold=-1,
            is_active=True,
        )
    )

    with pytest.raises(
        IntegrityError,
        match="ck_policies_outbound_anomaly_threshold|CHECK constraint failed",
    ):
        db.commit()
    db.rollback()


def test_deleting_policy_cascades_to_rule_exclusions(db: Session) -> None:
    """Deleting a policy must remove its rule exclusions (ondelete=CASCADE)."""
    policy = Policy(
        name="cascade-exclusions",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
        is_active=True,
    )
    db.add(policy)
    db.flush()

    exclusion = RuleExclusion(
        policy_id=policy.id,
        rule_id=942100,
        target_type=TargetType.ARGS,
        target_value="token",
    )
    db.add(exclusion)
    db.flush()
    exclusion_id = exclusion.id

    db.delete(policy)
    db.commit()

    assert db.get(RuleExclusion, exclusion_id) is None


def test_deleting_policy_cascades_to_custom_rules(db: Session) -> None:
    """Deleting a policy must remove its custom rules (ondelete=CASCADE)."""
    policy = Policy(
        name="cascade-custom-rules",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
        is_active=True,
    )
    db.add(policy)
    db.flush()

    custom_rule = CustomRule(
        policy_id=policy.id,
        rule_id=9000001,
        phase=RulePhase.REQUEST_HEADERS,
        variables="REQUEST_HEADERS:User-Agent",
        operator=RuleOperator.RX,
        operator_argument="(?i)curl",
        actions="deny,status:403",
    )
    db.add(custom_rule)
    db.flush()
    custom_rule_id = custom_rule.id

    db.delete(policy)
    db.commit()

    assert db.get(CustomRule, custom_rule_id) is None


def test_deleting_policy_cascades_to_policy_bindings(db: Session) -> None:
    """Deleting a policy must remove path-scoped policy bindings."""
    policy = Policy(
        name="cascade-policy-bindings",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
        is_active=True,
    )
    vhost = VHost(
        domain="cascade-policy-bindings.example.com",
        backend_url="http://backend:8000",
        is_active=True,
    )
    db.add_all([policy, vhost])
    db.flush()

    binding = PolicyBinding(
        vhost_id=vhost.id,
        policy_id=policy.id,
        path_prefix="/",
        priority=0,
    )
    db.add(binding)
    db.flush()
    binding_id = binding.id

    db.delete(policy)
    db.commit()

    assert db.get(PolicyBinding, binding_id) is None


def test_deleting_vhost_cascades_to_policy_bindings(db: Session) -> None:
    """Deleting a vhost must remove its path-scoped policy bindings."""
    policy = Policy(
        name="cascade-vhost-policy-bindings",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
        is_active=True,
    )
    vhost = VHost(
        domain="cascade-vhost-policy-bindings.example.com",
        backend_url="http://backend:8000",
        is_active=True,
    )
    db.add_all([policy, vhost])
    db.flush()

    binding = PolicyBinding(
        vhost_id=vhost.id,
        policy_id=policy.id,
        path_prefix="/",
        priority=0,
    )
    db.add(binding)
    db.flush()
    binding_id = binding.id

    db.delete(vhost)
    db.commit()

    assert db.get(PolicyBinding, binding_id) is None


def test_policy_binding_path_prefix_must_start_with_slash(
    db: Session,
) -> None:
    """DB must reject path prefixes that are not URL paths."""
    policy = Policy(
        name="invalid-binding-path",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
        is_active=True,
    )
    vhost = VHost(
        domain="invalid-binding-path.example.com",
        backend_url="http://backend:8000",
        is_active=True,
    )
    db.add_all([policy, vhost])
    db.flush()

    db.add(
        PolicyBinding(
            vhost_id=vhost.id,
            policy_id=policy.id,
            path_prefix="api",
            priority=0,
        )
    )

    with pytest.raises(
        IntegrityError,
        match=(
            "ck_policy_bindings_path_prefix_starts_with_slash"
            "|CHECK constraint failed"
        ),
    ):
        db.commit()
    db.rollback()


def test_policy_binding_priority_must_be_non_negative(db: Session) -> None:
    """DB must reject negative policy binding priorities."""
    policy = Policy(
        name="invalid-binding-priority",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
        is_active=True,
    )
    vhost = VHost(
        domain="invalid-binding-priority.example.com",
        backend_url="http://backend:8000",
        is_active=True,
    )
    db.add_all([policy, vhost])
    db.flush()

    db.add(
        PolicyBinding(
            vhost_id=vhost.id,
            policy_id=policy.id,
            path_prefix="/api",
            priority=-1,
        )
    )

    with pytest.raises(
        IntegrityError,
        match="ck_policy_bindings_priority_non_negative|CHECK constraint failed",
    ):
        db.commit()
    db.rollback()


def test_policy_binding_path_priority_must_be_unique_per_vhost(
    db: Session,
) -> None:
    """DB must reject duplicate path and priority bindings for a vhost."""
    policy = Policy(
        name="duplicate-binding-policy",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
        is_active=True,
    )
    vhost = VHost(
        domain="duplicate-binding.example.com",
        backend_url="http://backend:8000",
        is_active=True,
    )
    db.add_all([policy, vhost])
    db.flush()

    for comment in ["first", "second"]:
        db.add(
            PolicyBinding(
                vhost_id=vhost.id,
                policy_id=policy.id,
                path_prefix="/api",
                priority=1,
                comment=comment,
            )
        )

    with pytest.raises(
        IntegrityError,
        match="uq_policy_bindings_vhost_path_priority|UNIQUE constraint failed",
    ):
        db.commit()
    db.rollback()


def test_custom_rule_id_below_reserved_range_raises_integrity_error(
    db: Session,
) -> None:
    """DB must reject custom rule IDs outside the reserved custom range."""
    policy = Policy(
        name="invalid-custom-rule-id",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
        is_active=True,
    )
    db.add(policy)
    db.flush()

    db.add(
        CustomRule(
            policy_id=policy.id,
            rule_id=8999999,
            phase=RulePhase.REQUEST_HEADERS,
            variables="ARGS",
            operator=RuleOperator.RX,
            operator_argument=".*",
            actions="deny",
        )
    )

    with pytest.raises(
        IntegrityError,
        match="ck_custom_rules_rule_id_range|CHECK constraint failed",
    ):
        db.commit()
    db.rollback()


def test_custom_rule_rule_id_must_be_unique_per_policy(db: Session) -> None:
    """DB must reject duplicate custom rule IDs in the same policy."""
    policy = Policy(
        name="duplicate-custom-rule-id",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
        is_active=True,
    )
    db.add(policy)
    db.flush()

    for variables in ["ARGS:first", "ARGS:second"]:
        db.add(
            CustomRule(
                policy_id=policy.id,
                rule_id=9000001,
                phase=RulePhase.REQUEST_HEADERS,
                variables=variables,
                operator=RuleOperator.RX,
                operator_argument=".*",
                actions="deny",
            )
        )

    with pytest.raises(
        IntegrityError,
        match="uq_custom_rules_policy_id_rule_id|UNIQUE constraint failed",
    ):
        db.commit()
    db.rollback()


def test_custom_rule_rule_id_can_repeat_across_policies(db: Session) -> None:
    """Different policies may reuse the same custom rule ID."""
    policy_one = Policy(
        name="policy-one-custom-rule-id",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
        is_active=True,
    )
    policy_two = Policy(
        name="policy-two-custom-rule-id",
        paranoia_level=2,
        inbound_anomaly_threshold=5,
        outbound_anomaly_threshold=5,
        is_active=True,
    )
    db.add_all([policy_one, policy_two])
    db.flush()

    for policy in [policy_one, policy_two]:
        db.add(
            CustomRule(
                policy_id=policy.id,
                rule_id=9000001,
                phase=RulePhase.REQUEST_HEADERS,
                variables="ARGS",
                operator=RuleOperator.RX,
                operator_argument=".*",
                actions="deny",
            )
        )

    db.commit()


def test_vhost_uppercase_domain_raises_integrity_error(db: Session) -> None:
    """DB must enforce lowercase-only vhost domain values."""
    db.add(
        VHost(
            domain="UpperCase.Example.com",
            backend_url="http://localhost:8080",
            is_active=True,
            ssl_enabled=False,
        )
    )

    with pytest.raises(
        IntegrityError,
        match="ck_vhosts_domain_lowercase|CHECK constraint failed",
    ):
        db.commit()
    db.rollback()
