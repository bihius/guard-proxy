"""Pydantic schemas for the dashboard aggregation endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

StatsWindow = Literal["1h", "24h", "7d", "30d"]


class MetricValue(BaseModel):
    """A counter for the selected window, compared against the previous one."""

    current: int
    previous: int
    # None when `previous` is 0 — a percentage change from nothing is not
    # meaningful, and the UI renders "new" instead of an infinite delta.
    delta_pct: float | None = None


class WindowBounds(BaseModel):
    """Time range every stats response is scoped to."""

    window: StatsWindow
    start_at: datetime
    end_at: datetime


class OverviewResponse(WindowBounds):
    """Response body returned by GET /stats/overview."""

    requests: MetricValue
    blocked: MetricValue
    monitored: MetricValue
    critical: MetricValue
    # None for non-admins and whenever the HAProxy Runtime API is unreachable —
    # a dead stats socket must not take the whole dashboard down with it.
    banned_ips: int | None = None
    protected_vhosts: int
    total_vhosts: int
    active_policies: int


class TimeseriesBucket(BaseModel):
    """Event counts for one time bucket, split by outcome."""

    bucket_at: datetime
    allow: int
    deny: int
    monitor: int


class TimeseriesResponse(WindowBounds):
    """Response body returned by GET /stats/timeseries."""

    bucket_seconds: int
    # Dense: empty intervals are returned as explicit zero buckets so the
    # client never has to reconstruct the time axis itself.
    buckets: list[TimeseriesBucket]


class TopRule(BaseModel):
    """A CRS/custom rule ranked by how often it denied a request."""

    rule_id: int
    rule_message: str | None = None
    count: int


class TopSourceIp(BaseModel):
    """A source IP ranked by how many of its requests were denied."""

    source_ip: str
    count: int
    # Always false for non-admins: the ban list is admin-only.
    is_banned: bool = False


class TopVHost(BaseModel):
    """A vhost ranked by how many requests were denied against it."""

    vhost: str
    vhost_id: int | None = None
    count: int


class TopResponse(WindowBounds):
    """Response body returned by GET /stats/top."""

    limit: int = Field(ge=1, le=20)
    rules: list[TopRule]
    source_ips: list[TopSourceIp]
    vhosts: list[TopVHost]
