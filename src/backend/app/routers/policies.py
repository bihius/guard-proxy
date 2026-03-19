"""Router Policies API — CRUD polityk WAF."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.policy import Policy
from app.models.user import User
from app.schemas.policy import PolicyCreate, PolicyDetail, PolicyResponse, PolicyUpdate

router = APIRouter(prefix="/policies", tags=["policies"])


def _get_policy_or_404(db: Session, policy_id: int) -> Policy:
    """Zwraca politykę po ID albo 404 gdy nie istnieje."""
    policy = db.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )
    return policy


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(
    body: PolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Policy:
    """Tworzy nową politykę WAF (tylko admin)."""
    policy = Policy(
        name=body.name,
        description=body.description,
        paranoia_level=body.paranoia_level,
        anomaly_threshold=body.anomaly_threshold,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(policy)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Policy name already exists",
        )
    db.refresh(policy)
    return policy


@router.get("", response_model=list[PolicyResponse])
def list_policies(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Policy]:
    """Zwraca listę polityk WAF (admin i viewer)."""
    return db.query(Policy).order_by(Policy.id.asc()).all()


@router.get("/{policy_id}", response_model=PolicyDetail)
def get_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Policy:
    """Zwraca szczegóły polityki razem z rule_overrides (admin i viewer)."""
    policy = (
        db.query(Policy)
        .options(selectinload(Policy.rule_overrides))
        .filter(Policy.id == policy_id)
        .first()
    )
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )
    return policy


@router.patch("/{policy_id}", response_model=PolicyResponse)
def update_policy(
    policy_id: int,
    body: PolicyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Policy:
    """Aktualizuje wskazane pola polityki (tylko admin)."""
    policy = _get_policy_or_404(db, policy_id)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Policy name already exists",
        )
    db.refresh(policy)
    return policy


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Usuwa politykę po ID (tylko admin)."""
    policy = _get_policy_or_404(db, policy_id)
    db.delete(policy)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
