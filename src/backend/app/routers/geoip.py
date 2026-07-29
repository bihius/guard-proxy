"""GeoIP database refresh API router (issue #175)."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import require_admin
from app.models.user import User
from app.schemas.geoip import GeoipRefreshResponse
from app.services import geoip_service

router = APIRouter(prefix="/geoip", tags=["geoip"])


@router.post("/refresh", response_model=GeoipRefreshResponse)
def refresh_geoip_database(
    _: User = Depends(require_admin),
) -> GeoipRefreshResponse:
    """Trigger an on-demand GeoIP database refresh (admin only).

    Shares its implementation with the scheduled daily refresh job (see
    app.services.scheduler.refresh_geoip_database). The concurrency guard
    lives in the service, not here, so the scheduled job contends for the
    same lock — a lock held only by this router would not serialise the two.
    """
    result = geoip_service.try_refresh()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A GeoIP refresh is already running",
        )

    return GeoipRefreshResponse(
        downloaded=result.downloaded,
        entries=result.entries,
        changed=result.changed,
        reloaded=result.reloaded,
        message=result.message,
    )
