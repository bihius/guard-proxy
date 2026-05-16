"""Pydantic schemas for runtime/deployment status endpoint."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.models.runtime_operation import (
    RuntimeOperationStatus,
    RuntimeOperationType,
)

DeploymentState = Literal["never_deployed", "deployed", "failed"]


class RuntimeGeneratedConfigStatus(BaseModel):
    """Current generated configuration summary produced at request time."""

    can_generate: bool
    checksum: str | None = None
    generated_at: datetime | None = None
    error: str | None = None


class RuntimeOperationSnapshot(BaseModel):
    """Latest persisted status for a specific runtime operation type."""

    id: int
    operation_type: RuntimeOperationType
    status: RuntimeOperationStatus
    config_checksum: str | None = None
    message: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime


class RuntimeStatusResponse(BaseModel):
    """Response body returned by GET /runtime/status."""

    frontend_contract_version: str
    deployment_state: DeploymentState
    generated_config: RuntimeGeneratedConfigStatus
    latest_validation: RuntimeOperationSnapshot | None = None
    latest_reload: RuntimeOperationSnapshot | None = None
