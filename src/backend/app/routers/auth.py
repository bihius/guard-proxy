"""Auth router — login, token refresh, current user."""

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, Token
from app.schemas.user import UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

# Stały dummy hash — bcrypt musi wykonać się zawsze, nawet gdy user nie istnieje.
# Bez tego atakujący mógłby odróżnić "zły email" od "złe hasło" po czasie odpowiedzi
# (timing attack): brak usera → brak bcrypt → odpowiedź szybciej.
_DUMMY_HASH: str = auth_service.hash_password("dummy-guard-proxy")


@router.post("/login", response_model=Token)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """Logowanie — zwraca access token i refresh token.

    Zwraca 401 jeśli email nie istnieje, hasło jest złe lub konto nieaktywne.
    Celowo nie rozróżniamy "zły email" od "złe hasło" — to dobra praktyka
    bezpieczeństwa (nie ujawniamy czy email istnieje w systemie).
    """
    user = db.query(User).filter(User.email == body.email).first()

    # Zawsze wywołujemy bcrypt — niezależnie czy user istnieje.
    # hash_to_check = prawdziwy hash jeśli user istnieje, dummy jeśli nie.
    # Dzięki temu czas odpowiedzi jest stały i timing attack jest niemożliwy.
    hash_to_check = user.hashed_password if user is not None else _DUMMY_HASH
    password_ok = auth_service.verify_password(body.password, hash_to_check)

    if not password_ok or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(
        access_token=auth_service.create_access_token(user.id, user.role),
        refresh_token=auth_service.create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=Token)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> Token:
    """Odświeżanie tokenów — przyjmuje refresh token, zwraca nową parę.

    Klient powinien wywołać ten endpoint gdy access token wygaśnie (HTTP 401).
    Zwracamy nowe tokeny (access + refresh), ale stary refresh token NIE jest
    unieważniany — pozostaje ważny aż do naturalnego wygaśnięcia (7 dni).
    Pełna invalidacja (denylist tokenów) wymaga osobnej tabeli w bazie i jest
    poza zakresem obecnej implementacji.
    """
    try:
        user_id = auth_service.decode_refresh_token(body.refresh_token)
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

    return Token(
        access_token=auth_service.create_access_token(user.id, user.role),
        refresh_token=auth_service.create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    """Zwraca dane aktualnie zalogowanego użytkownika.

    Nie wymaga dodatkowego zapytania do bazy — get_current_user już to robi.
    """
    return current_user
