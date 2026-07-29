import shutil
import subprocess
from pathlib import Path

import pytest

from app.constants.countries import VALID_COUNTRY_CODES
from app.services.config_renderer import (
    HaproxyBackend,
    HaproxyDdos,
    HaproxyGeoip,
    HaproxyRenderContext,
    HaproxyRoute,
    HaproxyServer,
    render_haproxy_cfg,
)


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate

    raise FileNotFoundError(
        f"Could not locate repository root from {start}; expected .git directory"
    )


REPO_ROOT = _find_repo_root(Path(__file__).resolve().parent)


def _normalise_config(config: str) -> str:
    return "\n".join(line.rstrip() for line in config.splitlines() if line.strip())


def _backend(
    name: str = "be",
    server_name: str = "srv",
    address: str = "host:80",
) -> HaproxyBackend:
    return HaproxyBackend(
        name=name,
        servers=(HaproxyServer(server_name=server_name, address=address),),
    )


def _m1_reference_context() -> HaproxyRenderContext:
    return HaproxyRenderContext(
        routes=(
            HaproxyRoute(
                vhost_acl_name="host_app",
                vhost_hosts=("app.local", "localhost", "127.0.0.1"),
                ssl_provider="none",
                backend=_backend("be_app", "app", "backend:8000"),
            ),
        )
    )


def test_haproxy_template_renders_m1_reference_modulo_whitespace() -> None:
    rendered = render_haproxy_cfg(_m1_reference_context())
    reference = (REPO_ROOT / "configs/haproxy/haproxy.cfg").read_text()

    assert _normalise_config(rendered) == _normalise_config(reference)


def test_haproxy_template_renders_admin_stats_socket_for_runtime_api() -> None:
    rendered = render_haproxy_cfg(_m1_reference_context())

    assert "stats socket /tmp/haproxy.sock mode 660 level operator" in rendered
    assert "stats socket /var/run/haproxy/admin.sock mode 666 level admin" in rendered


def test_haproxy_template_parameterises_vhost_and_backend() -> None:
    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_api",
                    vhost_hosts=("api.example.com",),
                ssl_provider="none",
                    backend=_backend("be_api", "api", "api-backend:9000"),
                ),
            ),
        )
    )

    assert "acl host_api hdr(host),field(1,:) -i api.example.com" in rendered
    assert "http-request deny deny_status 421 if !host_api" in rendered
    assert "use_backend be_api if host_api" in rendered
    # Unknown hosts are denied with 421 before backend selection, so the
    # generated config must not contain an unreachable default_backend.
    assert "default_backend" not in rendered
    assert "server api api-backend:9000 check" in rendered


def test_haproxy_template_renders_multiple_vhost_routes() -> None:
    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_vhost_1",
                    vhost_hosts=("foo-bar.com",),
                ssl_provider="none",
                    backend=_backend("be_vhost_1", "srv_vhost_1", "foo-backend:8000"),
                ),
                HaproxyRoute(
                    vhost_acl_name="host_vhost_2",
                    vhost_hosts=("foo.bar.com",),
                ssl_provider="none",
                    backend=_backend("be_vhost_2", "srv_vhost_2", "bar-backend:8000"),
                ),
            )
        )
    )

    assert "acl host_vhost_1 hdr(host),field(1,:) -i foo-bar.com" in rendered
    assert "acl host_vhost_2 hdr(host),field(1,:) -i foo.bar.com" in rendered
    assert (
        "http-request deny deny_status 421 if !host_vhost_1 !host_vhost_2"
        in rendered
    )
    assert "use_backend be_vhost_1 if host_vhost_1" in rendered
    assert "use_backend be_vhost_2 if host_vhost_2" in rendered
    assert "backend be_vhost_1" in rendered
    assert "backend be_vhost_2" in rendered


@pytest.mark.parametrize(
    "vhost_acl_name",
    [
        "has space",
        "has\nnewline",
        "has\ttab",
        "has#comment",
        "has;semi",
        "has{brace",
    ],
)
def test_haproxy_render_context_rejects_unsafe_acl_name(vhost_acl_name: str) -> None:
    with pytest.raises(ValueError, match="vhost_acl_name"):
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name=vhost_acl_name,
                    vhost_hosts=("safe.host",),
                ssl_provider="none",
                    backend=_backend(),
                ),
            )
        )


@pytest.mark.parametrize(
    "host",
    [
        "has space",
        "has\nnewline",
        "has\ttab",
        "has#comment",
        "has;semi",
        "safe.host:8080",
    ],
)
def test_haproxy_render_context_rejects_unsafe_host(host: str) -> None:
    with pytest.raises(ValueError, match="HaproxyRenderContext.vhost_hosts"):
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="safe_acl",
                    vhost_hosts=(host,),
                ssl_provider="none",
                    backend=_backend(),
                ),
            )
        )


@pytest.mark.parametrize(
    "field,kwargs",
    [
        ("name", {"name": "has space", "server_name": "srv", "address": "host:80"}),
        ("name", {"name": "has\nnewline", "server_name": "srv", "address": "host:80"}),
        (
            "server_name",
            {"name": "be", "server_name": "has space", "address": "host:80"},
        ),
        (
            "server_name",
            {"name": "be", "server_name": "has\nnewline", "address": "host:80"},
        ),
        ("address", {"name": "be", "server_name": "srv", "address": "has space"}),
        ("address", {"name": "be", "server_name": "srv", "address": "has\nnewline"}),
    ],
)
def test_haproxy_backend_rejects_unsafe_values(field: str, kwargs: dict) -> None:
    if field == "name":
        with pytest.raises(ValueError, match="HaproxyBackend"):
            _backend(name=kwargs["name"])
    else:
        with pytest.raises(ValueError, match="HaproxyServer"):
            HaproxyServer(
                server_name=kwargs["server_name"],
                address=kwargs["address"],
            )


def test_haproxy_render_context_rejects_empty_acl_name() -> None:
    with pytest.raises(ValueError, match="vhost_acl_name"):
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="",
                    vhost_hosts=("safe.host",),
                ssl_provider="none",
                    backend=_backend(),
                ),
            )
        )


def test_haproxy_render_context_rejects_empty_host() -> None:
    with pytest.raises(ValueError, match="HaproxyRenderContext.vhost_hosts"):
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="safe_acl",
                    vhost_hosts=("",),
                ssl_provider="none",
                    backend=_backend(),
                ),
            )
        )


def test_haproxy_render_context_rejects_duplicate_identifiers() -> None:
    with pytest.raises(ValueError, match="duplicate HAProxy identifier"):
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_duplicate",
                    vhost_hosts=("one.example.com",),
                ssl_provider="none",
                    backend=_backend("be_one", "srv_one", "one-backend:8000"),
                ),
                HaproxyRoute(
                    vhost_acl_name="host_duplicate",
                    vhost_hosts=("two.example.com",),
                ssl_provider="none",
                    backend=_backend("be_two", "srv_two", "two-backend:8000"),
                ),
            )
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "", "server_name": "srv", "address": "host:80"},
        {"name": "be", "server_name": "", "address": "host:80"},
        {"name": "be", "server_name": "srv", "address": ""},
    ],
)
def test_haproxy_backend_rejects_empty_values(kwargs: dict) -> None:
    with pytest.raises(ValueError, match="Haproxy"):
        HaproxyBackend(
            name=kwargs["name"],
            servers=(
                HaproxyServer(
                    server_name=kwargs["server_name"],
                    address=kwargs["address"],
                ),
            ),
        )


def _ddos(
    stick_table_name: str = "st_ddos_vhost_1",
    rate_limit_requests: int = 100,
    rate_limit_window_seconds: int = 10,
    max_connections_per_ip: int = 20,
    enabled: bool = True,
    auto_ban_enabled: bool = False,
    ban_stick_table_name: str = "",
    ban_threshold: int = 10,
    ban_duration_seconds: int = 600,
) -> HaproxyDdos:
    return HaproxyDdos(
        enabled=enabled,
        stick_table_name=stick_table_name,
        rate_limit_requests=rate_limit_requests,
        rate_limit_window_seconds=rate_limit_window_seconds,
        max_connections_per_ip=max_connections_per_ip,
        auto_ban_enabled=auto_ban_enabled,
        ban_stick_table_name=ban_stick_table_name,
        ban_threshold=ban_threshold,
        ban_duration_seconds=ban_duration_seconds,
    )


def test_haproxy_template_omits_ddos_blocks_when_disabled() -> None:
    rendered = render_haproxy_cfg(_m1_reference_context())

    assert "stick-table" not in rendered
    assert "track-sc0" not in rendered
    assert "deny_status 429" not in rendered


def test_haproxy_template_renders_ddos_blocks_when_enabled() -> None:
    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_api",
                    vhost_hosts=("api.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_api", "api", "api-backend:9000"),
                    ddos=_ddos(
                        stick_table_name="st_ddos_vhost_1",
                        rate_limit_requests=100,
                        rate_limit_window_seconds=10,
                        max_connections_per_ip=20,
                    ),
                ),
            ),
        )
    )

    assert (
        "backend st_ddos_vhost_1\n"
        "    stick-table type ipv6 size 100k expire 10s "
        "store http_req_rate(10s),conn_cur" in rendered
    )
    assert (
        "http-request track-sc0 src table st_ddos_vhost_1 "
        "if host_api !is_health !is_acme" in rendered
    )
    assert (
        "http-request deny deny_status 429 if host_api !is_health !is_acme "
        "{ sc_http_req_rate(0,st_ddos_vhost_1) gt 100 }" in rendered
    )
    assert (
        "http-request deny deny_status 429 if host_api !is_health !is_acme "
        "{ sc_conn_cur(0,st_ddos_vhost_1) gt 20 }" in rendered
    )
    assert "timeout http-request 5s" in rendered


def test_haproxy_template_omits_ddos_for_disabled_route_only() -> None:
    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_vhost_1",
                    vhost_hosts=("one.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_one", "srv_one", "one-backend:8000"),
                    ddos=_ddos(stick_table_name="st_ddos_vhost_1"),
                ),
                HaproxyRoute(
                    vhost_acl_name="host_vhost_2",
                    vhost_hosts=("two.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_two", "srv_two", "two-backend:8000"),
                ),
            )
        )
    )

    assert "table st_ddos_vhost_1 if host_vhost_1" in rendered
    assert "table st_ddos_vhost_1 if host_vhost_2" not in rendered
    assert "if host_vhost_2 { sc_http_req_rate" not in rendered


def test_haproxy_template_omits_auto_ban_blocks_when_disabled() -> None:
    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_api",
                    vhost_hosts=("api.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_api", "api", "api-backend:9000"),
                    ddos=_ddos(auto_ban_enabled=False),
                ),
            ),
        )
    )

    assert "track-sc1" not in rendered
    assert "sc-inc-gpc0" not in rendered
    assert "st_ban_" not in rendered


def test_haproxy_template_renders_auto_ban_blocks_when_enabled() -> None:
    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_api",
                    vhost_hosts=("api.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_api", "api", "api-backend:9000"),
                    ddos=_ddos(
                        stick_table_name="st_ddos_vhost_1",
                        rate_limit_requests=100,
                        max_connections_per_ip=20,
                        auto_ban_enabled=True,
                        ban_stick_table_name="st_ban_vhost_1",
                        ban_threshold=5,
                        ban_duration_seconds=600,
                    ),
                ),
            ),
        )
    )

    assert (
        "backend st_ban_vhost_1\n"
        "    stick-table type ipv6 size 100k expire 600s store gpc0" in rendered
    )
    assert (
        "http-request track-sc1 src table st_ban_vhost_1 "
        "if host_api !is_health !is_acme" in rendered
    )
    assert (
        "http-request deny deny_status 429 if host_api !is_health !is_acme "
        "{ sc_get_gpc0(1) gt 5 }" in rendered
    )
    assert (
        "http-request sc-inc-gpc0(1) if host_api !is_health !is_acme "
        "{ sc_http_req_rate(0,st_ddos_vhost_1) gt 100 }" in rendered
    )
    assert (
        "http-request sc-inc-gpc0(1) if host_api !is_health !is_acme "
        "{ sc_conn_cur(0,st_ddos_vhost_1) gt 20 }" in rendered
    )


def test_haproxy_render_context_rejects_duplicate_ban_table_names() -> None:
    with pytest.raises(ValueError, match="ban_stick_table_name"):
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_one",
                    vhost_hosts=("one.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_one", "srv_one", "one-backend:8000"),
                    ddos=_ddos(
                        stick_table_name="st_ddos_one",
                        auto_ban_enabled=True,
                        ban_stick_table_name="st_ban_dup",
                    ),
                ),
                HaproxyRoute(
                    vhost_acl_name="host_two",
                    vhost_hosts=("two.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_two", "srv_two", "two-backend:8000"),
                    ddos=_ddos(
                        stick_table_name="st_ddos_two",
                        auto_ban_enabled=True,
                        ban_stick_table_name="st_ban_dup",
                    ),
                ),
            )
        )


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        (
            "ban_stick_table_name",
            {"ban_stick_table_name": "", "ban_threshold": 1, "ban_duration_seconds": 1},
        ),
        (
            "ban_threshold",
            {
                "ban_stick_table_name": "st_ban",
                "ban_threshold": 0,
                "ban_duration_seconds": 1,
            },
        ),
        (
            "ban_duration_seconds",
            {
                "ban_stick_table_name": "st_ban",
                "ban_threshold": 1,
                "ban_duration_seconds": 0,
            },
        ),
        (
            "ban_duration_seconds_too_large",
            {
                "ban_stick_table_name": "st_ban",
                "ban_threshold": 1,
                "ban_duration_seconds": 86401,
            },
        ),
    ],
)
def test_haproxy_ddos_rejects_invalid_ban_values(field: str, kwargs: dict) -> None:
    with pytest.raises(ValueError):
        HaproxyDdos(
            enabled=True,
            stick_table_name="st_ddos",
            rate_limit_requests=1,
            rate_limit_window_seconds=1,
            max_connections_per_ip=1,
            auto_ban_enabled=True,
            **kwargs,
        )


def test_haproxy_render_context_rejects_duplicate_ddos_table_names() -> None:
    with pytest.raises(ValueError, match="stick_table_name"):
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_one",
                    vhost_hosts=("one.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_one", "srv_one", "one-backend:8000"),
                    ddos=_ddos(stick_table_name="st_dup"),
                ),
                HaproxyRoute(
                    vhost_acl_name="host_two",
                    vhost_hosts=("two.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_two", "srv_two", "two-backend:8000"),
                    ddos=_ddos(stick_table_name="st_dup"),
                ),
            )
        )


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        (
            "stick_table_name",
            {
                "stick_table_name": "",
                "rate_limit_requests": 1,
                "rate_limit_window_seconds": 1,
                "max_connections_per_ip": 1,
            },
        ),
        (
            "rate_limit_requests",
            {
                "stick_table_name": "st_ddos",
                "rate_limit_requests": 0,
                "rate_limit_window_seconds": 1,
                "max_connections_per_ip": 1,
            },
        ),
        (
            "rate_limit_window_seconds",
            {
                "stick_table_name": "st_ddos",
                "rate_limit_requests": 1,
                "rate_limit_window_seconds": 0,
                "max_connections_per_ip": 1,
            },
        ),
        (
            "rate_limit_window_seconds_too_large",
            {
                "stick_table_name": "st_ddos",
                "rate_limit_requests": 1,
                "rate_limit_window_seconds": 3601,
                "max_connections_per_ip": 1,
            },
        ),
        (
            "max_connections_per_ip",
            {
                "stick_table_name": "st_ddos",
                "rate_limit_requests": 1,
                "rate_limit_window_seconds": 1,
                "max_connections_per_ip": 0,
            },
        ),
    ],
)
def test_haproxy_ddos_rejects_invalid_values(field: str, kwargs: dict) -> None:
    with pytest.raises(ValueError):
        HaproxyDdos(enabled=True, **kwargs)


@pytest.mark.skipif(shutil.which("haproxy") is None, reason="haproxy is not installed")
def test_rendered_haproxy_template_with_ddos_validates_with_haproxy(
    tmp_path: Path,
) -> None:
    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_app",
                    vhost_hosts=("app.local",),
                    ssl_provider="none",
                    backend=_backend("be_app", "app", "backend:8000"),
                    ddos=_ddos(stick_table_name="st_ddos_vhost_1"),
                ),
            ),
        )
    )

    coraza_cfg = REPO_ROOT / "configs/haproxy/coraza.cfg"
    rendered = rendered.replace(
        "/usr/local/etc/haproxy/coraza.cfg", str(coraza_cfg)
    )

    rendered_path = tmp_path / "haproxy.cfg"
    rendered_path.write_text(rendered)

    result = subprocess.run(
        ["haproxy", "-c", "-f", str(rendered_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("haproxy") is None, reason="haproxy is not installed")
def test_rendered_haproxy_template_with_auto_ban_validates_with_haproxy(
    tmp_path: Path,
) -> None:
    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_app",
                    vhost_hosts=("app.local",),
                    ssl_provider="none",
                    backend=_backend("be_app", "app", "backend:8000"),
                    ddos=_ddos(
                        stick_table_name="st_ddos_vhost_1",
                        auto_ban_enabled=True,
                        ban_stick_table_name="st_ban_vhost_1",
                    ),
                ),
            ),
        )
    )

    coraza_cfg = REPO_ROOT / "configs/haproxy/coraza.cfg"
    rendered = rendered.replace(
        "/usr/local/etc/haproxy/coraza.cfg", str(coraza_cfg)
    )

    rendered_path = tmp_path / "haproxy.cfg"
    rendered_path.write_text(rendered)

    result = subprocess.run(
        ["haproxy", "-c", "-f", str(rendered_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# GeoIP country filtering (issue #175)
# ---------------------------------------------------------------------------


def _geoip(
    mode: str = "allowlist",
    countries: tuple[str, ...] = ("PL", "DE"),
    map_path: str = "/etc/haproxy/generated/geoip/country.map",
    fail_open: bool = True,
) -> HaproxyGeoip:
    return HaproxyGeoip(
        mode=mode,
        countries=countries,
        map_path=map_path,
        fail_open=fail_open,
    )


def test_haproxy_template_renders_allowlist_geoip_in_both_frontends() -> None:
    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_api",
                    vhost_hosts=("api.example.com",),
                    ssl_provider="letsencrypt",
                    backend=_backend("be_api", "api", "api-backend:9000"),
                    geoip=_geoip(mode="allowlist", countries=("PL", "DE")),
                ),
            ),
        )
    )

    set_var_line = (
        "http-request set-var(txn.geoip_country) src,map_ip"
        "(/etc/haproxy/generated/geoip/country.map) if !is_acme"
    )
    acl_line = "acl geoip_host_api var(txn.geoip_country) -m str PL DE"
    deny_line = (
        "http-request deny deny_status 403 if host_api !is_acme "
        "{ var(txn.geoip_country) -m found } !geoip_host_api"
    )
    assert rendered.count(set_var_line) == 2
    assert rendered.count(acl_line) == 2
    assert rendered.count(deny_line) == 2


def test_haproxy_template_renders_blocklist_geoip_without_found_guard() -> None:
    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_api",
                    vhost_hosts=("api.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_api", "api", "api-backend:9000"),
                    geoip=_geoip(mode="blocklist", countries=("RU", "CN")),
                ),
            ),
        )
    )

    acl_line = "acl geoip_host_api var(txn.geoip_country) -m str RU CN"
    deny_line = "http-request deny deny_status 403 if host_api !is_acme geoip_host_api"
    assert acl_line in rendered
    assert deny_line in rendered
    assert "-m found } !geoip_host_api" not in rendered


def test_haproxy_template_geoip_fail_closed_adds_extra_deny() -> None:
    rendered_fail_open = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_api",
                    vhost_hosts=("api.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_api", "api", "api-backend:9000"),
                    geoip=_geoip(mode="blocklist", countries=("RU",), fail_open=True),
                ),
            ),
        )
    )
    rendered_fail_closed = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_api",
                    vhost_hosts=("api.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_api", "api", "api-backend:9000"),
                    geoip=_geoip(mode="blocklist", countries=("RU",), fail_open=False),
                ),
            ),
        )
    )

    fail_closed_deny = (
        "http-request deny deny_status 403 if host_api !is_acme "
        "!{ var(txn.geoip_country) -m found }"
    )
    assert fail_closed_deny not in rendered_fail_open
    assert fail_closed_deny in rendered_fail_closed


def test_haproxy_template_omits_geoip_lines_when_route_has_none() -> None:
    rendered_plain = render_haproxy_cfg(_m1_reference_context())
    rendered_with_geoip_field = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_app",
                    vhost_hosts=("app.local", "localhost", "127.0.0.1"),
                    ssl_provider="none",
                    backend=_backend("be_app", "app", "backend:8000"),
                    geoip=None,
                ),
            ),
        )
    )

    assert "geoip_country" not in rendered_plain
    assert "geoip_country" not in rendered_with_geoip_field
    assert _normalise_config(rendered_plain) == _normalise_config(
        rendered_with_geoip_field
    )


def test_haproxy_template_geoip_lines_precede_ddos_and_spoe() -> None:
    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_api",
                    vhost_hosts=("api.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_api", "api", "api-backend:9000"),
                    ddos=_ddos(stick_table_name="st_ddos_vhost_1"),
                    geoip=_geoip(mode="blocklist", countries=("RU",)),
                ),
            ),
        )
    )

    geoip_index = rendered.index("geoip_country")
    ddos_index = rendered.index("track-sc0")
    spoe_index = rendered.index("filter spoe engine coraza")

    assert geoip_index < ddos_index < spoe_index


def test_haproxy_template_geoip_rules_exempt_acme_but_never_health() -> None:
    """/health must not be a country-filter bypass.

    `is_health` is a host-independent `path /health` match with no
    `use_backend` of its own, so a request to /health on a protected vhost is
    routed to the customer origin. Exempting it from the GeoIP rules would let
    any blocked country reach that origin just by asking for /health. ACME is
    different: `is_acme` has its own local `backend_acme` and must stay exempt
    so certificate issuance keeps working.
    """
    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_api",
                    vhost_hosts=("api.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_api", "api", "api-backend:9000"),
                    geoip=_geoip(mode="blocklist", countries=("RU",), fail_open=False),
                ),
            ),
        )
    )

    geoip_lines = [
        line
        for line in rendered.splitlines()
        if "geoip" in line and line.strip().startswith("http-request")
    ]
    assert geoip_lines, "expected at least one geoip-related line"
    for line in geoip_lines:
        assert "!is_health" not in line
        assert "!is_acme" in line


def test_haproxy_template_chunks_country_codes_to_survive_line_word_limit() -> None:
    """HAProxy truncates a config line after 64 words, which is fatal.

    A single-line list of every ISO code would blow past that, so codes are
    emitted as repeated same-name ACLs (which HAProxy ORs together). Verified
    against haproxy:3.0-alpine: 59 codes on an `acl` line is the real ceiling.
    """
    countries = tuple(sorted(code for code in VALID_COUNTRY_CODES if code != "ZZ"))
    assert len(countries) > 60, "fixture must exceed the per-line word limit"

    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            routes=(
                HaproxyRoute(
                    vhost_acl_name="host_api",
                    vhost_hosts=("api.example.com",),
                    ssl_provider="none",
                    backend=_backend("be_api", "api", "api-backend:9000"),
                    geoip=_geoip(mode="blocklist", countries=countries),
                ),
            ),
        )
    )

    # Both frontends emit the same block; analyse fe_http's copy on its own.
    fe_http = rendered.split("frontend fe_https", 1)[0]
    acl_lines = [
        line.strip()
        for line in fe_http.splitlines()
        if line.strip().startswith("acl geoip_host_api ")
    ]
    assert len(acl_lines) > 1, "expected the country list to be split across lines"
    for line in acl_lines:
        assert len(line.split()) <= 64

    emitted: list[str] = []
    for line in acl_lines:
        emitted.extend(line.split("-m str ", 1)[1].split())
    assert emitted == list(countries), "chunking must not drop or reorder codes"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mode": "denylist"},
        {"countries": ()},
        {"countries": ("pl",)},
        {"countries": ("POL",)},
        {"countries": ("P L",)},
        {"countries": ("PL\ndeny",)},
        {"map_path": "relative/path.map"},
        {"map_path": "/has space/country.map"},
    ],
)
def test_haproxy_geoip_rejects_invalid_values(kwargs: dict) -> None:
    base = {
        "mode": "allowlist",
        "countries": ("PL",),
        "map_path": "/etc/haproxy/generated/geoip/country.map",
        "fail_open": True,
    }
    base.update(kwargs)
    with pytest.raises(ValueError):
        HaproxyGeoip(**base)


@pytest.mark.skipif(shutil.which("haproxy") is None, reason="haproxy is not installed")
def test_rendered_haproxy_template_validates_with_haproxy(tmp_path: Path) -> None:
    rendered = render_haproxy_cfg(_m1_reference_context())

    # In production this path is provided by the container image (see
    # docker/docker-compose.yml). For local validation, point it at
    # the repo's reference coraza.cfg so `haproxy -c` can resolve it.
    coraza_cfg = REPO_ROOT / "configs/haproxy/coraza.cfg"
    rendered = rendered.replace(
        "/usr/local/etc/haproxy/coraza.cfg", str(coraza_cfg)
    )

    rendered_path = tmp_path / "haproxy.cfg"
    rendered_path.write_text(rendered)

    result = subprocess.run(
        ["haproxy", "-c", "-f", str(rendered_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
