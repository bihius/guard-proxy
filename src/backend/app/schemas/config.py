"""Pydantic schemas for config apply endpoint."""

from pydantic import BaseModel


class GeneratedConfigOut(BaseModel):
    haproxy_cfg: str
    crs_setup_conf: str
    rule_overrides_conf: str


class ConfigApplyResponse(BaseModel):
    generated_config: GeneratedConfigOut
    status: str
    correlation_id: str
    checksum: str
    message: str
    candidate_path: str
    active_path: str | None
    validation_output: str | None
    reload_output: str | None
    rollback_output: str | None
