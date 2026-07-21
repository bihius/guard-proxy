"""Ban-list service — reads/clears auto-ban entries via HAProxy Runtime API.

Talks to the admin-level stats socket (`settings.haproxy_stats_socket_path`)
emitted in the generated `haproxy.cfg` (see #275, #276). Each vhost with
DDoS protection and auto-ban enabled owns a stick-table named
`st_ban_vhost_<id>` (see `config_generator.py::_to_haproxy_context`); this
module enumerates those tables' contents and can clear entries from them.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from dataclasses import dataclass

from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models.vhost import VHost
from app.schemas.security import BannedIpResponse, UnbanResponse

logger = logging.getLogger(__name__)

_TABLE_ENTRY_RE = re.compile(
    r"key=(?P<key>\S+).*?exp=(?P<exp>\d+).*?gpc0=(?P<gpc0>\d+)"
)

# HAProxy's Runtime API reports failures (unknown table, permission denied,
# unsupported command, ...) as plain text in the command's own response
# rather than as a socket-level error, so a successful `recv()` does not
# mean the command succeeded. Anchored to the start of a line, mirroring
# `config_apply._RELOAD_ERROR_RE`, so a `key=...` data line or the
# `# table: ...` header can never false-positive.
_RUNTIME_API_ERROR_RE = re.compile(
    r"^\s*(unknown|no such|can't find|permission denied|invalid|error)\b",
    re.IGNORECASE | re.MULTILINE,
)


class BanListError(Exception):
    """Base class for ban-list domain errors."""


class InvalidIpError(BanListError):
    """Raised when a supplied IP address string cannot be parsed."""

    def __init__(self, ip: str) -> None:
        self.ip = ip
        super().__init__(f"'{ip}' is not a valid IP address")


class RuntimeApiError(BanListError):
    """Raised when the HAProxy Runtime API socket cannot be reached at all."""


@dataclass(frozen=True)
class BanTableEntry:
    """One parsed row from a `show table` response."""

    ip: str
    gpc0: int
    expires_in_seconds: int


def _send_runtime_command(command: str) -> str:
    """Send one Runtime API command over the admin stats socket and return output.

    Raises `RuntimeApiError` both when the socket itself is unreachable and
    when HAProxy accepts the connection but replies with an error message
    (e.g. an unknown table) — the caller cannot otherwise tell a successful
    `clear`/`show` from one HAProxy silently rejected.
    """
    socket_path = settings.haproxy_stats_socket_path
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(settings.haproxy_stats_timeout_seconds)
            client.connect(socket_path)
            client.sendall(command.encode("utf-8") + b"\n")
            client.shutdown(socket.SHUT_WR)
            output_chunks: list[bytes] = []
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                output_chunks.append(chunk)
    except OSError as error:
        raise RuntimeApiError(str(error)) from error

    output = b"".join(output_chunks).decode("utf-8", errors="replace")
    if _RUNTIME_API_ERROR_RE.search(output):
        raise RuntimeApiError(output.strip() or "HAProxy Runtime API returned an error")

    return output


def _parse_show_table(raw: str) -> list[BanTableEntry]:
    """Parse `show table <name>` output into structured entries.

    Example line:
        0x...: key=192.0.2.7 use=0 exp=540000 gpc0=15
    `exp` is milliseconds remaining; converted to whole seconds (rounded up
    so a live entry never reports 0 remaining).
    """
    entries: list[BanTableEntry] = []
    for line in raw.splitlines():
        match = _TABLE_ENTRY_RE.search(line)
        if match is None:
            continue
        exp_ms = int(match.group("exp"))
        entries.append(
            BanTableEntry(
                ip=match.group("key"),
                gpc0=int(match.group("gpc0")),
                expires_in_seconds=(exp_ms + 999) // 1000,
            )
        )
    return entries


class BanListService:
    """Reads and clears auto-ban stick-table entries via the Runtime API."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_banned(self) -> list[BannedIpResponse]:
        """Return every tracked/banned entry across all auto-ban-enabled vhosts.

        Tolerates individual table failures (one dead table must not blank
        the whole list) but raises `RuntimeApiError` if every attempted
        table failed, so a fully unreachable Runtime API surfaces as an
        error instead of an empty list indistinguishable from "nothing
        tracked" — mirroring `unban`'s all-tables-failed handling below.
        """
        tables = self._active_ban_tables()
        results: list[BannedIpResponse] = []
        failures = 0
        for vhost, table_name, ban_threshold in tables:
            try:
                raw = _send_runtime_command(f"show table {table_name}")
                entries = _parse_show_table(raw)
            except RuntimeApiError:
                logger.exception(
                    "ban-list failed to read table %s for vhost %s",
                    table_name,
                    vhost.id,
                )
                failures += 1
                continue

            for entry in entries:
                results.append(
                    BannedIpResponse(
                        ip=entry.ip,
                        vhost_id=vhost.id,
                        domain=vhost.domain,
                        gpc0=entry.gpc0,
                        ban_threshold=ban_threshold,
                        banned=entry.gpc0 > ban_threshold,
                        expires_in_seconds=entry.expires_in_seconds,
                    )
                )

        if tables and failures == len(tables):
            raise RuntimeApiError("Failed to reach HAProxy Runtime API")

        return results

    def unban(self, ip: str) -> UnbanResponse:
        """Clear an IP from every active ban table; return the number cleared.

        `cleared` counts tables where HAProxy confirmed the `clear table`
        command (including a no-op when the key was already absent) — not
        merely tables where the socket write succeeded, since
        `_send_runtime_command` raises on an HAProxy-reported error too.
        Tolerates individual table failures (one dead table must not block
        clearing the others) but raises `RuntimeApiError` if every attempted
        table failed, so a fully unreachable Runtime API surfaces as an
        error instead of a silent no-op `cleared=0`.
        """
        try:
            ipaddress.ip_address(ip)
        except ValueError as error:
            raise InvalidIpError(ip) from error

        tables = self._active_ban_tables()
        cleared = 0
        failures = 0
        for _vhost, table_name, _threshold in tables:
            try:
                _send_runtime_command(f"clear table {table_name} key {ip}")
                cleared += 1
            except RuntimeApiError:
                logger.exception(
                    "ban-list failed to clear key %s in table %s", ip, table_name
                )
                failures += 1

        if tables and failures == len(tables):
            raise RuntimeApiError("Failed to reach HAProxy Runtime API")

        return UnbanResponse(ip=ip, cleared=cleared)

    def _active_ban_tables(self) -> list[tuple[VHost, str, int]]:
        vhosts = (
            self.db.query(VHost)
            .options(selectinload(VHost.policy))
            .order_by(VHost.id.asc())
            .all()
        )
        return [
            (vhost, f"st_ban_vhost_{vhost.id}", vhost.policy.ban_threshold)
            for vhost in vhosts
            if vhost.is_active
            and vhost.policy is not None
            and vhost.policy.ddos_protection_enabled
            and vhost.policy.auto_ban_enabled
        ]
