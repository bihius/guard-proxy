"""Database-level constraint tests for policy and vhost invariants."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.models.vhost import VHost


def test_policy_paranoia_level_above_max_raises_integrity_error(db: Session) -> None:
    """DB must reject paranoia levels outside the 1..4 range."""
    db.add(
        Policy(
            name="invalid-paranoia-level",
            paranoia_level=5,
            anomaly_threshold=5,
            is_active=True,
        )
    )

    with pytest.raises(
        IntegrityError,
        match="ck_policies_paranoia_level|CHECK constraint failed",
    ):
        db.commit()
    db.rollback()


def test_policy_negative_anomaly_threshold_raises_integrity_error(db: Session) -> None:
    """DB must reject negative anomaly thresholds."""
    db.add(
        Policy(
            name="invalid-anomaly-threshold",
            paranoia_level=2,
            anomaly_threshold=-1,
            is_active=True,
        )
    )

    with pytest.raises(
        IntegrityError,
        match="ck_policies_anomaly_threshold|CHECK constraint failed",
    ):
        db.commit()
    db.rollback()


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
