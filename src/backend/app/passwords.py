"""Password hashing helpers shared by runtime code and DB-only tooling."""

import logging

from passlib.context import CryptContext

logger = logging.getLogger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return whether a plaintext password matches the stored hash."""
    try:
        return bool(_pwd_context.verify(plain_password, hashed_password))
    except ValueError:
        logger.warning("Password verification failed: unrecognized or malformed hash")
        return False
