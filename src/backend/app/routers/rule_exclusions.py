"""Rule Exclusions API router for CRUD operations within a policy."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.rule_exclusion import RuleExclusion
from app.models.user import User
from app.schemas.rule_exclusion import (
    RuleExclusionCreate,
    RuleExclusionResponse,
    RuleExclusionUpdate,
)
from app.services.exclusion_service import (
    ExclusionDisallowedFieldError,
    ExclusionFieldCannotBeNullError,
    ExclusionNotFoundError,
    ExclusionPolicyNotFoundError,
    ExclusionService,
)

router = APIRouter(prefix="/policies/{policy_id}/exclusions", tags=["rule-exclusions"])


@router.post(
    "",
    response_model=RuleExclusionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_rule_exclusion(
    policy_id: int,
    body: RuleExclusionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RuleExclusion:
    """Create a CRS rule exclusion for the given policy (admin only)."""
    service = ExclusionService(db)

    try:
        return service.create_exclusion(
            policy_id,
            rule_id=body.rule_id,
            target_type=body.target_type,
            target_value=body.target_value,
            scope_path=body.scope_path,
            comment=body.comment,
        )
    except ExclusionPolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error


@router.get("", response_model=list[RuleExclusionResponse])
def list_rule_exclusions(
    policy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[RuleExclusion]:
    """Return all rule exclusions for the given policy."""
    service = ExclusionService(db)

    try:
        return service.list_exclusions(policy_id)
    except ExclusionPolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error


@router.get("/{rule_exclusion_id}", response_model=RuleExclusionResponse)
def get_rule_exclusion(
    policy_id: int,
    rule_exclusion_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RuleExclusion:
    """Return a single rule exclusion scoped to the given policy."""
    service = ExclusionService(db)

    try:
        return service.get_exclusion(policy_id, rule_exclusion_id)
    except ExclusionPolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error
    except ExclusionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule exclusion not found",
        ) from error


@router.patch("/{rule_exclusion_id}", response_model=RuleExclusionResponse)
def update_rule_exclusion(
    policy_id: int,
    rule_exclusion_id: int,
    body: RuleExclusionUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RuleExclusion:
    """Update selected fields of a rule exclusion (admin only)."""
    service = ExclusionService(db)

    try:
        return service.update_exclusion(
            policy_id,
            rule_exclusion_id,
            body.model_dump(exclude_unset=True),
        )
    except ExclusionPolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error
    except ExclusionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule exclusion not found",
        ) from error
    except ExclusionDisallowedFieldError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except ExclusionFieldCannotBeNullError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


@router.delete("/{rule_exclusion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule_exclusion(
    policy_id: int,
    rule_exclusion_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Delete a rule exclusion from a policy (admin only)."""
    service = ExclusionService(db)

    try:
        service.delete_exclusion(policy_id, rule_exclusion_id)
    except ExclusionPolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error
    except ExclusionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule exclusion not found",
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
