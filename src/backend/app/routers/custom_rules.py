"""Custom Rules API router for CRUD operations within a policy."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.custom_rule import CustomRule
from app.models.user import User
from app.schemas.custom_rule import (
    CustomRuleCreate,
    CustomRuleResponse,
    CustomRuleUpdate,
)
from app.services.custom_rule_service import (
    CustomRuleDisallowedFieldError,
    CustomRuleDuplicateRuleIdError,
    CustomRuleFieldCannotBeNullError,
    CustomRuleNotFoundError,
    CustomRulePolicyNotFoundError,
    CustomRuleService,
)

router = APIRouter(
    prefix="/policies/{policy_id}/custom-rules", tags=["custom-rules"]
)


@router.post(
    "",
    response_model=CustomRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_custom_rule(
    policy_id: int,
    body: CustomRuleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> CustomRule:
    """Create a custom rule for the given policy (admin only)."""
    service = CustomRuleService(db)

    try:
        return service.create_custom_rule(
            policy_id,
            rule_id=body.rule_id,
            phase=body.phase,
            variables=body.variables,
            operator=body.operator,
            operator_argument=body.operator_argument,
            actions=body.actions,
            comment=body.comment,
            is_active=body.is_active,
        )
    except CustomRulePolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error
    except CustomRuleDuplicateRuleIdError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A custom rule with this ID already exists in this policy.",
        ) from error


@router.get("", response_model=list[CustomRuleResponse])
def list_custom_rules(
    policy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[CustomRule]:
    """Return all custom rules for the given policy."""
    service = CustomRuleService(db)

    try:
        return service.list_custom_rules(policy_id)
    except CustomRulePolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error


@router.get("/{custom_rule_id}", response_model=CustomRuleResponse)
def get_custom_rule(
    policy_id: int,
    custom_rule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CustomRule:
    """Return a single custom rule scoped to the given policy."""
    service = CustomRuleService(db)

    try:
        return service.get_custom_rule(policy_id, custom_rule_id)
    except CustomRulePolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error
    except CustomRuleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom rule not found",
        ) from error


@router.patch("/{custom_rule_id}", response_model=CustomRuleResponse)
def update_custom_rule(
    policy_id: int,
    custom_rule_id: int,
    body: CustomRuleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> CustomRule:
    """Update selected fields of a custom rule (admin only)."""
    service = CustomRuleService(db)

    try:
        return service.update_custom_rule(
            policy_id,
            custom_rule_id,
            body.model_dump(exclude_unset=True),
        )
    except CustomRulePolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error
    except CustomRuleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom rule not found",
        ) from error
    except CustomRuleDuplicateRuleIdError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A custom rule with this ID already exists in this policy.",
        ) from error
    except CustomRuleDisallowedFieldError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except CustomRuleFieldCannotBeNullError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


@router.delete("/{custom_rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_rule(
    policy_id: int,
    custom_rule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Delete a custom rule from a policy (admin only)."""
    service = CustomRuleService(db)

    try:
        service.delete_custom_rule(policy_id, custom_rule_id)
    except CustomRulePolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error
    except CustomRuleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom rule not found",
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
