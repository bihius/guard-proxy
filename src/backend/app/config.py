from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Guard Proxy API"
    debug: bool = False
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

    # Database
    database_url: str = "sqlite:///./guard_proxy.db"

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    auth_refresh_cookie_name: str = "guard_proxy_refresh_token"
    auth_refresh_cookie_secure: bool = False
    auth_refresh_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    log_ingest_shared_secret: str

    @field_validator("jwt_secret_key")
    @classmethod
    def jwt_secret_key_must_not_be_empty(cls, v: str) -> str:
        """Ensure JWT secret key is set — an empty key would be a security hole."""
        if not v.strip():
            raise ValueError(
                "JWT_SECRET_KEY must not be empty. "
                "Set it in .env or as an environment variable."
            )
        return v

    @field_validator("auth_refresh_cookie_name")
    @classmethod
    def auth_refresh_cookie_name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("AUTH_REFRESH_COOKIE_NAME must not be empty.")
        return v

    @field_validator("log_ingest_shared_secret")
    @classmethod
    def log_ingest_shared_secret_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("LOG_INGEST_SHARED_SECRET must not be empty.")
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Allow CORS origins to be configured as CSV or JSON-style arrays."""
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []

            if value.startswith("["):
                import json

                parsed = json.loads(value)
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS JSON value must be a list.")
                return [str(origin).strip() for origin in parsed if str(origin).strip()]

            return [origin.strip() for origin in value.split(",") if origin.strip()]

        return value


settings = Settings()
