from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRET_VALUES = {
    "replace-this-with-a-random-secret",
    "replace-this-with-a-second-random-secret",
    "change-me",
    "changeme",
}


def _validate_secret(value: str, field_name: str) -> str:
    """Reject empty or template placeholder secrets."""
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    if normalized.lower() in _PLACEHOLDER_SECRET_VALUES:
        raise ValueError(
            f"{field_name} must be replaced with a real secret before startup."
        )
    return normalized


def _validate_database_url(value: str) -> str:
    """Reject empty database URL values."""
    if not value.strip():
        raise ValueError("DATABASE_URL must not be empty")
    return value


class EnvFileSettings(BaseSettings):
    """Base settings loaded from the real runtime environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class DatabaseSettings(EnvFileSettings):
    """Database settings shared by the application and tooling."""

    database_url: str = "sqlite:///./guard_proxy.db"
    debug: bool = False

    @field_validator("database_url")
    @classmethod
    def database_url_must_not_be_empty(cls, value: str) -> str:
        return _validate_database_url(value)


class Settings(EnvFileSettings):
    """Application runtime settings."""

    # Application
    app_name: str = "Guard Proxy API"
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
    debug: bool = False

    @field_validator("database_url")
    @classmethod
    def database_url_must_not_be_empty(cls, value: str) -> str:
        return _validate_database_url(value)

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
        return _validate_secret(v, "JWT_SECRET_KEY")

    @field_validator("auth_refresh_cookie_name")
    @classmethod
    def auth_refresh_cookie_name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("AUTH_REFRESH_COOKIE_NAME must not be empty.")
        return v

    @field_validator("log_ingest_shared_secret")
    @classmethod
    def log_ingest_shared_secret_must_not_be_empty(cls, v: str) -> str:
        return _validate_secret(v, "LOG_INGEST_SHARED_SECRET")

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

    @model_validator(mode="after")
    def validate_cookie_settings(self) -> "Settings":
        if (
            self.auth_refresh_cookie_samesite == "none"
            and not self.auth_refresh_cookie_secure
        ):
            raise ValueError(
                "AUTH_REFRESH_COOKIE_SECURE must be true when "
                "AUTH_REFRESH_COOKIE_SAMESITE is 'none'."
            )
        return self


def validate_runtime_settings(settings_obj: Settings) -> Settings:
    """Run explicit runtime validation during application startup."""
    return Settings()


@lru_cache
def get_settings() -> Settings:
    """Return cached runtime settings."""
    return Settings()


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """Return cached database settings for tooling and runtime DB setup."""
    return DatabaseSettings()


settings = get_settings()
