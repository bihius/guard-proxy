"""E2E test for DB-backed policy apply behavior."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

ADMIN_EMAIL = "policy-apply-admin@example.com"
ADMIN_PASSWORD = "policy-apply-password-123"
HOST_HEADER = "app.local"
SHOP_HOST = "shop.local"
BLOG_HOST = "blog.local"
PLAIN_HOST = "plain.local"
SCANNER_USER_AGENT = "nuclei"
SCANNER_RULE_ID = 913100
EXCLUSION_RULE_ID = 942100
CUSTOM_RULE_ID = 9000001
HTTP_TIMEOUT_SECONDS = 5
SERVICE_TIMEOUT_SECONDS = 180
# Coraza's supervisor polls /runtime/current every second before reloading the
# SPOA's rules. Keep this timeout comfortably above that lower bound plus
# container scheduling.
RELOAD_TIMEOUT_SECONDS = 45
# Delay between traffic-probe requests: ~20 req/s, well above the 5 req/s that
# issue #303 asks a probe to sustain during an apply.
PROBE_INTERVAL_SECONDS = 0.05


def _find_repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "docker/docker-compose.yml").is_file():
            return candidate
    raise RuntimeError("Could not locate repository root")


REPO_ROOT = _find_repo_root()
COMPOSE_FILE = REPO_ROOT / "docker/docker-compose.yml"
ENV_FILE = REPO_ROOT / "docker/.env"
CRS_RULES_DIR = REPO_ROOT / "configs/coraza/crs/rules"


@dataclass(frozen=True)
class ComposeStack:
    command: list[str]
    env: dict[str, str]
    base_url: str


@pytest.fixture()
def compose_stack() -> ComposeStack:
    _require_e2e_prerequisites()

    project_name = f"guard-proxy-policy-apply-{uuid.uuid4().hex[:8]}"
    port = _free_tcp_port()
    stack = ComposeStack(
        command=_compose_command(project_name),
        env={
            **os.environ,
            "HAPROXY_HTTP_PORT": str(port),
        },
        base_url=f"http://127.0.0.1:{port}",
    )

    _run(
        stack.command
        + ["up", "-d", "--build", "postgres", "backend", "coraza", "haproxy"],
        env=stack.env,
        timeout=600,
    )

    try:
        for service in ("postgres", "backend", "coraza", "haproxy"):
            _wait_for_healthy(stack, service)
        _seed_admin(stack)
        yield stack
    except BaseException:
        print("\nPolicy apply e2e failed. Recent service logs:")
        print(_compose_logs(stack))
        raise
    finally:
        _run(stack.command + ["down", "-v"], env=stack.env, check=False, timeout=180)


@pytest.mark.e2e
def test_policy_apply_rule_override_flips_runtime_waf_behavior(
    compose_stack: ComposeStack,
) -> None:
    token = _login(compose_stack)
    policy_id = _create_policy_with_vhost(compose_stack, token, "Policy apply e2e")
    _api_json(
        compose_stack,
        "POST",
        f"/policies/{policy_id}/exclusions",
        token=token,
        expected_status=201,
        payload={
            "rule_id": EXCLUSION_RULE_ID,
            "target_type": "args",
            "target_value": "token",
            "scope_path": "/api/login",
            "comment": "E2E proves exclusions reach generated config",
        },
    )
    _api_json(
        compose_stack,
        "POST",
        f"/policies/{policy_id}/custom-rules",
        token=token,
        expected_status=201,
        payload={
            "rule_id": CUSTOM_RULE_ID,
            "phase": "request_headers",
            "variables": "REQUEST_HEADERS:X-Guard-Proxy-E2E",
            "operator": "streq",
            "operator_argument": "deny-me",
            "actions": "deny,status:403,log",
            "comment": "E2E proves custom rules reach generated config",
            "is_active": True,
        },
    )

    applied = _apply_config(compose_stack, token)
    app = _coraza_app(applied, policy_id)
    assert "SecRuleEngine On" in app["crs_setup_conf"]
    assert f"SecRuleRemoveById {SCANNER_RULE_ID}" not in app["rule_overrides_conf"]
    assert (
        f"ctl:ruleRemoveTargetById={EXCLUSION_RULE_ID};ARGS:token"
        in app["rule_overrides_conf"]
    )
    assert (
        f"id:{CUSTOM_RULE_ID},phase:1,deny,status:403,log"
        in app["rule_overrides_conf"]
    )
    _assert_coraza_runtime_override(compose_stack, policy_id, should_exist=False)
    _assert_coraza_runtime_tuning(compose_stack, policy_id, should_exist=True)
    _wait_for_status(
        compose_stack,
        403,
        "scanner request before override",
        headers={"User-Agent": SCANNER_USER_AGENT},
    )

    override = _api_json(
        compose_stack,
        "POST",
        f"/policies/{policy_id}/rules",
        token=token,
        expected_status=201,
        payload={
            "rule_id": SCANNER_RULE_ID,
            "action": "disable",
            "comment": "E2E proves DB override reaches Coraza",
        },
    )

    applied = _apply_config(compose_stack, token)
    assert (
        f"SecRuleRemoveById {SCANNER_RULE_ID}"
        in _coraza_app(applied, policy_id)["rule_overrides_conf"]
    )
    _assert_coraza_runtime_override(compose_stack, policy_id, should_exist=True)
    # The runtime-file assertion proves the override reached Coraza's mount;
    # the HTTP verdict is still the user-visible contract for issue #114.
    _wait_for_status(
        compose_stack,
        200,
        "scanner request after disable override",
        headers={"User-Agent": SCANNER_USER_AGENT},
    )

    _api_json(
        compose_stack,
        "PATCH",
        f"/policies/{policy_id}/rules/{override['id']}",
        token=token,
        payload={"action": "enable"},
    )

    applied = _apply_config(compose_stack, token)
    assert (
        f"SecRuleRemoveById {SCANNER_RULE_ID}"
        not in _coraza_app(applied, policy_id)["rule_overrides_conf"]
    )
    _assert_coraza_runtime_override(compose_stack, policy_id, should_exist=False)
    _wait_for_status(
        compose_stack,
        403,
        "scanner request after re-enable",
        headers={"User-Agent": SCANNER_USER_AGENT},
    )


@pytest.mark.e2e
def test_each_vhost_is_inspected_with_its_own_policy(
    compose_stack: ComposeStack,
) -> None:
    """Policies, rule overrides, and custom rules apply only to their vhost."""
    token = _login(compose_stack)
    shop_policy_id = _create_policy_with_vhost(
        compose_stack, token, "Shop policy", domain=SHOP_HOST
    )
    blog_policy_id = _create_policy_with_vhost(
        compose_stack, token, "Blog policy", domain=BLOG_HOST
    )
    _api_json(
        compose_stack,
        "POST",
        "/vhosts",
        token=token,
        expected_status=201,
        payload={"domain": PLAIN_HOST, "backend_url": "http://backend:8000"},
    )
    # Blog lets scanners through and blocks a header that the shop allows.
    _api_json(
        compose_stack,
        "POST",
        f"/policies/{blog_policy_id}/rules",
        token=token,
        expected_status=201,
        payload={"rule_id": SCANNER_RULE_ID, "action": "disable"},
    )
    _api_json(
        compose_stack,
        "POST",
        f"/policies/{blog_policy_id}/custom-rules",
        token=token,
        expected_status=201,
        payload={
            "rule_id": CUSTOM_RULE_ID,
            "phase": "request_headers",
            "variables": "REQUEST_HEADERS:X-Guard-Proxy-E2E",
            "operator": "streq",
            "operator_argument": "deny-me",
            "actions": "deny,status:403,log",
            "is_active": True,
        },
    )

    applied = _apply_config(compose_stack, token)

    assert [app["name"] for app in applied["generated_config"]["coraza_apps"]] == [
        "default",
        f"policy_{shop_policy_id}",
        f"policy_{blog_policy_id}",
    ]
    scanner = {"User-Agent": SCANNER_USER_AGENT}
    custom = {"X-Guard-Proxy-E2E": "deny-me"}
    # Wait for Coraza to load the new applications before single-shot checks.
    _wait_for_status(
        compose_stack, 403, "blog custom rule", headers={"Host": BLOG_HOST, **custom}
    )
    _wait_for_status(
        compose_stack, 403, "shop scanner", headers={"Host": SHOP_HOST, **scanner}
    )
    assert _status(compose_stack, {"Host": BLOG_HOST, **scanner}) == 200
    assert _status(compose_stack, {"Host": SHOP_HOST, **custom}) == 200
    # Without a policy the vhost is inspected in log-only mode.
    assert _status(compose_stack, {"Host": PLAIN_HOST, **scanner}) == 200


@pytest.mark.e2e
def test_config_apply_keeps_serving_traffic_without_503(
    compose_stack: ComposeStack,
) -> None:
    """Regression for #303: an apply must not interrupt traffic.

    Each apply used to restart coraza-spoa, and HAProxy's fail-closed rules
    answered every request that arrived while it was down with 503.
    """
    token = _login(compose_stack)
    policy_id = _create_policy_with_vhost(compose_stack, token, "Apply traffic e2e")
    _apply_config(compose_stack, token)
    _wait_for_status(
        compose_stack,
        403,
        "scanner request before override",
        headers={"User-Agent": SCANNER_USER_AGENT},
    )

    with _probe_traffic(compose_stack) as probe:
        _api_json(
            compose_stack,
            "POST",
            f"/policies/{policy_id}/rules",
            token=token,
            expected_status=201,
            payload={"rule_id": SCANNER_RULE_ID, "action": "disable"},
        )
        _apply_config(compose_stack, token)
        # The flipped verdict proves Coraza is enforcing the new rules, so the
        # probe covered the whole rule switch, not just the HAProxy reload.
        _wait_for_status(
            compose_stack,
            200,
            "scanner request after disable override",
            headers={"User-Agent": SCANNER_USER_AGENT},
        )
        _apply_config(compose_stack, token)
        time.sleep(3)

    assert len(probe.results) > 20, f"probe sent too few requests: {probe.results}"
    failures = [result for result in probe.results if result != 200]
    assert not failures, f"traffic was interrupted during apply: {failures}"

    # Fail-closed must still hold when Coraza is really unavailable.
    _run(compose_stack.command + ["stop", "coraza"], env=compose_stack.env)
    _wait_for_status(compose_stack, 503, "request with Coraza stopped")


@dataclass
class TrafficProbe:
    results: list[int | str] = field(default_factory=list)


@contextmanager
def _probe_traffic(stack: ComposeStack) -> Iterator[TrafficProbe]:
    """Send benign requests through the WAF in the background until exit."""
    probe = TrafficProbe()
    stop = threading.Event()

    def run() -> None:
        while not stop.is_set():
            try:
                status, _ = _http_request(f"{stack.base_url}/docs", method="GET")
                probe.results.append(status)
            except URLError as error:
                probe.results.append(str(error))
            stop.wait(PROBE_INTERVAL_SECONDS)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        yield probe
    finally:
        stop.set()
        thread.join(timeout=HTTP_TIMEOUT_SECONDS + 1)


def _create_policy_with_vhost(
    stack: ComposeStack, token: str, name: str, *, domain: str = HOST_HEADER
) -> int:
    policy = _api_json(
        stack,
        "POST",
        "/policies",
        token=token,
        expected_status=201,
        payload={
            "name": name,
            "paranoia_level": 1,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 4,
            "enforcement_mode": "block",
        },
    )
    _api_json(
        stack,
        "POST",
        "/vhosts",
        token=token,
        expected_status=201,
        payload={
            "domain": domain,
            "backend_url": "http://backend:8000",
            "ssl_enabled": False,
            "is_active": True,
            "policy_id": policy["id"],
        },
    )
    return int(policy["id"])


def _coraza_app(applied: dict[str, Any], policy_id: int) -> dict[str, str]:
    return next(
        app
        for app in applied["generated_config"]["coraza_apps"]
        if app["name"] == f"policy_{policy_id}"
    )


def _status(stack: ComposeStack, headers: dict[str, str]) -> int:
    status, _ = _http_request(f"{stack.base_url}/docs", method="GET", headers=headers)
    return status


def _require_e2e_prerequisites() -> None:
    if not ENV_FILE.is_file():
        pytest.fail(f"Missing {ENV_FILE}. Copy the example env file into place.")
    if not CRS_RULES_DIR.is_dir():
        pytest.fail(
            "Missing CRS submodule content. Run "
            "`git submodule update --init --recursive` from the repository root."
        )
    if shutil.which("docker") is None:
        pytest.fail("Docker is required for policy apply e2e tests.")
    try:
        _docker_compose_prefix()
    except RuntimeError:
        pytest.fail("Docker Compose is required for policy apply e2e tests.")


def _compose_command(project_name: str) -> list[str]:
    return [
        *_docker_compose_prefix(),
        "-f",
        str(COMPOSE_FILE),
        "--env-file",
        str(ENV_FILE),
        "--project-name",
        project_name,
    ]


@lru_cache
def _docker_compose_prefix() -> tuple[str, ...]:
    if _command_ok(["docker", "compose", "version"]):
        return ("docker", "compose")

    docker_compose = shutil.which("docker-compose")
    if docker_compose is None:
        raise RuntimeError("Docker Compose is required")
    return (docker_compose,)


def _command_ok(command: list[str]) -> bool:
    return (
        subprocess.run(command, capture_output=True, text=True, check=False).returncode
        == 0
    )


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def _wait_for_healthy(stack: ComposeStack, service: str) -> None:
    deadline = time.monotonic() + SERVICE_TIMEOUT_SECONDS
    last_status = "unknown"

    while time.monotonic() < deadline:
        container_id = _container_id(stack, service)
        if container_id:
            last_status = _container_status(container_id)
            if last_status == "healthy":
                return
            if last_status in {"dead", "exited"}:
                pytest.fail(
                    f"{service} container is {last_status}.\n{_compose_logs(stack)}"
                )
        time.sleep(2)

    pytest.fail(
        f"Timed out waiting for {service} to become healthy; "
        f"last status: {last_status}.\n{_compose_logs(stack)}"
    )


def _container_id(stack: ComposeStack, service: str) -> str:
    result = _run(
        stack.command + ["ps", "-q", service],
        env=stack.env,
        check=False,
    )
    return result.stdout.strip()


def _container_status(container_id: str) -> str:
    result = _run(
        [
            "docker",
            "inspect",
            "--format",
            (
                "{{if .State.Health}}{{.State.Health.Status}}"
                "{{else}}{{.State.Status}}{{end}}"
            ),
            container_id,
        ],
        check=False,
    )
    return result.stdout.strip() or "unknown"


def _seed_admin(stack: ComposeStack) -> None:
    _run(
        stack.command
        + [
            "exec",
            "-T",
            "backend",
            "/app/.venv/bin/python",
            "scripts/seed_admin.py",
            "--email",
            ADMIN_EMAIL,
            "--password",
            ADMIN_PASSWORD,
            "--full-name",
            "Policy Apply Test Admin",
        ],
        env=stack.env,
    )


def _login(stack: ComposeStack) -> str:
    response = _api_json(
        stack,
        "POST",
        "/auth/login",
        payload={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    return str(response["access_token"])


def _apply_config(stack: ComposeStack, token: str) -> dict[str, Any]:
    response = _api_json(stack, "POST", "/config/apply", token=token)
    assert response["status"] == "success"
    return response


def _runtime_rule_overrides(stack: ComposeStack, policy_id: int) -> str:
    result = _run(
        stack.command
        + [
            "exec",
            "-T",
            "coraza",
            "cat",
            f"/runtime/current/coraza/policy_{policy_id}/rule-overrides.conf",
        ],
        env=stack.env,
    )
    return result.stdout


def _assert_coraza_runtime_override(
    stack: ComposeStack, policy_id: int, *, should_exist: bool
) -> None:
    expected = f"SecRuleRemoveById {SCANNER_RULE_ID}"
    if should_exist:
        assert expected in _runtime_rule_overrides(stack, policy_id)
    else:
        assert expected not in _runtime_rule_overrides(stack, policy_id)


def _assert_coraza_runtime_tuning(
    stack: ComposeStack, policy_id: int, *, should_exist: bool
) -> None:
    rule_overrides = _runtime_rule_overrides(stack, policy_id)
    expected = [
        f"ctl:ruleRemoveTargetById={EXCLUSION_RULE_ID};ARGS:token",
        f"id:{CUSTOM_RULE_ID},phase:1,deny,status:403,log",
    ]
    for line in expected:
        if should_exist:
            assert line in rule_overrides
        else:
            assert line not in rule_overrides


def _api_json(
    stack: ComposeStack,
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    expected_status: int = 200,
) -> dict[str, Any]:
    status, body = _backend_http_request(
        stack,
        path,
        method=method,
        token=token,
        payload=payload,
    )
    if status != expected_status:
        pytest.fail(
            f"{method} {path}: expected HTTP {expected_status}, got {status}.\n{body}"
        )
    if not body:
        return {}
    return json.loads(body)


def _backend_http_request(
    stack: ComposeStack,
    path: str,
    *,
    method: str,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[int, str]:
    request = {
        "method": method,
        "url": f"http://127.0.0.1:8000{path}",
        "token": token,
        "payload": payload,
    }
    script = r"""
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

request_data = json.loads(sys.stdin.read())
headers = {"Accept": "application/json"}
body = None
if request_data["payload"] is not None:
    body = json.dumps(request_data["payload"]).encode("utf-8")
    headers["Content-Type"] = "application/json"
if request_data["token"] is not None:
    headers["Authorization"] = "Bearer " + request_data["token"]

request = Request(
    request_data["url"],
    data=body,
    headers=headers,
    method=request_data["method"],
)
try:
    with urlopen(request, timeout=5) as response:
        result = {
            "status": response.status,
            "body": response.read().decode("utf-8", errors="replace"),
        }
except HTTPError as error:
    result = {
        "status": error.code,
        "body": error.read().decode("utf-8", errors="replace"),
    }

print(json.dumps(result))
"""
    result = _run(
        stack.command
        + ["exec", "-T", "backend", "/app/.venv/bin/python", "-c", script],
        env=stack.env,
        input_text=json.dumps(request),
    )
    response = json.loads(result.stdout)
    return int(response["status"]), str(response["body"])


def _wait_for_status(
    stack: ComposeStack,
    expected_status: int,
    description: str,
    *,
    headers: dict[str, str] | None = None,
) -> None:
    deadline = time.monotonic() + RELOAD_TIMEOUT_SECONDS
    last_status: int | str = "unknown"

    while time.monotonic() < deadline:
        try:
            status, _ = _http_request(
                f"{stack.base_url}/docs",
                method="GET",
                headers=headers,
            )
            last_status = status
            if status == expected_status:
                return
        except URLError as error:
            last_status = str(error)
        time.sleep(1)

    pytest.fail(
        f"{description}: expected HTTP {expected_status}, got {last_status}.\n"
        f"{_compose_logs(stack)}"
    )


def _http_request(
    url: str,
    *,
    method: str,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    request_headers = {
        "Host": HOST_HEADER,
        **(headers or {}),
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    if token is not None:
        request_headers["Authorization"] = f"Bearer {token}"

    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


def _compose_logs(stack: ComposeStack) -> str:
    result = _run(
        stack.command + ["logs", "--tail=80", "backend", "haproxy", "coraza"],
        env=stack.env,
        check=False,
    )
    return result.stdout + result.stderr
