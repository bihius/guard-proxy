"""Tail the Coraza audit log and ship each event to the backend ingest endpoint.

Durability model: the audit file *is* the buffer. The state file stores a byte
offset and, once known, the file's device and inode. The offset advances only
after an event is accepted (2xx) or deliberately dropped. A dropped line is
appended to a dead-letter file beside the state file before the offset moves.
Transient failures (network errors, timeouts, 5xx, 429, and auth errors
401/403) retry with exponential backoff and leave the offset unchanged, so a
backend outage stalls the pipeline rather than dropping events.

Rename-based rotation is detected by comparing the open file with the path.
The previous file is read to completion, then the new file is read from the
start. A same-identity file that is shorter than the offset was truncated and
is read from the start. A truncate that is refilled past the old offset before
the next poll is indistinguishable from an append and is not detected.
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
from dataclasses import dataclass
from types import FrameType
from typing import BinaryIO, Literal

from app.config import Settings, load_settings
from app.mapping import coraza_event_to_ingest

logger = logging.getLogger("log-shipper")

_running = True
_dropped_total = 0

# Maximum bytes consumed by a single readline() call. Coraza audit events are
# typically 2–10 KB; 1 MB is a generous upper bound that prevents an unterminated
# line from growing the in-memory buffer without limit. A finished line that is
# longer than this is skipped, not retried forever.
_MAX_LINE_BYTES = 1 * 1024 * 1024

# Cap a dead-letter record so one poison line cannot fill the disk.
_DEAD_LETTER_LINE_CAP = 8 * 1024

_RecordKind = Literal["line", "too_long", "truncated"]


class _ShipResult(enum.Enum):
    SHIPPED = "shipped"  # accepted by backend (2xx) — advance offset
    DROPPED = "dropped"  # permanent failure — advance offset
    ABORTED = "aborted"  # shutdown during retry — do NOT advance offset


class _Poll(enum.Enum):
    PROGRESSED = "progressed"
    IDLE = "idle"
    ABORTED = "aborted"


@dataclass
class _ShipperState:
    """Checkpoint stored next to the audit log tail."""

    offset: int
    st_ino: int | None = None
    st_dev: int | None = None


def _handle_term(_signum: int, _frame: FrameType | None) -> None:
    global _running
    _running = False


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _load_state(path: str) -> _ShipperState:
    """Load the checkpoint. A missing file is a normal first start.

    A corrupt file is logged and replayed from offset 0. Ingest deduplicates
    on ``producer_event_id``, so replaying is safer than skipping to EOF.
    An unreadable identity is dropped while a valid offset is kept.
    """

    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    except FileNotFoundError:
        return _ShipperState(offset=0)
    except OSError as error:
        logger.error(
            "corrupt shipper state path=%s reason=invalid_offset detail=%s",
            path,
            error,
        )
        return _ShipperState(offset=0)

    text = raw.strip()
    if not text:
        logger.error("corrupt shipper state path=%s reason=empty", path)
        return _ShipperState(offset=0)

    try:
        legacy = int(text, 10)
    except ValueError:
        legacy = None
    if legacy is not None:
        if legacy < 0:
            logger.error("corrupt shipper state path=%s reason=invalid_offset", path)
            return _ShipperState(offset=0)
        return _ShipperState(offset=legacy)

    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError:
        logger.error("corrupt shipper state path=%s reason=invalid_json", path)
        return _ShipperState(offset=0)

    data = _string_keyed_dict(parsed)
    if data is None:
        logger.error("corrupt shipper state path=%s reason=invalid_json", path)
        return _ShipperState(offset=0)

    if "offset" not in data:
        logger.error("corrupt shipper state path=%s reason=invalid_offset", path)
        return _ShipperState(offset=0)
    offset = _non_negative_int(data["offset"])
    if offset is None:
        logger.error("corrupt shipper state path=%s reason=invalid_offset", path)
        return _ShipperState(offset=0)

    identity = _identity_from_state(data)
    if identity is None:
        logger.warning(
            "ignoring invalid file identity in shipper state path=%s", path
        )
        return _ShipperState(offset=offset)
    return _ShipperState(offset=offset, st_ino=identity[0], st_dev=identity[1])


def _string_keyed_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return None
        result[key] = item
    return result


def _identity_from_state(
    data: dict[str, object],
) -> tuple[int | None, int | None] | None:
    """Return ``(ino, dev)`` or ``(None, None)`` when identity was not stored.

    Return ``None`` when a stored identity cannot be used.
    """

    has_ino = "st_ino" in data
    has_dev = "st_dev" in data
    if not has_ino and not has_dev:
        return (None, None)
    ino = _non_negative_int(data["st_ino"]) if has_ino else None
    dev = _non_negative_int(data["st_dev"]) if has_dev else None
    if ino is None or dev is None:
        return None
    return (ino, dev)


def _persist_state(path: str, state: _ShipperState) -> None:
    """Atomically replace the state file and fsync the file and its directory."""

    body: dict[str, int] = {"offset": state.offset}
    if state.st_ino is not None and state.st_dev is not None:
        body["st_ino"] = state.st_ino
        body["st_dev"] = state.st_dev
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(body, separators=(",", ":")))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    _fsync_directory(os.path.dirname(path) or ".")


def _fsync_directory(directory: str) -> None:
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        logger.warning(
            "failed to fsync shipper state directory path=%s", directory
        )
        return
    try:
        try:
            os.fsync(descriptor)
        except OSError:
            logger.warning(
                "failed to fsync shipper state directory path=%s", directory
            )
    finally:
        os.close(descriptor)


def _dead_letter_path(state_file: str) -> str:
    return f"{state_file}.deadletter"


def _append_dead_letter(state_file: str, reason: str, line: bytes) -> None:
    text = line.decode("utf-8", errors="replace")
    if len(text) > _DEAD_LETTER_LINE_CAP:
        text = text[:_DEAD_LETTER_LINE_CAP]
    record = json.dumps({"reason": reason, "line": text}, ensure_ascii=False)
    path = _dead_letter_path(state_file)
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(record + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(os.path.dirname(path) or ".")
    except OSError:
        logger.error(
            "failed to append dead-letter record path=%s reason=%s", path, reason
        )


def _note_drop(state_file: str, reason: str, line: bytes) -> None:
    global _dropped_total
    _append_dead_letter(state_file, reason, line)
    _dropped_total += 1
    logger.warning("dropped_total=%d reason=%s", _dropped_total, reason)


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
        return int(response.status)


def _ship_line(settings: Settings, line: bytes) -> _ShipResult:
    """Block until ``line`` is shipped, dropped, or the process is shutting down.

    A blank line is dropped without a dead-letter record. Every other permanent
    failure is dead-lettered before the caller advances the offset.
    """

    text = line.decode("utf-8", errors="replace").strip()
    if not text:
        return _ShipResult.DROPPED

    try:
        event = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("dropping unparseable audit line")
        _note_drop(settings.state_file, "unparseable", line)
        return _ShipResult.DROPPED
    if not isinstance(event, dict):
        logger.warning("dropping non-object audit line")
        _note_drop(settings.state_file, "non_object", line)
        return _ShipResult.DROPPED

    payload = coraza_event_to_ingest(event)
    if payload is None:
        logger.warning("dropping event that cannot be mapped to an ingest payload")
        _note_drop(settings.state_file, "unmappable", line)
        return _ShipResult.DROPPED

    backoff = settings.backoff_base_seconds
    while _running:
        try:
            status = _post_event(settings, payload)
            logger.info(
                "shipped event producer_event_id=%s status=%s",
                payload["producer_event_id"],
                status,
            )
            return _ShipResult.SHIPPED
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                # Auth rejection is a config error (wrong shared secret), not a
                # per-event poison pill. Stall with backoff so the pipeline pauses
                # rather than silently shredding the audit stream.
                logger.warning(
                    "ingest auth rejected (%s) — check LOG_INGEST_SHARED_SECRET; "
                    "retrying in %.1fs",
                    error.code,
                    backoff,
                )
            elif error.code == 429 or error.code >= 500:
                logger.warning("ingest %s, retrying in %.1fs", error.code, backoff)
            else:
                # Other 4xx (for example 422): this payload will keep failing.
                body = error.read().decode("utf-8", errors="replace")[:500]
                logger.error(
                    "dropping event rejected by ingest (%s): %s", error.code, body
                )
                _note_drop(settings.state_file, f"http_{error.code}", line)
                return _ShipResult.DROPPED
        except urllib.error.URLError as error:
            logger.warning(
                "ingest unreachable (%s), retrying in %.1fs", error.reason, backoff
            )
        except (TimeoutError, OSError) as error:
            # urlopen can raise socket.timeout / TimeoutError outside URLError.
            logger.warning(
                "ingest unreachable (%s), retrying in %.1fs", error, backoff
            )

        _interruptible_sleep(backoff)
        backoff = min(backoff * 2, settings.backoff_max_seconds)

    return _ShipResult.ABORTED


def _interruptible_sleep(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while _running and time.monotonic() < deadline:
        time.sleep(min(0.5, deadline - time.monotonic()))


def _consume_record(
    handle: BinaryIO, *, drain: bool
) -> tuple[_RecordKind, bytes] | None:
    """Read one audit record.

    Return ``None`` when the writer has not finished the line yet. In that case
    the file position is restored to the start of the record. ``drain`` means
    the file will not grow again, so a trailing partial line is consumed.
    """

    start = handle.tell()
    chunk = handle.readline(_MAX_LINE_BYTES)
    if not chunk:
        return None
    if chunk.endswith(b"\n"):
        return ("line", chunk)
    if len(chunk) < _MAX_LINE_BYTES:
        if drain:
            return ("truncated", chunk)
        handle.seek(start)
        return None

    while True:
        more = handle.readline(_MAX_LINE_BYTES)
        unfinished = not more or (
            not more.endswith(b"\n") and len(more) < _MAX_LINE_BYTES
        )
        if unfinished:
            if drain:
                return ("truncated", chunk)
            handle.seek(start)
            return None
        if more.endswith(b"\n"):
            return ("too_long", chunk)


def _ship_available(
    settings: Settings,
    handle: BinaryIO,
    state: _ShipperState,
    *,
    drain: bool,
) -> _Poll:
    """Ship records that are already available. Update ``state.offset``."""

    progressed = False
    while _running:
        handle.seek(state.offset)
        record = _consume_record(handle, drain=drain)
        if record is None:
            return _Poll.PROGRESSED if progressed else _Poll.IDLE
        kind, payload = record
        if kind == "line":
            result = _ship_line(settings, payload)
            if result is _ShipResult.ABORTED:
                handle.seek(state.offset)
                return _Poll.ABORTED
        elif kind == "too_long":
            _note_drop(settings.state_file, "line_too_long", payload)
        else:
            _note_drop(settings.state_file, "truncated_by_rotation", payload)
        state.offset = handle.tell()
        _persist_state(settings.state_file, state)
        progressed = True
    return _Poll.PROGRESSED if progressed else _Poll.ABORTED


def _state_for_opened_file(
    settings: Settings, state: _ShipperState, path_stat: os.stat_result
) -> _ShipperState:
    """Decide where to start reading a file that was not already open."""

    saved_identity = state.st_ino is not None and state.st_dev is not None
    same_file = (
        saved_identity
        and state.st_ino == path_stat.st_ino
        and state.st_dev == path_stat.st_dev
    )
    if saved_identity and not same_file:
        logger.error(
            "audit log identity changed while the shipper was stopped "
            "path=%s saved_ino=%s saved_dev=%s current_ino=%s current_dev=%s; "
            "starting at offset 0",
            settings.audit_log_path,
            state.st_ino,
            state.st_dev,
            path_stat.st_ino,
            path_stat.st_dev,
        )
        fresh = _ShipperState(
            offset=0, st_ino=path_stat.st_ino, st_dev=path_stat.st_dev
        )
        _persist_state(settings.state_file, fresh)
        return fresh

    if path_stat.st_size < state.offset:
        logger.warning("audit log truncated; resetting offset to 0")
        fresh = _ShipperState(
            offset=0, st_ino=path_stat.st_ino, st_dev=path_stat.st_dev
        )
        _persist_state(settings.state_file, fresh)
        return fresh

    if not same_file:
        # Legacy offset-only state. The file is long enough to keep the offset.
        adopted = _ShipperState(
            offset=state.offset, st_ino=path_stat.st_ino, st_dev=path_stat.st_dev
        )
        _persist_state(settings.state_file, adopted)
        return adopted
    return state


def run(settings: Settings) -> None:
    global _dropped_total
    _dropped_total = 0
    logger.info("log shipper starting; tailing %s", settings.audit_log_path)
    state = _load_state(settings.state_file)
    handle: BinaryIO | None = None
    try:
        while _running:
            try:
                path_stat = os.stat(settings.audit_log_path)
            except FileNotFoundError:
                _interruptible_sleep(settings.poll_interval_seconds)
                continue

            if handle is None:
                state = _state_for_opened_file(settings, state, path_stat)
                handle = open(settings.audit_log_path, "rb")
            else:
                open_stat = os.fstat(handle.fileno())
                rotated = (
                    path_stat.st_ino != open_stat.st_ino
                    or path_stat.st_dev != open_stat.st_dev
                )
                if rotated:
                    logger.warning(
                        "audit log rotated; draining the previous file "
                        "ino=%s dev=%s",
                        open_stat.st_ino,
                        open_stat.st_dev,
                    )
                    outcome = _ship_available(settings, handle, state, drain=True)
                    handle.close()
                    handle = None
                    if outcome is _Poll.ABORTED:
                        logger.error(
                            "stopping during rotation drain; bytes left in the "
                            "rotated file will not be retried because it is no "
                            "longer at the audit log path"
                        )
                        break
                    state = _ShipperState(
                        offset=0,
                        st_ino=path_stat.st_ino,
                        st_dev=path_stat.st_dev,
                    )
                    _persist_state(settings.state_file, state)
                    continue
                if path_stat.st_size < state.offset:
                    logger.warning("audit log truncated; resetting offset to 0")
                    state = _ShipperState(
                        offset=0,
                        st_ino=open_stat.st_ino,
                        st_dev=open_stat.st_dev,
                    )
                    _persist_state(settings.state_file, state)

            outcome = _ship_available(settings, handle, state, drain=False)
            if outcome is _Poll.ABORTED:
                break
            if outcome is _Poll.IDLE:
                _interruptible_sleep(settings.poll_interval_seconds)
    finally:
        if handle is not None:
            handle.close()
    logger.info("log shipper stopped at offset %d", state.offset)


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
