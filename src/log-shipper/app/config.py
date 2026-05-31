"""Runtime configuration for the log shipper, sourced from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Shipper settings resolved from environment variables."""

    ingest_url: str
    ingest_secret: str
    audit_log_path: str
    state_file: str
    poll_interval_seconds: float
    backoff_base_seconds: float
    backoff_max_seconds: float
    request_timeout_seconds: float


def load_settings() -> Settings:
    """Build :class:`Settings` from the process environment."""

    secret = os.environ.get("LOG_INGEST_SHARED_SECRET", "").strip()
    if not secret:
        raise RuntimeError("LOG_INGEST_SHARED_SECRET must be set")

    return Settings(
        ingest_url=os.environ.get(
            "INGEST_URL", "http://backend:8000/logs/ingest"
        ).strip(),
        ingest_secret=secret,
        audit_log_path=os.environ.get(
            "CORAZA_AUDIT_LOG", "/var/log/coraza/audit.log"
        ).strip(),
        state_file=os.environ.get(
            "SHIPPER_STATE_FILE", "/var/lib/log-shipper/offset"
        ).strip(),
        poll_interval_seconds=float(os.environ.get("SHIPPER_POLL_INTERVAL", "1")),
        backoff_base_seconds=float(os.environ.get("SHIPPER_BACKOFF_BASE", "1")),
        backoff_max_seconds=float(os.environ.get("SHIPPER_BACKOFF_MAX", "30")),
        request_timeout_seconds=float(os.environ.get("SHIPPER_REQUEST_TIMEOUT", "5")),
    )
