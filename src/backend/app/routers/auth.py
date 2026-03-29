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

# Stały dummy hash — bcrypt musi wykonać się zawsze, nawet gdy user nie istnieje.
# Bez tego atakujący mógłby odróżnić "zły email" od "złe hasło" po czasie odpowiedzi
# (timing attack): brak usera → brak bcrypt → odpowiedź szybciej.
_DUMMY_HASH: str = auth_service.hash_password("dummy-guard-proxy")


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Ustawia refresh token jako HttpOnly cookie.

    Cookie jest celowo niedostępne dla JavaScriptu (`httponly=True`), dzięki czemu
    frontend nie trzyma długotrwałego tokena w localStorage ani w pamięci UI.
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
    """Logowanie — zwraca access token, a refresh token ustawia w cookie.

    Zwraca 401 jeśli email nie istnieje, hasło jest złe lub konto nieaktywne.
    Celowo nie rozróżniamy żadnego z tych przypadków — to dobra praktyka
    bezpieczeństwa: atakujący nie może odróżnić złego emaila, złego hasła
    ani nieaktywnego konta po treści odpowiedzi.
    """
    user = db.query(User).filter(User.email == body.email).first()

    # Zawsze wywołujemy bcrypt — niezależnie czy user istnieje.
    # hash_to_check = prawdziwy hash jeśli user istnieje, dummy jeśli nie.
    # Dzięki temu czas odpowiedzi jest stały i timing attack jest niemożliwy.
    hash_to_check = user.hashed_password if user is not None else _DUMMY_HASH
    password_ok = auth_service.verify_password(body.password, hash_to_check)

    # is_active sprawdzamy razem z password_ok — nie zwracamy osobnego błędu
    # dla nieaktywnych kont, bo to potwierdziłoby atakującemu że email+hasło
    # są poprawne (credential confirmation / account enumeration).
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
    """Odświeżanie tokenów — odczytuje refresh token z cookie.

    Frontend wysyła request z credentials/include, a backend sam odczytuje cookie.
    Dzięki temu refresh token nie przechodzi już przez JavaScript ani przez body JSON.
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
    """Wylogowanie — czyści refresh cookie po stronie backendu."""
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    """Zwraca dane aktualnie zalogowanego użytkownika.

    Nie wymaga dodatkowego zapytania do bazy — get_current_user już to robi.
    """
    return current_user
