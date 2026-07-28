"""GeoIP database refresh API router (issue #175)."""

import threading

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import require_admin
from app.models.user import User
from app.schemas.geoip import GeoipRefreshResponse
from app.services import geoip_service

router = APIRouter(prefix="/geoip", tags=["geoip"])

# Guards against concurrent refreshes, matching app.routers.config._apply_lock.
_refresh_lock = threading.Lock()

@router.post("/refresh", response_model=GeoipRefreshResponse)
def refresh_geoip_database(
    _: User = Depends(require_admin),
) -> GeoipRefreshResponse:
    """Trigger an on-demand GeoIP database refresh (admin only).

    Shares its implementation with the scheduled weekly refresh job (see
    app.services.scheduler.refresh_geoip_database).
    """
    if not _refresh_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A GeoIP refresh is already running",
        )
    try:
        result = geoip_service.refresh()
    finally:
        _refresh_lock.release()

    response = GeoipRefreshResponse(
        configured=result.configured,
        downloaded=result.downloaded,
        entries=result.entries,
        changed=result.changed,
        reloaded=result.reloaded,
        message=result.message,
    )
    if not result.configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.message,
        )
    return response
