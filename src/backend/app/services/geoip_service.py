"""GeoIP database download and HAProxy map generation (issue #175).

Pipeline: MaxMind GeoLite2-Country (MMDB) -> generated HAProxy map file
(CIDR -> ISO 3166-1 alpha-2) -> `map_ip()` ACLs in haproxy.cfg.j2. This keeps
country lookups native to HAProxy — no Lua, no HAProxy MMDB module — because
the backend already owns the runtime config generation pipeline.

Both the MMDB and the generated map file live on the shared
`generated_config` volume, next to (but outside of) the versioned
`releases/<id>/` directories used by config_apply, because the GeoIP data is
refreshed on its own weekly schedule independent of config applies:

    <runtime_root>/geoip/GeoLite2-Country.mmdb
    <runtime_root>/geoip/country.map

The backend reaches this path via `settings.runtime_generated_config_root`;
HAProxy reads the same file through its `/etc/haproxy/generated` mount (see
`app.services.config_generator.HAPROXY_GEOIP_MAP_PATH`).
"""

from __future__ import annotations

import hashlib
import logging
import os
import tarfile
from dataclasses import dataclass
from pathlib import Path

import httpx
import maxminddb

from app.config import settings
from app.constants.countries import VALID_COUNTRY_CODES

logger = logging.getLogger(__name__)

_DOWNLOAD_URL = "https://download.maxmind.com/app/geoip_download"
_EDITION_ID = "GeoLite2-Country"

_STUB_HEADER = (
    "# Guard Proxy GeoIP map (CIDR -> ISO 3166-1 alpha-2).\n"
    "# Regenerated from GeoLite2-Country; manual edits are overwritten.\n"
)
# RFC 5737 TEST-NET-1, never routed — keeps the file non-empty so HAProxy
# always parses it even before any real GeoLite2 data has been downloaded.
_STUB_SENTINEL = "192.0.2.0/24 ZZ\n"

_MMDB_FILENAME = "GeoLite2-Country.mmdb"
_MAP_FILENAME = "country.map"


class GeoipError(Exception):
    """Base class for GeoIP service errors."""


class GeoipNotConfiguredError(GeoipError):
    """Raised when a MaxMind license key has not been configured."""


@dataclass(frozen=True)
class GeoipRefreshResult:
    """Outcome of one `refresh()` run."""

    configured: bool
    downloaded: bool
    entries: int
    changed: bool
    reloaded: bool
    message: str


def geoip_dir() -> Path:
    """Directory holding the MMDB and generated map, on the runtime volume."""
    return Path(settings.runtime_generated_config_root) / "geoip"


def mmdb_path() -> Path:
    """Path to the downloaded GeoLite2-Country database."""
    return geoip_dir() / _MMDB_FILENAME


def map_file_path() -> Path:
    """Path to the generated HAProxy CIDR -> country map."""
    return geoip_dir() / _MAP_FILENAME


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


def download_database() -> Path:
    """Download and extract the GeoLite2-Country MMDB.

    No-op (returning the existing path, or raising GeoipNotConfiguredError if
    none exists yet) when no license key is configured.
    """
    if not settings.maxmind_license_key:
        logger.warning(
            "MAXMIND_LICENSE_KEY is not configured; skipping GeoIP database download"
        )
        path = mmdb_path()
        if path.exists():
            return path
        raise GeoipNotConfiguredError(
            "MAXMIND_LICENSE_KEY is not configured and no database "
            "has been downloaded yet"
        )

    directory = geoip_dir()
    directory.mkdir(parents=True, exist_ok=True)
    tarball_path = directory / f".{_EDITION_ID}.tar.gz.tmp"

    try:
        # Never log params (they contain the license key) — only the URL.
        logger.info("downloading GeoIP database from %s", _DOWNLOAD_URL)
        response = httpx.get(
            _DOWNLOAD_URL,
            params={
                "edition_id": _EDITION_ID,
                "license_key": settings.maxmind_license_key,
                "suffix": "tar.gz",
            },
            timeout=60.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        tarball_path.write_bytes(response.content)

        with tarfile.open(tarball_path, "r:gz") as archive:
            member = next(
                (m for m in archive.getmembers() if m.name.endswith(_MMDB_FILENAME)),
                None,
            )
            if member is None:
                raise GeoipError(
                    f"{_MMDB_FILENAME} not found inside downloaded archive"
                )
            extracted = archive.extractfile(member)
            if extracted is None:
                raise GeoipError(f"Could not read {_MMDB_FILENAME} from archive")

            tmp_mmdb = directory / f".{_MMDB_FILENAME}.tmp"
            with tmp_mmdb.open("wb") as out:
                while chunk := extracted.read(65536):
                    out.write(chunk)
            os.replace(tmp_mmdb, mmdb_path())
    finally:
        tarball_path.unlink(missing_ok=True)

    return mmdb_path()


def generate_map_file(mmdb: Path | None = None) -> int:
    """Regenerate the HAProxy map file from the MMDB. Returns entries written.

    Atomic (write to a temp file, then `os.replace()`), so HAProxy can keep
    reading the previous map file while this runs.
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
    with maxminddb.open_database(str(path), maxminddb.MODE_MEMORY) as reader:
        with tmp_map.open("w", encoding="utf-8") as out:
            out.write(_STUB_HEADER)
            for network, record in reader:
                code = _country_code(record)
                if code is None or code not in VALID_COUNTRY_CODES:
                    skipped += 1
                    continue
                out.write(f"{network} {code}\n")
                entries += 1

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
            return code
    registered = record.get("registered_country")
    if isinstance(registered, dict):
        code = registered.get("iso_code")
        if isinstance(code, str) and code:
            return code
    return None


def refresh(force_reload: bool = True) -> GeoipRefreshResult:
    """Refresh the GeoIP database and regenerate the HAProxy map.

    Single entry point shared by the scheduled weekly job and the manual
    `POST /geoip/refresh` endpoint. Never raises — network, filesystem, and
    archive errors are all converted into a failed GeoipRefreshResult so a
    bad refresh cannot crash the scheduler.
    """
    ensure_map_file_exists()

    if not settings.maxmind_license_key:
        return GeoipRefreshResult(
            configured=False,
            downloaded=False,
            entries=0,
            changed=False,
            reloaded=False,
            message=(
                "MAXMIND_LICENSE_KEY is not configured; "
                "GeoIP filtering fails open."
            ),
        )

    before_digest = _map_digest()

    try:
        download_database()
        entries = generate_map_file()
    except (httpx.HTTPError, OSError, tarfile.TarError, GeoipError) as error:
        logger.exception("GeoIP refresh failed")
        return GeoipRefreshResult(
            configured=True,
            downloaded=False,
            entries=0,
            changed=False,
            reloaded=False,
            message=f"GeoIP refresh failed: {error}",
        )

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

    return GeoipRefreshResult(
        configured=True,
        downloaded=True,
        entries=entries,
        changed=changed,
        reloaded=reloaded,
        message=f"GeoIP database refreshed: {entries} entries written.",
    )


def _map_digest() -> str | None:
    path = map_file_path()
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()
