"""Unit tests for the certbot command the certificate flow builds.

The ACME directory matters here: without a way to point certbot somewhere
other than Let's Encrypt production, the flow can only be exercised against
real rate limits.
"""

import subprocess
from pathlib import Path

import pytest

from app.services import certbot_service
from app.services.certbot_service import CertbotService, build_certbot_command

DOMAIN = "app.example.com"
EMAIL = "ops@example.net"


def test_build_certbot_command_without_server_url() -> None:
    """No configured ACME server means certbot's own default is left in place."""
    command = build_certbot_command(
        domain=DOMAIN, email=EMAIL, port=8888, server_url=None
    )

    assert command == [
        "certbot",
        "certonly",
        "--standalone",
        "--http-01-port",
        "8888",
        "-d",
        DOMAIN,
        "--non-interactive",
        "--agree-tos",
        "-m",
        EMAIL,
        "--config-dir",
        "/tmp/certbot/config",
        "--work-dir",
        "/tmp/certbot/work",
        "--logs-dir",
        "/tmp/certbot/logs",
    ]
    assert "--server" not in command


def test_build_certbot_command_with_server_url() -> None:
    command = build_certbot_command(
        domain=DOMAIN,
        email=EMAIL,
        port=8889,
        server_url="https://localhost:14000/dir",
    )

    assert command[-2:] == ["--server", "https://localhost:14000/dir"]
    assert command[command.index("--http-01-port") + 1] == "8889"


def test_build_certbot_command_without_server_url_never_has_empty_server() -> None:
    """An empty setting must not become `--server ""`, which certbot rejects."""
    command = build_certbot_command(
        domain=DOMAIN, email=EMAIL, port=8888, server_url=""
    )

    assert "--server" not in command


@pytest.mark.parametrize(
    "server_url",
    [None, "https://localhost:14000/dir"],
)
def test_provision_cert_uses_the_configured_acme_server(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, server_url: str | None
) -> None:
    """provision_cert passes the configured directory through to certbot."""
    captured: dict[str, list[str]] = {}

    def fake_run(
        cmd: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        live_dir = tmp_path / "live" / DOMAIN
        live_dir.mkdir(parents=True)
        (live_dir / "fullchain.pem").write_text("CERT")
        (live_dir / "privkey.pem").write_text("KEY")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(certbot_service, "_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(certbot_service.subprocess, "run", fake_run)
    monkeypatch.setattr(certbot_service.settings, "acme_server_url", server_url)

    cert_pem, key_pem = CertbotService(port=8888).provision_cert(DOMAIN, EMAIL)

    assert (cert_pem, key_pem) == ("CERT", "KEY")
    if server_url is None:
        assert "--server" not in captured["cmd"]
    else:
        assert captured["cmd"][-2:] == ["--server", server_url]


def test_provision_cert_reports_missing_certificate_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """certbot exiting 0 without writing the PEMs is an error, not a silent pass."""

    def fake_run(
        cmd: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(certbot_service, "_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(certbot_service.subprocess, "run", fake_run)

    with pytest.raises(certbot_service.CertbotError, match="not found"):
        CertbotService().provision_cert(DOMAIN, EMAIL)
