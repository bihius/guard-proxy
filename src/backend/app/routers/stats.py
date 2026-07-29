"""Stats API router — aggregated counters powering the operations dashboard."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.schemas.stats import (
    OverviewResponse,
    StatsWindow,
    TimeseriesResponse,
    TopResponse,
)
from app.services.stats_service import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    window: StatsWindow = Query(default="24h"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OverviewResponse:
    """Dashboard KPI counters for the window, with previous-window deltas."""
    return StatsService(db).overview(
        window,
        include_banned_ips=user.role == UserRole.admin,
    )


@router.get("/timeseries", response_model=TimeseriesResponse)
def get_timeseries(
    window: StatsWindow = Query(default="24h"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TimeseriesResponse:
    """Bucketed allow/deny/monitor counts for charting the window."""
    return StatsService(db).timeseries(window)


@router.get("/top", response_model=TopResponse)
def get_top(
    window: StatsWindow = Query(default="24h"),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TopResponse:
    """Most frequently triggered rules, attacking IPs and targeted vhosts."""
    return StatsService(db).top(
        window,
        limit=limit,
        include_ban_state=user.role == UserRole.admin,
    )
