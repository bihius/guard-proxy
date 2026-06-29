import shutil
import subprocess
from pathlib import Path

import pytest

from app.services.config_renderer import (
    HaproxyBackend,
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


@pytest.mark.skipif(shutil.which("haproxy") is None, reason="haproxy is not installed")
def test_rendered_haproxy_template_validates_with_haproxy(tmp_path: Path) -> None:
    rendered = render_haproxy_cfg(_m1_reference_context())

    # In production this path is provided by the container image (see
    # deploy/docker/docker-compose.yml). For local validation, point it at
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
