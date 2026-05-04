import shutil
import subprocess
from pathlib import Path

import pytest

from app.services.config_renderer import (
    HaproxyBackend,
    HaproxyRenderContext,
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


def _m1_reference_context() -> HaproxyRenderContext:
    return HaproxyRenderContext(
        vhost_acl_name="host_app",
        vhost_hosts=(
            "app.local",
            "app.local:80",
            "app.local:8080",
            "localhost",
            "localhost:8080",
            "127.0.0.1",
            "127.0.0.1:8080",
        ),
        backend=HaproxyBackend(
            name="be_app",
            server_name="app",
            address="backend:8000",
        ),
    )


def test_haproxy_template_renders_m1_reference_modulo_whitespace() -> None:
    rendered = render_haproxy_cfg(_m1_reference_context())
    reference = (REPO_ROOT / "configs/haproxy/haproxy.cfg").read_text()

    assert _normalise_config(rendered) == _normalise_config(reference)


def test_haproxy_template_parameterises_vhost_and_backend() -> None:
    rendered = render_haproxy_cfg(
        HaproxyRenderContext(
            vhost_acl_name="host_api",
            vhost_hosts=("api.example.com", "api.example.com:80"),
            backend=HaproxyBackend(
                name="be_api",
                server_name="api",
                address="api-backend:9000",
            ),
        )
    )

    assert "acl host_api hdr(host) -i api.example.com api.example.com:80" in rendered
    assert "http-request deny deny_status 421 if !host_api" in rendered
    assert "use_backend be_api if host_api" in rendered
    assert "default_backend be_api" in rendered
    assert "server api api-backend:9000 check" in rendered


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
            vhost_acl_name=vhost_acl_name,
            vhost_hosts=("safe.host",),
            backend=HaproxyBackend(name="be", server_name="srv", address="host:80"),
        )


@pytest.mark.parametrize(
    "host",
    [
        "has space",
        "has\nnewline",
        "has\ttab",
        "has#comment",
        "has;semi",
    ],
)
def test_haproxy_render_context_rejects_unsafe_host(host: str) -> None:
    with pytest.raises(ValueError, match="HaproxyRenderContext.vhost_hosts"):
        HaproxyRenderContext(
            vhost_acl_name="safe_acl",
            vhost_hosts=(host,),
            backend=HaproxyBackend(name="be", server_name="srv", address="host:80"),
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
    with pytest.raises(ValueError, match="HaproxyBackend"):
        HaproxyBackend(**kwargs)


def test_haproxy_render_context_rejects_empty_acl_name() -> None:
    with pytest.raises(ValueError, match="vhost_acl_name"):
        HaproxyRenderContext(
            vhost_acl_name="",
            vhost_hosts=("safe.host",),
            backend=HaproxyBackend(name="be", server_name="srv", address="host:80"),
        )


def test_haproxy_render_context_rejects_empty_host() -> None:
    with pytest.raises(ValueError, match="HaproxyRenderContext.vhost_hosts"):
        HaproxyRenderContext(
            vhost_acl_name="safe_acl",
            vhost_hosts=("",),
            backend=HaproxyBackend(name="be", server_name="srv", address="host:80"),
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
    with pytest.raises(ValueError, match="HaproxyBackend"):
        HaproxyBackend(**kwargs)


@pytest.mark.skipif(shutil.which("haproxy") is None, reason="haproxy is not installed")
def test_rendered_haproxy_template_validates_with_haproxy(tmp_path: Path) -> None:
    rendered_path = tmp_path / "haproxy.cfg"
    rendered_path.write_text(render_haproxy_cfg(_m1_reference_context()))

    result = subprocess.run(
        ["haproxy", "-c", "-f", str(rendered_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
