"""Security API router — auto-ban list read/unban via HAProxy Runtime API."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.schemas.security import BannedIpListResponse, UnbanResponse
from app.services.ban_list_service import (
    BanListService,
    InvalidIpError,
    RuntimeApiError,
)

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/banned-ips", response_model=BannedIpListResponse)
def list_banned_ips(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> BannedIpListResponse:
    """Returns tracked/banned source IPs across auto-ban-enabled vhosts (admin only)."""
    service = BanListService(db)
    try:
        items = service.list_banned()
    except RuntimeApiError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to reach HAProxy Runtime API",
        ) from error
    return BannedIpListResponse(items=items, total=len(items))


@router.delete("/banned-ips/{ip}", response_model=UnbanResponse)
def unban_ip(
    ip: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UnbanResponse:
    """Clears a source IP from every active ban stick-table (admin only)."""
    service = BanListService(db)
    try:
        return service.unban(ip)
    except InvalidIpError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except RuntimeApiError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to reach HAProxy Runtime API",
        ) from error
