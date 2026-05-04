"""Policies API router — WAF policy CRUD."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.policy import Policy
from app.models.user import User
from app.schemas.policy import PolicyCreate, PolicyDetail, PolicyResponse, PolicyUpdate
from app.services.policy_service import (
    PolicyDatabaseConstraintError,
    PolicyDisallowedFieldError,
    PolicyFieldCannotBeNullError,
    PolicyNameAlreadyExistsError,
    PolicyNotFoundError,
    PolicyService,
)

router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(
    body: PolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Policy:
    """Creates a new WAF policy (admin only)."""
    service = PolicyService(db)

    try:
        return service.create_policy(
            name=body.name,
            description=body.description,
            paranoia_level=body.paranoia_level,
            inbound_anomaly_threshold=body.inbound_anomaly_threshold,
            outbound_anomaly_threshold=body.outbound_anomaly_threshold,
            enforcement_mode=body.enforcement_mode,
            created_by=current_user.id,
        )
    except PolicyNameAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Policy name already exists",
        ) from error
    except PolicyDatabaseConstraintError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database integrity constraint violated",
        ) from error


@router.get("", response_model=list[PolicyResponse])
def list_policies(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Policy]:
    """Returns list of WAF policies (admin and viewer)."""
    service = PolicyService(db)
    return service.list_policies()


@router.get("/{policy_id}", response_model=PolicyDetail)
def get_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Policy:
    """Returns policy details with rule_overrides (admin and viewer)."""
    service = PolicyService(db)
    try:
        return service.get_policy(policy_id)
    except PolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error


@router.patch("/{policy_id}", response_model=PolicyResponse)
def update_policy(
    policy_id: int,
    body: PolicyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Policy:
    """Updates selected policy fields (admin only)."""
    service = PolicyService(db)

    try:
        return service.update_policy(
            policy_id,
            body.model_dump(exclude_unset=True),
        )
    except PolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error
    except PolicyDisallowedFieldError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except PolicyFieldCannotBeNullError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except PolicyNameAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Policy name already exists",
        ) from error
    except PolicyDatabaseConstraintError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database integrity constraint violated",
        ) from error


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Deletes policy by ID (admin only)."""
    service = PolicyService(db)
    try:
        service.delete_policy(policy_id)
    except PolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
