"""Auth router — login, token refresh, current user."""

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import AccessTokenResponse, LoginRequest
from app.schemas.user import UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
_REFRESH_COOKIE_PATH = "/auth"

# Precomputed bcrypt hash used for timing-attack mitigation when user is missing.
# Keep this as a constant to avoid bcrypt work during module import/startup.
# Value is for plain text: "dummy-guard-proxy".
_DUMMY_HASH: str = "$2b$12$l.ip0p2T3WgWHyi7eDv2XOHxntTAt0e9J4Eycj14Qq5Du6QlVq/Du"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Sets the refresh token as an HttpOnly cookie.

    The cookie is intentionally unavailable to JavaScript (`httponly=True`), so
    the frontend does not keep a long-lived token in localStorage or UI memory.
    """
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=refresh_token,
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_refresh_cookie_secure,
        samesite=settings.auth_refresh_cookie_samesite,
        path=_REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_refresh_cookie_name,
        httponly=True,
        secure=settings.auth_refresh_cookie_secure,
        samesite=settings.auth_refresh_cookie_samesite,
        path=_REFRESH_COOKIE_PATH,
    )


@router.post("/login", response_model=AccessTokenResponse)
def login(
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    """Login endpoint returning an access token and setting refresh token cookie.

    Returns 401 when email does not exist, password is invalid, or account
    is inactive. We intentionally do not distinguish these cases so an attacker
    cannot infer whether email, password, or account state was the reason.
    """
    user = db.query(User).filter(User.email == body.email).first()

    # Always call bcrypt, regardless of whether user exists.
    # hash_to_check = real hash when user exists, dummy hash otherwise.
    # This keeps response timing consistent and mitigates timing attacks.
    hash_to_check = user.hashed_password if user is not None else _DUMMY_HASH
    password_ok = auth_service.verify_password(body.password, hash_to_check)

    # Check is_active together with password_ok; do not return a separate error
    # for inactive accounts, because that would confirm valid email+password
    # to an attacker (credential confirmation / account enumeration).
    if not password_ok or user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    refresh_token = auth_service.create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh_token)

    return AccessTokenResponse(
        access_token=auth_service.create_access_token(user.id, user.role)
    )


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    """Refresh endpoint reading refresh token from cookie.

    Frontend sends request with credentials/include and backend reads cookie.
    This keeps refresh token out of JavaScript and out of request JSON body.
    """
    refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = auth_service.decode_refresh_token(refresh_token)
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    new_refresh_token = auth_service.create_refresh_token(user.id)
    _set_refresh_cookie(response, new_refresh_token)

    return AccessTokenResponse(
        access_token=auth_service.create_access_token(user.id, user.role)
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    """Logout endpoint clearing refresh cookie on backend side."""
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    """Returns the currently authenticated user's profile.

    No extra DB query is needed — get_current_user already loads the user.
    """
    return current_user
