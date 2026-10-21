"""Pydantic schemas for runtime/deployment status endpoint."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.models.runtime_operation import (
    RuntimeOperationStatus,
    RuntimeOperationType,
)

DeploymentState = Literal["never_deployed", "deployed", "failed"]
HaproxyConfigSource = Literal["generated", "seed", "missing"]
CorazaConfigSource = Literal["generated", "fallback"]


class RuntimeGeneratedConfigStatus(BaseModel):
    """Current generated configuration summary produced at request time."""

    can_generate: bool
    checksum: str | None = None
    generated_at: datetime | None = None
    error: str | None = None
    # Domains of active vhosts that have no policy assigned. They will be
    # served using the default CRS context. Listed here as a visibility aid
    # so operators know which vhosts are running without an explicit policy.
    unbound_vhost_domains: list[str] | None = None


class ActiveRuntimeConfig(BaseModel):
    """What HAProxy and Coraza are actually running from right now (issue #315).

    A `seed` or `missing` HAProxy source means the reference/demo config is
    serving traffic; a `fallback` Coraza source means the single application
    baked into the Coraza image inspects every request at paranoia level 1 in
    detect-only mode and the per-policy settings are ignored.
    """

    haproxy_source: HaproxyConfigSource
    coraza_source: CorazaConfigSource
    degraded: bool
    warning: str | None = None


class VersionAgreement(BaseModel):
    """Versions the stack pieces must agree on (issue #316).

    `configured_image_tag` is the tag the operator wrote into `.env`; it is
    None when the backend is not run from the release kit. `warning` is set
    when that tag and this backend's own version disagree, which means the
    stack mixes images from different releases.
    """

    app_version: str
    configured_image_tag: str | None
    crs_version: str
    warning: str | None = None


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
    active_config: ActiveRuntimeConfig
    version_agreement: VersionAgreement
    latest_validation: RuntimeOperationSnapshot | None = None
    latest_reload: RuntimeOperationSnapshot | None = None
