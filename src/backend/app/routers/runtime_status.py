"""Runtime/deployment status API router."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.runtime_status import RuntimeStatusResponse
from app.services.runtime_status_service import RuntimeStatusService

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/status", response_model=RuntimeStatusResponse)
def get_runtime_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RuntimeStatusResponse:
    """Return runtime/deployed configuration status for dashboard use."""
    service = RuntimeStatusService(db)
    return service.get_runtime_status()
