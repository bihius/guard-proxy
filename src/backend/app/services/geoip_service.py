"""GeoIP database download and HAProxy map generation (issue #175).

Pipeline: ip66.dev country-level MMDB -> generated HAProxy map file
(CIDR -> ISO 3166-1 alpha-2) -> `map_ip()` ACLs in haproxy.cfg.j2. This keeps
country lookups native to HAProxy — no Lua, no HAProxy MMDB module — because
the backend already owns the runtime config generation pipeline.

The database is downloaded from ip66.dev (https://ip66.dev), a free,
no-registration MMDB source licensed under CC BY 4.0 and rebuilt daily
upstream. Attribution: GeoIP data provided by ip66.dev, licensed CC BY 4.0.

Both the MMDB and the generated map file live on the shared
`generated_config` volume, next to (but outside of) the versioned
`releases/<id>/` directories used by config_apply, because the GeoIP data is
refreshed on its own daily schedule independent of config applies:

    <runtime_root>/geoip/country.mmdb
    <runtime_root>/geoip/country.map

The backend reaches this path via `settings.runtime_generated_config_root`;
HAProxy reads the same file through its `/etc/haproxy/generated` mount (see
`app.services.config_generator.HAPROXY_GEOIP_MAP_PATH`).
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import os
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, cast

import httpx
import maxminddb

from app.config import settings
from app.constants.countries import MAPPABLE_COUNTRY_CODES

logger = logging.getLogger(__name__)

# Serialises refreshes across the scheduled job and the API endpoint. Both go
# through the same fixed temp paths, so this is what stops them from
# clobbering each other's partial writes.
_refresh_lock = threading.Lock()

_STUB_HEADER = (
    "# Guard Proxy GeoIP map (CIDR -> ISO 3166-1 alpha-2).\n"
    "# Regenerated from the ip66.dev country database; manual edits are\n"
    "# overwritten. GeoIP data provided by https://ip66.dev, licensed CC BY 4.0.\n"
)
# RFC 5737 TEST-NET-1, never routed — keeps the file non-empty so HAProxy
# always parses it even before any real ip66.dev data has been downloaded.
_STUB_SENTINEL = "192.0.2.0/24 ZZ\n"

_MMDB_FILENAME = "country.mmdb"
_MAP_FILENAME = "country.map"
_META_FILENAME = "country.mmdb.meta.json"

# Iterating the database MUST go through maxminddb's C extension. The pure
# Python reader (MODE_MEMORY / MODE_FILE) raises
# "ValueError: ::1:0:0/0 has host bits set" partway through the real ip66.dev
# database while rebuilding IPv6 networks from the search tree, so it cannot
# enumerate this database at all. MODE_AUTO picks the extension when it is
# available; `generate_map_file()` turns the fallback's failure into an
# actionable GeoipError rather than an opaque crash.
_READER_MODE = maxminddb.MODE_AUTO

_STUB_BYTES = len((_STUB_HEADER + _STUB_SENTINEL).encode("utf-8"))

# The upstream database uses a few codes that are not ISO 3166-1 alpha-2
# assignments. "UK" is just the wrong spelling of "GB" (11 networks in the
# July 2026 build) and is aliased so blocking GB also covers them. Everything
# else is left unresolved on purpose and therefore fails open: "EU" (~90k
# networks) marks Europe-wide allocations with no single country, "XK" is the
# user-assigned code for Kosovo, and CS/YU/AN are withdrawn codes.
_COUNTRY_ALIASES = {"UK": "GB"}


class GeoipError(Exception):
    """Base class for GeoIP service errors."""


@dataclass(frozen=True)
class GeoipRefreshResult:
    """Outcome of one `refresh()` run."""

    downloaded: bool
    entries: int
    changed: bool
    reloaded: bool
    message: str


def geoip_dir() -> Path:
    """Directory holding the MMDB and generated map, on the runtime volume."""
    return Path(settings.runtime_generated_config_root) / "geoip"


def mmdb_path() -> Path:
    """Path to the downloaded ip66.dev country MMDB."""
    return geoip_dir() / _MMDB_FILENAME


def map_file_path() -> Path:
    """Path to the generated HAProxy CIDR -> country map."""
    return geoip_dir() / _MAP_FILENAME


def _meta_path() -> Path:
    """Path to the sidecar file storing the last ETag / Last-Modified."""
    return geoip_dir() / _META_FILENAME


def _map_is_stub() -> bool:
    """True when the map on disk is missing or still the placeholder stub.

    Used so a "not modified" download does not leave a stub map in place: the
    MMDB can be current while the map is not (first boot after an upgrade, a
    wiped volume, or a map generation that failed last time). The size check
    short-circuits the common case so a real ~20 MB map is never read back.
    """
    path = map_file_path()
    try:
        if path.stat().st_size != _STUB_BYTES:
            return False
        return path.read_text(encoding="utf-8") == _STUB_HEADER + _STUB_SENTINEL
    except OSError:
        return True


def ensure_map_file_exists() -> Path:
    """Guarantee `country.map` exists so HAProxy always has something to parse.

    Idempotent and cheap: does nothing when the map already exists. Writes a
    non-empty stub (all lookups miss -> fail open) when it does not. This is
    the mechanism that guarantees `haproxy -c` never fails on a missing map
    path, e.g. right after upgrading an existing deployment into this feature.
    """
    directory = geoip_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = map_file_path()
    if not path.exists():
        path.write_text(_STUB_HEADER + _STUB_SENTINEL, encoding="utf-8")
        logger.warning(
            "geoip map file missing; wrote empty stub "
            "(all lookups will miss -> fail open)"
        )
    return path


def _load_conditional_headers() -> dict[str, str]:
    """Build If-None-Match / If-Modified-Since headers from the sidecar file."""
    path = _meta_path()
    if not path.exists():
        return {}
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    headers: dict[str, str] = {}
    etag = meta.get("etag")
    if isinstance(etag, str) and etag:
        headers["If-None-Match"] = etag
    last_modified = meta.get("last_modified")
    if isinstance(last_modified, str) and last_modified:
        headers["If-Modified-Since"] = last_modified
    return headers


def _store_conditional_headers(response: httpx.Response) -> None:
    """Persist the ETag / Last-Modified validators next to the MMDB."""
    meta = {
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
    }
    _meta_path().write_text(json.dumps(meta), encoding="utf-8")


def download_database() -> tuple[Path, bool]:
    """Download the ip66.dev country MMDB, if it changed.

    Issues a conditional GET using the stored ETag/Last-Modified validators
    from the previous download. Returns `(path, downloaded)` where
    `downloaded` is False when the server replied 304 Not Modified (or when
    no download has ever run and one just succeeded, `downloaded` is True).
    """
    directory = geoip_dir()
    directory.mkdir(parents=True, exist_ok=True)
    tmp_mmdb = directory / f".{_MMDB_FILENAME}.tmp"

    headers = _load_conditional_headers() if mmdb_path().exists() else {}

    logger.info("downloading GeoIP database from %s", settings.geoip_database_url)
    try:
        with httpx.stream(
            "GET",
            settings.geoip_database_url,
            headers=headers,
            timeout=60.0,
            follow_redirects=True,
        ) as response:
            if response.status_code == 304:
                logger.info("GeoIP database not modified since last download")
                return mmdb_path(), False

            response.raise_for_status()

            with tmp_mmdb.open("wb") as out:
                for chunk in response.iter_bytes(65536):
                    out.write(chunk)

            os.replace(tmp_mmdb, mmdb_path())
            _store_conditional_headers(response)
    finally:
        tmp_mmdb.unlink(missing_ok=True)

    return mmdb_path(), True


_Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def _write_run(out: TextIO, networks: list[_Network], code: str | None) -> int:
    """Collapse one same-country run and write it out. Returns lines written.

    A run is homogeneous by construction — the caller starts a new one
    whenever the country code or the IP version changes — which both satisfies
    `collapse_addresses()` (it rejects mixed families) and lets the two
    branches below narrow the element type for the type checker.
    """
    if not networks or code is None:
        return 0

    collapsed: Iterator[_Network]
    if networks[0].version == 4:
        collapsed = ipaddress.collapse_addresses(
            cast("list[ipaddress.IPv4Network]", networks)
        )
    else:
        collapsed = ipaddress.collapse_addresses(
            cast("list[ipaddress.IPv6Network]", networks)
        )

    written = 0
    for network in collapsed:
        out.write(f"{network} {code}\n")
        written += 1
    return written


def generate_map_file(mmdb: Path | None = None) -> int:
    """Regenerate the HAProxy map file from the MMDB. Returns entries written.

    Atomic (write to a temp file, then `os.replace()`), so HAProxy can keep
    reading the previous map file while this runs.

    The upstream database splits blocks by ASN as well as by country, so
    adjacent networks are merged with `ipaddress.collapse_addresses()` before
    writing — that cuts roughly 1.3M raw networks down to ~1.0M lines.

    The merge is done per *run* of consecutive same-country, same-version
    networks rather than by first grouping every network by country. Both
    produce identical output, because `collapse_addresses()` can only merge
    networks that are adjacent in address space and the reader yields networks
    in ascending address order — so any two mergeable networks are always in
    the same run. Streaming this way keeps peak memory flat (one run at a
    time); buffering all networks first cost ~780 MB on the real database,
    which would not fit the backend container.

    Note `collapse_addresses()` raises `TypeError` when IPv4 and IPv6 networks
    are mixed in one call, which is why the IP version also breaks a run.
    """
    path = mmdb if mmdb is not None else mmdb_path()
    if not path.exists():
        logger.warning("GeoIP database %s is missing; cannot generate map", path)
        ensure_map_file_exists()
        return 0

    directory = geoip_dir()
    directory.mkdir(parents=True, exist_ok=True)
    tmp_map = directory / f".{_MAP_FILENAME}.tmp"

    entries = 0
    skipped = 0
    run: list[_Network] = []
    run_code: str | None = None
    run_version: int | None = None

    try:
        with (
            maxminddb.open_database(str(path), _READER_MODE) as reader,
            tmp_map.open("w", encoding="utf-8") as out,
        ):
            out.write(_STUB_HEADER)
            for network, record in reader:
                code = _country_code(record)
                if code is None or code not in MAPPABLE_COUNTRY_CODES:
                    skipped += 1
                    continue
                if code != run_code or network.version != run_version:
                    entries += _write_run(out, run, run_code)
                    run = []
                    run_code = code
                    run_version = network.version
                run.append(network)
            entries += _write_run(out, run, run_code)
    except ValueError as error:
        # The pure Python maxminddb reader cannot enumerate this database (see
        # _READER_MODE). Surface it as an actionable error instead of letting a
        # bare ValueError escape as a "GeoIP refresh failed" mystery.
        tmp_map.unlink(missing_ok=True)
        raise GeoipError(
            "Could not enumerate the GeoIP database. This happens when the "
            "maxminddb C extension is unavailable and the pure Python reader "
            "is used as a fallback; install a maxminddb build with the "
            f"extension. Underlying error: {error}"
        ) from error

    os.replace(tmp_map, map_file_path())
    if skipped:
        logger.warning(
            "geoip map generation skipped %d entries with no country code", skipped
        )
    return entries


def _country_code(record: object) -> str | None:
    if not isinstance(record, dict):
        return None
    country = record.get("country")
    if isinstance(country, dict):
        code = country.get("iso_code")
        if isinstance(code, str) and code:
            return _COUNTRY_ALIASES.get(code, code)
    registered = record.get("registered_country")
    if isinstance(registered, dict):
        code = registered.get("iso_code")
        if isinstance(code, str) and code:
            return _COUNTRY_ALIASES.get(code, code)
    return None


def _failed_refresh(error: Exception) -> GeoipRefreshResult:
    return GeoipRefreshResult(
        downloaded=False,
        entries=0,
        changed=False,
        reloaded=False,
        message=f"GeoIP refresh failed: {error}",
    )


def try_refresh(force_reload: bool = True) -> GeoipRefreshResult | None:
    """`refresh()` that gives up instead of waiting. Returns None when busy.

    Used by the API endpoint so an admin gets an immediate 409 rather than
    blocking on a refresh the scheduler already started.
    """
    if not _refresh_lock.acquire(blocking=False):
        return None
    try:
        return _refresh_locked(force_reload)
    finally:
        _refresh_lock.release()


def refresh(force_reload: bool = True) -> GeoipRefreshResult:
    """Refresh the GeoIP database and regenerate the HAProxy map.

    Single entry point shared by the scheduled daily job and the manual
    `POST /geoip/refresh` endpoint. Never raises — network, filesystem and
    malformed-database errors are all converted into a failed
    GeoipRefreshResult so a bad refresh cannot crash the scheduler.

    Serialised on a module-level lock. Both callers write to the same fixed
    temp paths (`.country.mmdb.tmp`, `.country.map.tmp`), so two concurrent
    refreshes would interleave writes and each `finally: unlink()` would
    delete the other's temp file before its `os.replace()` — publishing a
    corrupt map into a live security filter.
    """
    with _refresh_lock:
        return _refresh_locked(force_reload)


def _refresh_locked(force_reload: bool) -> GeoipRefreshResult:
    ensure_map_file_exists()

    before_digest = _map_digest()

    try:
        _mmdb, downloaded = download_database()
    except (httpx.HTTPError, OSError, GeoipError) as error:
        logger.exception("GeoIP refresh failed")
        return _failed_refresh(error)

    try:
        # Regenerate when the database changed, but also whenever the map is
        # still a stub — otherwise a 304 would report "up to date" while every
        # lookup misses and the filter silently fails open.
        regenerate = downloaded or _map_is_stub()
        entries = generate_map_file() if regenerate else 0
    except (OSError, GeoipError, maxminddb.InvalidDatabaseError) as error:
        # The file on disk is not a usable database — a mirror answering 200
        # with an HTML error page is the common case, and raise_for_status()
        # cannot catch that. Its ETag/Last-Modified were already recorded by
        # the successful download above, so leaving them would make every
        # later refresh a 304 and the corruption permanent. Dropping the
        # validators forces the next run to fetch in full.
        # InvalidDatabaseError subclasses RuntimeError, so neither OSError nor
        # GeoipError would catch it on their own.
        _meta_path().unlink(missing_ok=True)
        logger.exception("GeoIP refresh failed; dropped cache validators")
        return _failed_refresh(error)

    after_digest = _map_digest()
    changed = before_digest != after_digest

    reloaded = False
    if changed and force_reload:
        # Map files are only re-read on reload; the Runtime API `set map`
        # command does not persist and would drift from disk, so a real
        # reload is required.
        from app.services.config_apply import reload_haproxy

        reload_result = reload_haproxy()
        reloaded = reload_result.ok
        if not reload_result.ok:
            logger.warning(
                "GeoIP map changed but HAProxy reload failed: %s",
                reload_result.output,
            )

    message = (
        f"GeoIP database refreshed: {entries} entries written."
        if regenerate
        else "GeoIP database is already up to date."
    )
    return GeoipRefreshResult(
        downloaded=downloaded,
        entries=entries,
        changed=changed,
        reloaded=reloaded,
        message=message,
    )


def _map_digest() -> str | None:
    """Hash the map file, streamed so an ~18 MB map is never held in memory."""
    path = map_file_path()
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
