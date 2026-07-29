"""Pydantic schemas for the GeoIP database refresh endpoint."""

from pydantic import BaseModel


class GeoipRefreshResponse(BaseModel):
    """Result of a GeoIP database refresh run returned by POST /geoip/refresh."""

    downloaded: bool
    entries: int
    changed: bool
    reloaded: bool
    message: str
