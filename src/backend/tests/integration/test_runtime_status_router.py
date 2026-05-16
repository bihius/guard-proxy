from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.runtime_operation import (
    RuntimeOperation,
    RuntimeOperationStatus,
    RuntimeOperationType,
)
from app.models.vhost import VHost


def test_runtime_status_requires_auth(client: TestClient) -> None:
    response = client.get("/runtime/status")

    assert response.status_code == 401


def test_runtime_status_allows_viewer(
    client: TestClient,
    viewer_token: dict[str, str],
) -> None:
    response = client.get("/runtime/status", headers=viewer_token)

    assert response.status_code == 200


def test_runtime_status_returns_never_deployed_for_empty_state(
    client: TestClient,
    admin_token: dict[str, str],
) -> None:
    response = client.get("/runtime/status", headers=admin_token)

    assert response.status_code == 200
    body = response.json()
    assert body["frontend_contract_version"] == "1"
    assert body["deployment_state"] == "never_deployed"
    assert body["generated_config"]["can_generate"] is True
    assert len(body["generated_config"]["checksum"]) == 64
    assert body["latest_validation"] is None
    assert body["latest_reload"] is None


def test_runtime_status_returns_latest_validation_and_reload(
    client: TestClient,
    admin_token: dict[str, str],
    db: Session,
) -> None:
    db.add(
        RuntimeOperation(
            operation_type=RuntimeOperationType.validation,
            status=RuntimeOperationStatus.success,
            config_checksum="1" * 64,
            message="Config validated successfully",
        )
    )
    db.add(
        RuntimeOperation(
            operation_type=RuntimeOperationType.reload,
            status=RuntimeOperationStatus.success,
            config_checksum="2" * 64,
            message="HAProxy reloaded",
        )
    )
    db.commit()

    response = client.get("/runtime/status", headers=admin_token)

    assert response.status_code == 200
    body = response.json()
    assert body["deployment_state"] == "deployed"
    assert body["latest_validation"]["status"] == "success"
    assert body["latest_validation"]["message"] == "Config validated successfully"
    assert body["latest_reload"]["status"] == "success"
    assert body["latest_reload"]["message"] == "HAProxy reloaded"


def test_runtime_status_reports_generation_error_for_invalid_vhost_data(
    client: TestClient,
    admin_token: dict[str, str],
    db: Session,
) -> None:
    # This simulates invalid persisted data bypassing API validation.
    db.add(
        VHost(
            domain="broken.example.com",
            backend_url="http://",
            is_active=True,
            ssl_enabled=False,
            policy_id=None,
        )
    )
    db.commit()

    response = client.get("/runtime/status", headers=admin_token)

    assert response.status_code == 200
    body = response.json()
    assert body["generated_config"]["can_generate"] is False
    assert "missing host" in body["generated_config"]["error"]
