"""Router VHosts API — CRUD wirtualnych hostów."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.user import User
from app.models.vhost import VHost
from app.schemas.vhost import VHostCreate, VHostDetail, VHostResponse, VHostUpdate
from app.services.vhost_service import (
    VHostDomainAlreadyExistsError,
    VHostFieldCannotBeNullError,
    VHostNotFoundError,
    VHostPolicyNotFoundError,
    VHostService,
)

router = APIRouter(prefix="/vhosts", tags=["vhosts"])


@router.post("", response_model=VHostResponse, status_code=status.HTTP_201_CREATED)
def create_vhost(
    body: VHostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> VHost:
    """Tworzy nowy vhost (tylko admin)."""
    service = VHostService(db)

    try:
        return service.create_vhost(
            domain=body.domain,
            backend_url=body.backend_url,
            description=body.description,
            ssl_enabled=body.ssl_enabled,
            is_active=body.is_active,
            policy_id=body.policy_id,
            created_by=current_user.id,
        )
    except VHostPolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error
    except VHostDomainAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="VHost domain already exists",
        ) from error


@router.get("", response_model=list[VHostResponse])
def list_vhosts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[VHost]:
    """Zwraca listę vhostów (admin i viewer)."""
    service = VHostService(db)
    return service.list_vhosts()


@router.get("/{vhost_id}", response_model=VHostDetail)
def get_vhost(
    vhost_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> VHost:
    """Zwraca szczegóły vhosta razem z pełną polityką."""
    service = VHostService(db)
    try:
        return service.get_vhost(vhost_id)
    except VHostNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VHost not found",
        ) from error


@router.patch("/{vhost_id}", response_model=VHostResponse)
def update_vhost(
    vhost_id: int,
    body: VHostUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> VHost:
    """Aktualizuje wskazane pola vhosta (tylko admin)."""
    service = VHostService(db)

    try:
        return service.update_vhost(vhost_id, body.model_dump(exclude_unset=True))
    except VHostNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VHost not found",
        ) from error
    except VHostPolicyNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        ) from error
    except VHostFieldCannotBeNullError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except VHostDomainAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="VHost domain already exists",
        ) from error


@router.delete("/{vhost_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vhost(
    vhost_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Usuwa vhost po ID (tylko admin)."""
    service = VHostService(db)
    try:
        service.delete_vhost(vhost_id)
    except VHostNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VHost not found",
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
