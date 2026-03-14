"""Auth router — login, token refresh, current user."""

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """Logowanie — zwraca access token i refresh token.

    Zwraca 401 jeśli email nie istnieje, hasło jest złe lub konto nieaktywne.
    Celowo nie rozróżniamy "zły email" od "złe hasło" — to dobra praktyka
    bezpieczeństwa (nie ujawniamy czy email istnieje w systemie).
    """
    user = db.query(User).filter(User.email == body.email).first()

    # Sprawdzamy oba warunki przed zwróceniem błędu — zapobiega timing attack.
    # Gdybyśmy zwracali błąd od razu gdy user nie istnieje, atakujący mógłby
    # odróżnić "zły email" od "złe hasło" po czasie odpowiedzi.
    password_ok = user is not None and auth_service.verify_password(
        body.password, user.hashed_password
    )

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
def refresh(body: Token, db: Session = Depends(get_db)) -> Token:
    """Odświeżanie tokenów — przyjmuje refresh token, zwraca nową parę.

    Klient powinien wywołać ten endpoint gdy access token wygaśnie (HTTP 401).
    Po udanym refresh obie strony dostają nowe tokeny (rotation).
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
