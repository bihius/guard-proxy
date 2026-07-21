"""Pydantic schemas for the ban-list / unban security endpoints."""

from pydantic import BaseModel


class BannedIpResponse(BaseModel):
    """One tracked entry in a vhost's auto-ban stick-table."""

    ip: str
    vhost_id: int
    domain: str
    gpc0: int
    ban_threshold: int
    banned: bool
    expires_in_seconds: int


class BannedIpListResponse(BaseModel):
    """Response body returned by GET /security/banned-ips."""

    items: list[BannedIpResponse]
    total: int


class UnbanResponse(BaseModel):
    """Response body returned by DELETE /security/banned-ips/{ip}."""

    ip: str
    cleared: int
