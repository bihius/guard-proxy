"""FastAPI dependencies — reusable building blocks for protected endpoints."""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.services import auth_service

# HTTPBearer reads "Authorization: Bearer <token>" from each request.
# auto_error=False — do not raise here; we handle errors ourselves below
# to return a clearer message.
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: decodes JWT and returns currently authenticated user.

    Use it as an endpoint parameter:
        def my_endpoint(user: User = Depends(get_current_user)): ...

    Raises:
        401 — missing token, invalid token, or expired token
        401 — user does not exist in database
        403 — user account is inactive
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token_data = auth_service.decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, token_data.sub)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency requiring admin role.

    Use instead of get_current_user when endpoint is admin-only:
        def my_endpoint(user: User = Depends(require_admin)): ...

    Raises:
        403 — authenticated user is not an admin
    """
    if user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user
