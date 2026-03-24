"""Router VHosts API — CRUD wirtualnych hostów."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.policy import Policy
from app.models.user import User
from app.models.vhost import VHost
from app.schemas.vhost import VHostCreate, VHostDetail, VHostResponse, VHostUpdate

router = APIRouter(prefix="/vhosts", tags=["vhosts"])

NON_NULLABLE_PATCH_FIELDS = {
    "domain",
    "backend_url",
    "ssl_enabled",
    "is_active",
}


def _is_vhost_domain_unique_violation(error: IntegrityError) -> bool:
    """Sprawdza, czy IntegrityError dotyczy unikalnej domeny vhosta."""
    error_text = str(error.orig).lower()
    return "unique" in error_text and "domain" in error_text


def _get_vhost_or_404(db: Session, vhost_id: int) -> VHost:
    """Zwraca vhost po ID albo 404 gdy nie istnieje."""
    vhost = db.get(VHost, vhost_id)
    if vhost is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VHost not found",
        )
    return vhost


def _ensure_policy_exists(db: Session, policy_id: int | None) -> None:
    """Waliduje policy_id, jeśli request wskazuje konkretną politykę."""
    if policy_id is not None and db.get(Policy, policy_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )


@router.post("", response_model=VHostResponse, status_code=status.HTTP_201_CREATED)
def create_vhost(
    body: VHostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> VHost:
    """Tworzy nowy vhost (tylko admin)."""
    _ensure_policy_exists(db, body.policy_id)

    vhost = VHost(
        domain=body.domain,
        backend_url=body.backend_url,
        description=body.description,
        ssl_enabled=body.ssl_enabled,
        is_active=body.is_active,
        policy_id=body.policy_id,
        created_by=current_user.id,
    )
    db.add(vhost)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _is_vhost_domain_unique_violation(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="VHost domain already exists",
            )
        raise

    db.refresh(vhost)
    return vhost


@router.get("", response_model=list[VHostResponse])
def list_vhosts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[VHost]:
    """Zwraca listę vhostów (admin i viewer)."""
    return db.query(VHost).order_by(VHost.id.asc()).all()


@router.get("/{vhost_id}", response_model=VHostDetail)
def get_vhost(
    vhost_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> VHost:
    """Zwraca szczegóły vhosta razem z pełną polityką."""
    vhost = (
        db.query(VHost)
        .options(selectinload(VHost.policy))
        .filter(VHost.id == vhost_id)
        .first()
    )
    if vhost is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VHost not found",
        )
    return vhost


@router.patch("/{vhost_id}", response_model=VHostResponse)
def update_vhost(
    vhost_id: int,
    body: VHostUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> VHost:
    """Aktualizuje wskazane pola vhosta (tylko admin)."""
    vhost = _get_vhost_or_404(db, vhost_id)
    patch_data = body.model_dump(exclude_unset=True)

    for field in NON_NULLABLE_PATCH_FIELDS:
        if field in patch_data and patch_data[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Field '{field}' cannot be null",
            )

    if "policy_id" in patch_data:
        _ensure_policy_exists(db, patch_data["policy_id"])

    for field, value in patch_data.items():
        setattr(vhost, field, value)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _is_vhost_domain_unique_violation(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="VHost domain already exists",
            )
        raise

    db.refresh(vhost)
    return vhost


@router.delete("/{vhost_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vhost(
    vhost_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Usuwa vhost po ID (tylko admin)."""
    vhost = _get_vhost_or_404(db, vhost_id)
    db.delete(vhost)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
