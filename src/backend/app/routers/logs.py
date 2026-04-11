"""Router for log event ingestion and read APIs."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import IPvAnyAddress
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.log import Log, LogAction, LogSeverity
from app.models.user import User
from app.schemas.log import LogIngestRequest, LogListResponse, LogResponse

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("/ingest", response_model=LogResponse, status_code=status.HTTP_201_CREATED)
def ingest_log_event(
    body: LogIngestRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> Log:
    """Persist a single WAF or proxy event for later investigation."""

    if body.producer_event_id is not None:
        existing = (
            db.query(Log)
            .filter(Log.producer_event_id == body.producer_event_id)
            .one_or_none()
        )
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return existing

    log = Log(**body.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get("", response_model=LogListResponse)
def list_logs(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    vhost: str | None = Query(default=None, min_length=1, max_length=255),
    severity: LogSeverity | None = Query(default=None),
    action: LogAction | None = Query(default=None),
    source_ip: IPvAnyAddress | None = Query(default=None),
    method: str | None = Query(default=None, min_length=1, max_length=16),
    status_code: int | None = Query(default=None, ge=100, le=599),
    rule_id: int | None = Query(default=None, gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> LogListResponse:
    """Return paginated log events with investigation-oriented filters."""

    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from cannot be later than date_to",
        )

    query = db.query(Log)

    if date_from is not None:
        query = query.filter(Log.event_at >= date_from)
    if date_to is not None:
        query = query.filter(Log.event_at <= date_to)
    if vhost is not None:
        query = query.filter(Log.vhost == vhost.strip().lower())
    if severity is not None:
        query = query.filter(Log.severity == severity)
    if action is not None:
        query = query.filter(Log.action == action)
    if source_ip is not None:
        query = query.filter(Log.source_ip == _ip_to_string(source_ip))
    if method is not None:
        query = query.filter(Log.method == method.strip().upper())
    if status_code is not None:
        query = query.filter(Log.status_code == status_code)
    if rule_id is not None:
        query = query.filter(Log.rule_id == rule_id)

    total = query.count()
    items = (
        query.order_by(Log.event_at.desc(), Log.id.desc())
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


def _ip_to_string(address: IPvAnyAddress) -> str:
    return str(address)
