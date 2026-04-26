from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            return candidate

    raise FileNotFoundError(
        f"Could not locate repository root from {start}; expected pyproject.toml or .git"
    )


REPO_ROOT = _find_repo_root(Path(__file__).resolve().parent)
def test_reference_haproxy_config_enables_debug_logging() -> None:
    config = (REPO_ROOT / "configs/haproxy/haproxy.cfg").read_text()

    assert "log stdout format raw local0 debug" in config
    assert "http-request send-spoe-group coraza coraza-req unless is_health" in config


def test_docker_compose_runs_haproxy_in_debug_mode() -> None:
    compose = (REPO_ROOT / "deploy/docker/docker-compose.yml").read_text()

    assert (
        'command: ["haproxy", "-d", "-f", "/usr/local/etc/haproxy/haproxy.cfg"]'
        in compose
    )


def test_reference_coraza_spoa_config_enables_debug_logging() -> None:
    config = (REPO_ROOT / "configs/coraza/coraza-spoa.yaml").read_text()

    assert config.count("log_level: debug") == 2
    assert "log_file: /dev/stdout" in config


def test_haproxy_readme_documents_spoe_troubleshooting() -> None:
    readme = (REPO_ROOT / "configs/haproxy/README.md").read_text()

    assert "## Troubleshooting SPOE frames" in readme
    assert "docker compose -f deploy/docker/docker-compose.yml" in readme
    assert "X-Request-ID: spoe-debug-1" in readme
    assert "tcpdump -i lo -A -s 0 port 9000" in readme
