"""Pydantic schemas for log event ingestion and read APIs."""

from datetime import datetime
from ipaddress import ip_address
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.log import LogAction, LogSeverity


class LogResponse(BaseModel):
    """Single persisted event returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    producer_event_id: str | None
    event_at: datetime
    vhost: str
    action: LogAction
    source_ip: str
    method: str
    request_uri: str
    status_code: int | None
    rule_id: int | None
    rule_message: str | None
    anomaly_score: int | None
    paranoia_level: int | None
    severity: LogSeverity
    message: str | None
    raw_context: dict[str, Any] | None


class LogListResponse(BaseModel):
    """Paginated response returned by GET /logs."""

    items: list[LogResponse]
    total: int
    page: int
    page_size: int


class LogIngestRequest(BaseModel):
    """Payload accepted from a future runtime log producer."""

    producer_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    event_at: datetime
    vhost: str = Field(min_length=1, max_length=255)
    action: LogAction
    source_ip: str = Field(min_length=1, max_length=45)
    method: str = Field(min_length=1, max_length=16)
    request_uri: str = Field(min_length=1)
    status_code: int | None = Field(default=None, ge=100, le=599)
    rule_id: int | None = Field(default=None, gt=0)
    rule_message: str | None = None
    anomaly_score: int | None = Field(default=None, ge=0)
    paranoia_level: int | None = Field(default=None, ge=1, le=4)
    severity: LogSeverity
    message: str | None = None
    raw_context: dict[str, Any] | None = None

    @field_validator("producer_event_id", "rule_message", "message", mode="before")
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("vhost")
    @classmethod
    def normalize_vhost(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("source_ip")
    @classmethod
    def validate_source_ip(cls, value: str) -> str:
        normalized = value.strip()
        return str(ip_address(normalized))

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("request_uri")
    @classmethod
    def normalize_request_uri(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("request_uri cannot be empty")
        return normalized
