"""E2E test for DB-backed policy apply behavior."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

ADMIN_EMAIL = "policy-apply-admin@example.com"
ADMIN_PASSWORD = "policy-apply-password-123"
HOST_HEADER = "app.local"
SCANNER_USER_AGENT = "nuclei"
SCANNER_RULE_ID = 913100
HTTP_TIMEOUT_SECONDS = 5
SERVICE_TIMEOUT_SECONDS = 180
# Coraza's supervisor polls /runtime/current every second before restarting SPOA.
# Keep this timeout comfortably above that lower bound plus container scheduling.
RELOAD_TIMEOUT_SECONDS = 45


def _find_repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "deploy/docker/docker-compose.yml").is_file():
            return candidate
    raise RuntimeError("Could not locate repository root")


REPO_ROOT = _find_repo_root()
COMPOSE_FILE = REPO_ROOT / "deploy/docker/docker-compose.yml"
ENV_FILE = REPO_ROOT / "deploy/docker/.env"
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

    policy = _api_json(
        compose_stack,
        "POST",
        "/policies",
        token=token,
        expected_status=201,
        payload={
            "name": "Policy apply e2e",
            "paranoia_level": 1,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 4,
            "enforcement_mode": "block",
        },
    )
    policy_id = policy["id"]

    _api_json(
        compose_stack,
        "POST",
        "/vhosts",
        token=token,
        expected_status=201,
        payload={
            "domain": HOST_HEADER,
            "backend_url": "http://backend:8000",
            "ssl_enabled": False,
            "is_active": True,
            "policy_id": policy_id,
        },
    )

    applied = _apply_config(compose_stack, token)
    assert "SecRuleEngine On" in applied["generated_config"]["crs_setup_conf"]
    assert f"SecRuleRemoveById {SCANNER_RULE_ID}" not in applied["generated_config"][
        "rule_overrides_conf"
    ]
    _assert_coraza_runtime_override(compose_stack, should_exist=False)
    _wait_for_scanner_status(compose_stack, 403, "scanner request before override")

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
        in applied["generated_config"]["rule_overrides_conf"]
    )
    _assert_coraza_runtime_override(compose_stack, should_exist=True)
    # The runtime-file assertion proves the override reached Coraza's mount;
    # the HTTP verdict is still the user-visible contract for issue #114.
    _wait_for_scanner_status(
        compose_stack,
        200,
        "scanner request after disable override",
    )

    _api_json(
        compose_stack,
        "PATCH",
        f"/policies/{policy_id}/rules/{override['id']}",
        token=token,
        payload={"action": "enable"},
    )

    applied = _apply_config(compose_stack, token)
    assert f"SecRuleRemoveById {SCANNER_RULE_ID}" not in applied["generated_config"][
        "rule_overrides_conf"
    ]
    _assert_coraza_runtime_override(compose_stack, should_exist=False)
    _wait_for_scanner_status(compose_stack, 403, "scanner request after re-enable")


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


def _assert_coraza_runtime_override(stack: ComposeStack, *, should_exist: bool) -> None:
    result = _run(
        stack.command
        + [
            "exec",
            "-T",
            "coraza",
            "cat",
            "/runtime/current/rule-overrides.conf",
        ],
        env=stack.env,
    )
    expected = f"SecRuleRemoveById {SCANNER_RULE_ID}"
    if should_exist:
        assert expected in result.stdout
    else:
        assert expected not in result.stdout


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


def _wait_for_scanner_status(
    stack: ComposeStack,
    expected_status: int,
    description: str,
) -> None:
    deadline = time.monotonic() + RELOAD_TIMEOUT_SECONDS
    last_status: int | str = "unknown"

    while time.monotonic() < deadline:
        try:
            status, _ = _http_request(
                f"{stack.base_url}/docs",
                method="GET",
                headers={"User-Agent": SCANNER_USER_AGENT},
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
