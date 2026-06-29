"""VHosts API router — virtual host CRUD."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.policy_binding import PolicyBinding
from app.models.user import User
from app.models.vhost import VHost
from app.schemas.policy_binding import PolicyBindingCreate, PolicyBindingResponse
from app.schemas.vhost import (
    VHostCreate,
    VHostDetail,
    VHostListResponse,
    VHostResponse,
    VHostUpdate,
)
from app.services.vhost_service import (
    PolicyBindingAlreadyExistsError,
    PolicyBindingDefaultManagedByVHostError,
    PolicyBindingFieldCannotBeNullError,
    PolicyBindingInvalidPathPrefixError,
    PolicyBindingInvalidPriorityError,
    PolicyBindingNotFoundError,
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
    """Creates a new vhost (admin only)."""
    service = VHostService(db)

    try:
        return service.create_vhost(
            domain=body.domain,
            backend_url=body.backend_url,
            description=body.description,
            ssl_enabled=body.ssl_enabled,
            ssl_provider=body.ssl_provider,
            ssl_cert=body.ssl_cert,
            ssl_key=body.ssl_key,
            is_active=body.is_active,
            policy_id=body.policy_id,
            created_by=current_user.id,
            user_email=current_user.email,
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
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.get("", response_model=VHostListResponse)
def list_vhosts(
    page: int = Query(default=1, ge=1, le=10_000),
    per_page: int = Query(default=50, ge=1, le=500),
    q: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> VHostListResponse:
    """Returns a paginated list of vhosts, optionally filtered by domain."""
    service = VHostService(db)
    items, total = service.list_vhosts(page=page, per_page=per_page, q=q)
    return VHostListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{vhost_id}", response_model=VHostDetail)
def get_vhost(
    vhost_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> VHost:
    """Returns vhost details with full policy."""
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
    current_user: User = Depends(require_admin),
) -> VHost:
    """Updates selected vhost fields (admin only)."""
    service = VHostService(db)

    try:
        return service.update_vhost(
            vhost_id, 
            body.model_dump(exclude_unset=True), 
            user_email=current_user.email
        )
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
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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
    """Deletes vhost by ID (admin only)."""
    service = VHostService(db)
    try:
        service.delete_vhost(vhost_id)
    except VHostNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VHost not found",
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{vhost_id}/policy-bindings",
    response_model=list[PolicyBindingResponse],
)
def list_policy_bindings(
    vhost_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[PolicyBinding]:
    """Return path-scoped policy bindings for a vhost."""
    service = VHostService(db)

    try:
        return service.list_policy_bindings(vhost_id)
    except VHostNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VHost not found",
        ) from error


@router.post(
    "/{vhost_id}/policy-bindings",
    response_model=PolicyBindingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_policy_binding(
    vhost_id: int,
    body: PolicyBindingCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> PolicyBinding:
    """Create a path-scoped policy binding for a vhost."""
    service = VHostService(db)

    try:
        return service.create_policy_binding(
            vhost_id,
            policy_id=body.policy_id,
            path_prefix=body.path_prefix,
            priority=body.priority,
            comment=body.comment,
        )
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
    except PolicyBindingAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Policy binding already exists",
        ) from error
    except PolicyBindingDefaultManagedByVHostError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except (
        PolicyBindingFieldCannotBeNullError,
        PolicyBindingInvalidPathPrefixError,
        PolicyBindingInvalidPriorityError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


@router.delete(
    "/{vhost_id}/policy-bindings/{binding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_policy_binding(
    vhost_id: int,
    binding_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Delete a path-scoped policy binding from a vhost."""
    service = VHostService(db)

    try:
        service.delete_policy_binding(vhost_id, binding_id)
    except VHostNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VHost not found",
        ) from error
    except PolicyBindingNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy binding not found",
        ) from error
    except PolicyBindingDefaultManagedByVHostError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
