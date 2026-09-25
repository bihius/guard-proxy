"""Learning-mode tuning suggestions for a policy (issue #263)."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.tuning_suggestion import SuggestionStatus, TuningSuggestion
from app.models.user import User
from app.schemas.rule_exclusion import RuleExclusionCreate
from app.schemas.tuning_suggestion import (
    TuningAnalysisResponse,
    TuningSuggestionResponse,
)
from app.services import tuning_service
from app.services.tuning_service import (
    TuningPolicyNotFoundError,
    TuningSuggestionNotFoundError,
    TuningSuggestionNotPendingError,
)

router = APIRouter(prefix="/policies/{policy_id}/suggestions", tags=["tuning"])


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, TuningPolicyNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")
    if isinstance(error, TuningSuggestionNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Suggestion not found")
    return HTTPException(status.HTTP_409_CONFLICT, "Suggestion was already reviewed")


@router.get("", response_model=list[TuningSuggestionResponse])
def list_suggestions(
    policy_id: int,
    suggestion_status: SuggestionStatus | None = Query(
        default=SuggestionStatus.pending, alias="status"
    ),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[TuningSuggestion]:
    """Suggestions for the policy, most likely false positives first."""
    try:
        return tuning_service.list_suggestions(db, policy_id, suggestion_status)
    except TuningPolicyNotFoundError as error:
        raise _http_error(error) from error


@router.post("/analyze", response_model=TuningAnalysisResponse)
def analyze(
    policy_id: int,
    window_hours: int = Query(default=24, ge=1, le=720),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> TuningAnalysisResponse:
    """Analyze the policy's recent WAF events now (admin only).

    The nightly job does the same for active detect-only policies; this lets
    an admin run it on demand and for any policy.
    """
    try:
        result = tuning_service.analyze_policy(
            db, policy_id, window=timedelta(hours=window_hours)
        )
    except TuningPolicyNotFoundError as error:
        raise _http_error(error) from error
    return TuningAnalysisResponse(
        events_scanned=result.events_scanned,
        created=result.created,
        updated=result.updated,
        window_hours=window_hours,
    )


@router.post("/{suggestion_id}/approve", response_model=TuningSuggestionResponse)
def approve(
    policy_id: int,
    suggestion_id: int,
    body: RuleExclusionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> TuningSuggestion:
    """Create the exclusion the admin reviewed and mark the suggestion approved.

    The body is the exclusion to create, so the admin can narrow the scope or
    change the target before approving.
    """
    try:
        return tuning_service.approve_suggestion(db, policy_id, suggestion_id, body)
    except (
        TuningPolicyNotFoundError,
        TuningSuggestionNotFoundError,
        TuningSuggestionNotPendingError,
    ) as error:
        raise _http_error(error) from error


@router.post("/{suggestion_id}/reject", response_model=TuningSuggestionResponse)
def reject(
    policy_id: int,
    suggestion_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> TuningSuggestion:
    """Dismiss the suggestion; the analyzer will not propose it again."""
    try:
        return tuning_service.reject_suggestion(db, policy_id, suggestion_id)
    except (
        TuningPolicyNotFoundError,
        TuningSuggestionNotFoundError,
        TuningSuggestionNotPendingError,
    ) as error:
        raise _http_error(error) from error
