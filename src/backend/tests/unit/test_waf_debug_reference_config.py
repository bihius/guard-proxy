from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate

    raise FileNotFoundError(
        f"Could not locate repository root from {start}; expected .git directory"
    )


REPO_ROOT = _find_repo_root(Path(__file__).resolve().parent)


def test_default_haproxy_config_uses_info_logging() -> None:
    config = (REPO_ROOT / "configs/haproxy/haproxy.cfg").read_text()

    assert "log stdout format raw local0 info" in config
    assert "http-request send-spoe-group coraza coraza-req unless is_health" in config


def test_default_coraza_spoa_config_uses_info_logging() -> None:
    config = (REPO_ROOT / "configs/coraza/coraza-spoa.yaml").read_text()

    assert config.count("log_level: info") == 2
    assert "log_file: /dev/stdout" in config


def test_default_docker_compose_does_not_use_debug_flag() -> None:
    compose = (REPO_ROOT / "deploy/docker/docker-compose.yml").read_text()

    assert '"-d"' not in compose


def test_debug_coraza_spoa_config_enables_debug_logging() -> None:
    config = (REPO_ROOT / "configs/coraza/coraza-spoa.debug.yaml").read_text()

    assert config.count("log_level: debug") == 2
    assert "log_file: /dev/stdout" in config


def test_debug_compose_override_enables_haproxy_debug_flag() -> None:
    compose = (REPO_ROOT / "deploy/docker/docker-compose.debug.yml").read_text()

    assert (
        'command: ["haproxy", "-d", "-f", "/usr/local/etc/haproxy/haproxy.cfg"]'
        in compose
    )


def test_debug_compose_override_mounts_debug_coraza_config() -> None:
    compose = (REPO_ROOT / "deploy/docker/docker-compose.debug.yml").read_text()

    assert "coraza-spoa.debug.yaml" in compose


def test_makefile_exposes_run_and_dev_targets() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text()

    assert "run:" in makefile
    assert "dev:" in makefile
    assert "docker-compose.debug.yml" in makefile


def test_haproxy_readme_documents_spoe_troubleshooting() -> None:
    readme = (REPO_ROOT / "configs/haproxy/README.md").read_text()

    assert "## Troubleshooting SPOE frames" in readme
    assert "make dev" in readme
    assert "X-Request-ID: spoe-debug-1" in readme
    assert "tcpdump -i any -A -s 0 port 9000" in readme


def test_reference_haproxy_config_fails_closed_on_spoe_errors() -> None:
    config = (REPO_ROOT / "configs/haproxy/haproxy.cfg").read_text()

    assert (
        "http-request set-log-level err if { var(txn.coraza.error) -m found }"
        in config
    )
    assert (
        "http-request return status 503 "
        'hdr "X-WAF-Degraded" "true" '
        'hdr "X-WAF-Error" "%[var(txn.coraza.error)]" '
        "if { var(txn.coraza.error) -m found }" in config
    )


def test_haproxy_readme_documents_fail_closed_degraded_mode() -> None:
    readme = (REPO_ROOT / "configs/haproxy/README.md").read_text()

    assert "## Degraded-mode behaviour" in readme
    assert "fails closed" in readme
    assert "503 Service Unavailable" in readme
    assert "X-WAF-Degraded: true" in readme
    assert "tracked separately in #69" in readme
