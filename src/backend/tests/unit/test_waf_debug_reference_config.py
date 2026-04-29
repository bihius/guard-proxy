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


def test_default_docker_compose_starts_haproxy_before_coraza_is_healthy() -> None:
    compose = (REPO_ROOT / "deploy/docker/docker-compose.yml").read_text()

    assert "coraza:\n        condition: service_started" in compose
    assert "coraza:\n        condition: service_healthy" not in compose
    assert '"${HAPROXY_HTTP_PORT:-8080}:80"' in compose


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
        "http-request set-var(txn.waf_degraded_reason) "
        "str(spoe-processing-error) if { var(txn.coraza.error) -m found }"
        in config
    )
    assert (
        "http-request set-log-level err if "
        "{ var(txn.waf_degraded_reason) -m found }"
        in config
    )
    assert (
        "http-request capture var(txn.waf_degraded_reason) len 32 "
        "if { var(txn.waf_degraded_reason) -m found }"
        in config
    )

    # Fail closed with 503 on SPOE errors.  Locate the exact return rule line
    # and verify that both headers and the condition appear on it together.
    # Tolerate quoting differences and optional extra tokens (e.g.
    # content-type/string).
    return_line = next(
        (
            line.strip()
            for line in config.splitlines()
            if "X-WAF-Degraded-Reason spoe-processing-error" in line
        ),
        None,
    )
    assert return_line is not None, "No SPOE error return rule found"
    assert return_line.startswith("http-request return status 503")
    assert (
        "hdr X-WAF-Status degraded" in return_line
        or 'hdr "X-WAF-Status" "degraded"' in return_line
    ), f"X-WAF-Status header missing from return rule: {return_line}"
    assert "hdr X-WAF-Degraded-Reason spoe-processing-error" in return_line, (
        f"X-WAF-Degraded-Reason header missing from return rule: {return_line}"
    )
    assert (
        "hdr X-WAF-Error-Code %[var(txn.coraza.error)]" in return_line
        or 'hdr "X-WAF-Error-Code" "%[var(txn.coraza.error)]"' in return_line
    ), f"X-WAF-Error-Code header missing from return rule: {return_line}"
    assert "if { var(txn.coraza.error) -m found }" in return_line, (
        f"Condition missing from return rule: {return_line}"
    )


def test_reference_haproxy_config_fails_closed_when_coraza_is_unavailable() -> None:
    config = (REPO_ROOT / "configs/haproxy/haproxy.cfg").read_text()

    assert (
        "http-request set-var(txn.waf_degraded_reason) "
        "str(coraza-unavailable) if !is_health { nbsrv(coraza-spoa) eq 0 }"
        in config
    )

    unavailable_line = next(
        (
            line.strip()
            for line in config.splitlines()
            if "X-WAF-Degraded-Reason coraza-unavailable" in line
        ),
        None,
    )
    assert unavailable_line is not None, "No coraza-unavailable return rule found"
    assert unavailable_line.startswith("http-request return status 503")
    assert "hdr X-WAF-Status degraded" in unavailable_line
    assert "hdr X-WAF-Degraded-Reason coraza-unavailable" in unavailable_line
    assert "if { var(txn.waf_degraded_reason) -m str coraza-unavailable }" in (
        unavailable_line
    )


def test_reference_haproxy_config_preserves_host_health_and_waf_rules() -> None:
    config = (REPO_ROOT / "configs/haproxy/haproxy.cfg").read_text()

    assert "acl is_health path /health" in config
    assert "http-request send-spoe-group coraza coraza-req unless is_health" in config
    assert "http-request deny deny_status 421 if !host_app" in config
    assert (
        "http-request deny deny_status 403 if "
        "{ var(txn.coraza.action) -m str deny }"
        in config
    )


def test_reference_coraza_spoe_config_sets_error_variable() -> None:
    config = (REPO_ROOT / "configs/haproxy/coraza.cfg").read_text()

    assert "option              set-on-error  error" in config


def test_haproxy_readme_documents_fail_closed_degraded_mode() -> None:
    readme = (REPO_ROOT / "configs/haproxy/README.md").read_text()

    assert "## Degraded-mode behaviour" in readme
    assert "fails closed" in readme
    assert "503 Service Unavailable" in readme
    assert "X-WAF-Status: degraded" in readme
    assert "X-WAF-Degraded-Reason" in readme
    assert "coraza-unavailable" in readme
    assert "spoe-processing-error" in readme
    assert "tracked separately in #69" in readme
