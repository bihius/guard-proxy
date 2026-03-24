"""Logs router — odczyt logów z filtrowaniem i paginacją."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.log import Log, LogSeverity
from app.models.user import User
from app.schemas.log import LogListResponse

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=LogListResponse)
def list_logs(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    vhost: str | None = Query(default=None, min_length=1, max_length=255),
    severity: LogSeverity | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> LogListResponse:
    """Zwraca logi z opcjonalnym filtrowaniem i paginacją.

    date_from / date_to:
    filtrują po czasie zdarzenia.

    page / page_size:
    mówią które rekordy zwrócić, żeby nie wysyłać całej tabeli naraz.
    """
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from cannot be later than date_to",
        )

    query = db.query(Log)

    if date_from is not None:
        query = query.filter(Log.logged_at >= date_from)
    if date_to is not None:
        query = query.filter(Log.logged_at <= date_to)
    if vhost is not None:
        query = query.filter(Log.vhost == vhost)
    if severity is not None:
        query = query.filter(Log.severity == severity)

    total = query.count()
    items = (
        query.order_by(Log.logged_at.desc(), Log.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return LogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
