"""Tail the Coraza audit log and ship each event to the backend ingest endpoint.

Durability model: the audit file *is* the buffer. We persist a byte offset and only
advance it once an event has been accepted (2xx) or is known-undeliverable (a 4xx
poison pill we deliberately drop). Transient failures (network errors, 5xx, 429,
and auth errors 401/403) trigger exponential backoff with the offset frozen, so a
backend outage or misconfigured secret stalls the pipeline rather than dropping events.
"""

from __future__ import annotations

import enum
import json
import logging
import os
import signal
import time
import urllib.error
import urllib.request
from types import FrameType

from app.config import Settings, load_settings
from app.mapping import coraza_event_to_ingest

logger = logging.getLogger("log-shipper")

_running = True

# Maximum bytes consumed by a single readline() call.  Coraza audit events are
# typically 2–10 KB; 1 MB is a generous upper bound that prevents an unterminated
# line from growing the in-memory buffer without limit.
_MAX_LINE_BYTES = 1 * 1024 * 1024


class _ShipResult(enum.Enum):
    SHIPPED = "shipped"      # accepted by backend (2xx) — advance offset
    DROPPED = "dropped"      # permanent failure (parse error, 422, etc.) — advance offset
    ABORTED = "aborted"      # shutdown during retry — do NOT advance offset


def _handle_term(_signum: int, _frame: FrameType | None) -> None:
    global _running
    _running = False


def _load_offset(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as handle:
            return int(handle.read().strip() or "0")
    except (FileNotFoundError, ValueError):
        return 0


def _persist_offset(path: str, offset: int) -> None:
    # Atomic rename avoids a torn write, but we intentionally skip fsync: durability
    # is provided by idempotency (producer_event_id deduplicates at the backend),
    # so a crash that rolls back the offset is safe — the re-shipped line produces a
    # 200 rather than a duplicate row.
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(str(offset))
    os.replace(tmp, path)


def _post_event(settings: Settings, payload: dict[str, object]) -> int:
    """POST a single event; return the HTTP status code or raise on transport error."""

    request = urllib.request.Request(
        settings.ingest_url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Guard-Proxy-Ingest-Secret": settings.ingest_secret,
        },
    )
    with urllib.request.urlopen(
        request, timeout=settings.request_timeout_seconds
    ) as response:
        return response.status


def _ship_line(settings: Settings, line: bytes) -> _ShipResult:
    """Block until ``line`` is shipped, dropped, or the process is shutting down.

    Returns:
        SHIPPED  — backend accepted the event (2xx); advance offset.
        DROPPED  — permanent failure (unparseable, unmappable, or 4xx payload
                   rejection); advance offset to skip the poison pill.
        ABORTED  — shutdown signal arrived during a retry sleep; do NOT advance
                   the offset so the line is re-attempted on next start.
    """

    text = line.decode("utf-8", errors="replace").strip()
    if not text:
        return _ShipResult.DROPPED

    try:
        event = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("dropping unparseable audit line")
        return _ShipResult.DROPPED
    if not isinstance(event, dict):
        logger.warning("dropping non-object audit line")
        return _ShipResult.DROPPED

    payload = coraza_event_to_ingest(event)
    if payload is None:
        logger.warning("dropping event that cannot be mapped to an ingest payload")
        return _ShipResult.DROPPED

    backoff = settings.backoff_base_seconds
    while _running:
        try:
            status = _post_event(settings, payload)
            logger.info("shipped event producer_event_id=%s status=%s",
                        payload["producer_event_id"], status)
            return _ShipResult.SHIPPED
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                # Auth rejection is a config error (wrong shared secret), not a
                # per-event poison pill.  Stall with backoff so the pipeline pauses
                # loudly rather than silently shredding the audit stream.
                logger.warning(
                    "ingest auth rejected (%s) — check LOG_INGEST_SHARED_SECRET; "
                    "retrying in %.1fs",
                    error.code,
                    backoff,
                )
            elif error.code == 429 or error.code >= 500:
                logger.warning("ingest %s, retrying in %.1fs", error.code, backoff)
            else:
                # Other 4xx (e.g. 422 Unprocessable Entity): the backend rejected
                # this specific payload and will keep doing so.  Drop it rather
                # than blocking the pipeline.
                body = error.read().decode("utf-8", errors="replace")[:500]
                logger.error("dropping event rejected by ingest (%s): %s",
                             error.code, body)
                return _ShipResult.DROPPED
        except urllib.error.URLError as error:
            logger.warning("ingest unreachable (%s), retrying in %.1fs",
                           error.reason, backoff)

        _interruptible_sleep(backoff)
        backoff = min(backoff * 2, settings.backoff_max_seconds)

    return _ShipResult.ABORTED


def _interruptible_sleep(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while _running and time.monotonic() < deadline:
        time.sleep(min(0.5, deadline - time.monotonic()))


def run(settings: Settings) -> None:
    logger.info("log shipper starting; tailing %s", settings.audit_log_path)
    offset = _load_offset(settings.state_file)

    while _running:
        try:
            size = os.path.getsize(settings.audit_log_path)
        except FileNotFoundError:
            _interruptible_sleep(settings.poll_interval_seconds)
            continue

        # Reset on truncation.  Note: rename-based rotation (logrotate copytruncate
        # excluded) is NOT detected here because we track a byte offset, not an inode.
        # Coraza uses SecAuditLogType Serial (append-only, never rotated), so this is
        # safe for the current deployment; rotation support would require inotify or an
        # inode check.
        if size < offset:
            logger.warning("audit log truncated; resetting offset to 0")
            offset = 0
            _persist_offset(settings.state_file, offset)

        progressed = False
        with open(settings.audit_log_path, "rb") as handle:
            handle.seek(offset)
            while _running:
                line = handle.readline(_MAX_LINE_BYTES)
                if not line:
                    break
                if not line.endswith(b"\n"):
                    # Partial trailing line (writer hasn't flushed yet, or the line
                    # exceeded _MAX_LINE_BYTES): wait for the next poll cycle.
                    break
                result = _ship_line(settings, line)
                if result is _ShipResult.ABORTED:
                    # Shutdown during retry — do not advance the offset.
                    break
                offset += len(line)
                _persist_offset(settings.state_file, offset)
                progressed = True

        if not progressed:
            _interruptible_sleep(settings.poll_interval_seconds)

    logger.info("log shipper stopped at offset %d", offset)


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    signal.signal(signal.SIGTERM, _handle_term)
    signal.signal(signal.SIGINT, _handle_term)
    run(load_settings())


if __name__ == "__main__":
    main()
