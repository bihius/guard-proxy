"""FastAPI dependencies — reusable building blocks for protected endpoints."""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services import auth_service

# HTTPBearer czyta nagłówek "Authorization: Bearer <token>" z każdego requestu.
# auto_error=False — nie rzucamy błędu tutaj, obsługujemy to sami niżej
# żeby zwrócić czytelniejszy komunikat.
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: dekoduje JWT i zwraca aktualnie zalogowanego usera.

    Używaj jako parametr endpointu:
        def my_endpoint(user: User = Depends(get_current_user)): ...

    Raises:
        401 — brak tokena, token niepoprawny lub wygasły
        401 — user nie istnieje w bazie
        403 — konto użytkownika jest nieaktywne
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
    """Dependency: wymaga roli admin.

    Używaj zamiast get_current_user gdy endpoint jest tylko dla adminów:
        def my_endpoint(user: User = Depends(require_admin)): ...

    Raises:
        403 — zalogowany user nie jest adminem
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user
