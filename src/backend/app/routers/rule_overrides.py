"""Rule Overrides API router for CRUD operations within a policy."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.policy import Policy
from app.models.rule_override import RuleOverride
from app.models.user import User
from app.schemas.rule_override import (
    RuleOverrideCreate,
    RuleOverrideResponse,
    RuleOverrideUpdate,
)

router = APIRouter(prefix="/policies/{policy_id}/rules", tags=["rule-overrides"])

NON_NULLABLE_PATCH_FIELDS = {"rule_id", "action"}

_UNIQUE_CONSTRAINT = "uq_rule_overrides_policy_id_rule_id"


def _is_rule_override_unique_violation(error: IntegrityError) -> bool:
    """Check whether an IntegrityError comes from a duplicate rule override."""
    error_text = str(error.orig).lower()
    # PostgreSQL includes the constraint name; SQLite reports column names instead
    return _UNIQUE_CONSTRAINT in error_text or (
        "unique" in error_text
        and "rule_id" in error_text
        and "policy_id" in error_text
    )


def _get_policy_or_404(db: Session, policy_id: int) -> Policy:
    """Return a policy by ID or raise 404 if it does not exist."""
    policy = db.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )
    return policy


def _get_rule_override_or_404(
    db: Session, policy_id: int, rule_override_id: int
) -> RuleOverride:
    """Return an override scoped to a policy or raise 404 if missing."""
    rule_override = (
        db.query(RuleOverride)
        .filter(
            RuleOverride.policy_id == policy_id,
            RuleOverride.id == rule_override_id,
        )
        .first()
    )
    if rule_override is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule override not found",
        )
    return rule_override


@router.post(
    "",
    response_model=RuleOverrideResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_rule_override(
    policy_id: int,
    body: RuleOverrideCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RuleOverride:
    """Create a CRS rule override for the given policy (admin only)."""
    _get_policy_or_404(db, policy_id)

    rule_override = RuleOverride(
        policy_id=policy_id,
        rule_id=body.rule_id,
        action=body.action,
        comment=body.comment,
    )
    db.add(rule_override)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _is_rule_override_unique_violation(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Rule override already exists",
            )
        raise

    db.refresh(rule_override)
    return rule_override


@router.get("", response_model=list[RuleOverrideResponse])
def list_rule_overrides(
    policy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[RuleOverride]:
    """Return all rule overrides for the given policy."""
    _get_policy_or_404(db, policy_id)
    return (
        db.query(RuleOverride)
        .filter(RuleOverride.policy_id == policy_id)
        .order_by(RuleOverride.id.asc())
        .all()
    )


@router.get("/{rule_override_id}", response_model=RuleOverrideResponse)
def get_rule_override(
    policy_id: int,
    rule_override_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RuleOverride:
    """Return a single rule override scoped to the given policy."""
    _get_policy_or_404(db, policy_id)
    return _get_rule_override_or_404(db, policy_id, rule_override_id)


@router.patch("/{rule_override_id}", response_model=RuleOverrideResponse)
def update_rule_override(
    policy_id: int,
    rule_override_id: int,
    body: RuleOverrideUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RuleOverride:
    """Update selected fields of a rule override (admin only)."""
    _get_policy_or_404(db, policy_id)
    rule_override = _get_rule_override_or_404(db, policy_id, rule_override_id)
    patch_data = body.model_dump(exclude_unset=True)

    for field in NON_NULLABLE_PATCH_FIELDS:
        if field in patch_data and patch_data[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Field '{field}' cannot be null",
            )

    for field, value in patch_data.items():
        setattr(rule_override, field, value)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _is_rule_override_unique_violation(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Rule override already exists",
            )
        raise

    db.refresh(rule_override)
    return rule_override


@router.delete("/{rule_override_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule_override(
    policy_id: int,
    rule_override_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Delete a rule override from a policy (admin only)."""
    _get_policy_or_404(db, policy_id)
    rule_override = _get_rule_override_or_404(db, policy_id, rule_override_id)
    db.delete(rule_override)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
