"""Integration tests for the rule exclusions router."""

from typing import Any

from fastapi.testclient import TestClient


def _create_policy(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Policy for exclusions",
) -> dict[str, Any]:
    """Helper that creates a policy for rule exclusion tests."""
    resp = client.post(
        "/policies",
        headers=headers,
        json={
            "name": name,
            "description": "Policy used in rule exclusion tests",
            "paranoia_level": 2,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 5,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_rule_exclusion(
    client: TestClient,
    headers: dict[str, str],
    policy_id: int,
    *,
    rule_id: int = 942100,
    target_type: str = "args",
    target_value: str = "token",
    scope_path: str | None = "/api/login",
    comment: str | None = "False positive on login token",
) -> dict[str, Any]:
    """Helper that creates a rule exclusion for the given policy."""
    resp = client.post(
        f"/policies/{policy_id}/exclusions",
        headers=headers,
        json={
            "rule_id": rule_id,
            "target_type": target_type,
            "target_value": target_value,
            "scope_path": scope_path,
            "comment": comment,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_create_rule_exclusion_admin_returns_201(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """An admin can add a rule exclusion to an existing policy."""
    policy = _create_policy(client, admin_token)

    resp = client.post(
        f"/policies/{policy['id']}/exclusions",
        headers=admin_token,
        json={
            "rule_id": 942100,
            "target_type": "args",
            "target_value": "token",
            "scope_path": "/api/login",
            "comment": "False positive on login token",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["policy_id"] == policy["id"]
    assert body["rule_id"] == 942100
    assert body["target_type"] == "args"
    assert body["target_value"] == "token"
    assert body["scope_path"] == "/api/login"
    assert body["comment"] == "False positive on login token"


def test_create_rule_exclusion_without_scope_path_returns_201(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """scope_path is optional; omitting it applies the exclusion to all paths."""
    policy = _create_policy(client, admin_token, name="No scope path")

    resp = client.post(
        f"/policies/{policy['id']}/exclusions",
        headers=admin_token,
        json={"rule_id": 942100, "target_type": "args", "target_value": "token"},
    )

    assert resp.status_code == 201
    assert resp.json()["scope_path"] is None


def test_create_rule_exclusion_viewer_forbidden(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """A viewer cannot create a rule exclusion."""
    policy = _create_policy(client, admin_token, name="Viewer blocked")

    resp = client.post(
        f"/policies/{policy['id']}/exclusions",
        headers=viewer_token,
        json={"rule_id": 942100, "target_type": "args", "target_value": "token"},
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_create_rule_exclusion_missing_policy_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Creating an exclusion for a missing policy returns 404."""
    resp = client.post(
        "/policies/99999/exclusions",
        headers=admin_token,
        json={"rule_id": 942100, "target_type": "args", "target_value": "token"},
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


def test_create_rule_exclusion_blank_target_value_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """An empty target_value is rejected by schema validation."""
    policy = _create_policy(client, admin_token, name="Blank target value")

    resp = client.post(
        f"/policies/{policy['id']}/exclusions",
        headers=admin_token,
        json={"rule_id": 942100, "target_type": "args", "target_value": "   "},
    )

    assert resp.status_code == 422


def test_list_rule_exclusions_admin_and_viewer_return_200(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """Admins and viewers can list exclusions assigned to a policy."""
    policy = _create_policy(client, admin_token, name="List policy")
    _create_rule_exclusion(client, admin_token, policy["id"], rule_id=941100)
    _create_rule_exclusion(client, admin_token, policy["id"], rule_id=942100)

    admin_resp = client.get(f"/policies/{policy['id']}/exclusions", headers=admin_token)
    viewer_resp = client.get(
        f"/policies/{policy['id']}/exclusions", headers=viewer_token
    )

    assert admin_resp.status_code == 200
    assert viewer_resp.status_code == 200
    assert [item["rule_id"] for item in admin_resp.json()] == [941100, 942100]
    assert [item["rule_id"] for item in viewer_resp.json()] == [941100, 942100]


def test_list_rule_exclusions_missing_policy_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Listing exclusions requires an existing policy."""
    resp = client.get("/policies/99999/exclusions", headers=admin_token)

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


def test_get_rule_exclusion_returns_200(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """A single exclusion can be read by both admin and viewer."""
    policy = _create_policy(client, admin_token, name="Detail policy")
    created = _create_rule_exclusion(client, admin_token, policy["id"])

    admin_resp = client.get(
        f"/policies/{policy['id']}/exclusions/{created['id']}",
        headers=admin_token,
    )
    viewer_resp = client.get(
        f"/policies/{policy['id']}/exclusions/{created['id']}",
        headers=viewer_token,
    )

    assert admin_resp.status_code == 200
    assert viewer_resp.status_code == 200
    assert admin_resp.json()["id"] == created["id"]
    assert viewer_resp.json()["id"] == created["id"]


def test_get_rule_exclusion_not_found_for_other_policy_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """An exclusion from another policy cannot be read under the wrong policy ID."""
    policy_one = _create_policy(client, admin_token, name="Policy one")
    policy_two = _create_policy(client, admin_token, name="Policy two")
    created = _create_rule_exclusion(client, admin_token, policy_one["id"])

    resp = client.get(
        f"/policies/{policy_two['id']}/exclusions/{created['id']}",
        headers=admin_token,
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Rule exclusion not found"


def test_patch_rule_exclusion_admin_partial_update(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """PATCH updates only the specified exclusion fields."""
    policy = _create_policy(client, admin_token, name="Patch policy")
    created = _create_rule_exclusion(client, admin_token, policy["id"])

    resp = client.patch(
        f"/policies/{policy['id']}/exclusions/{created['id']}",
        headers=admin_token,
        json={"scope_path": None, "comment": "No longer scoped"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["rule_id"] == 942100
    assert body["scope_path"] is None
    assert body["comment"] == "No longer scoped"


def test_patch_rule_exclusion_viewer_forbidden(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """A viewer cannot edit an exclusion."""
    policy = _create_policy(client, admin_token, name="Patch blocked")
    created = _create_rule_exclusion(client, admin_token, policy["id"])

    resp = client.patch(
        f"/policies/{policy['id']}/exclusions/{created['id']}",
        headers=viewer_token,
        json={"comment": "Should not apply"},
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_patch_rule_exclusion_missing_policy_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """PATCH requires an existing policy."""
    resp = client.patch(
        "/policies/99999/exclusions/1",
        headers=admin_token,
        json={"comment": "irrelevant"},
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


def test_patch_rule_exclusion_missing_exclusion_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """PATCH on a missing exclusion returns 404."""
    policy = _create_policy(client, admin_token, name="Patch missing exclusion")

    resp = client.patch(
        f"/policies/{policy['id']}/exclusions/99999",
        headers=admin_token,
        json={"comment": "irrelevant"},
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Rule exclusion not found"


def test_patch_rule_exclusion_null_rule_id_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Explicitly setting rule_id to null in PATCH returns 422."""
    policy = _create_policy(client, admin_token, name="Patch null rule_id")
    created = _create_rule_exclusion(client, admin_token, policy["id"])

    resp = client.patch(
        f"/policies/{policy['id']}/exclusions/{created['id']}",
        headers=admin_token,
        json={"rule_id": None},
    )

    assert resp.status_code == 422
    assert "rule_id" in resp.json()["detail"]


def test_patch_rule_exclusion_null_target_type_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Explicitly setting target_type to null in PATCH returns 422."""
    policy = _create_policy(client, admin_token, name="Patch null target_type")
    created = _create_rule_exclusion(client, admin_token, policy["id"])

    resp = client.patch(
        f"/policies/{policy['id']}/exclusions/{created['id']}",
        headers=admin_token,
        json={"target_type": None},
    )

    assert resp.status_code == 422
    assert "target_type" in resp.json()["detail"]


def test_patch_rule_exclusion_null_target_value_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Explicitly setting target_value to null in PATCH returns 422."""
    policy = _create_policy(client, admin_token, name="Patch null target_value")
    created = _create_rule_exclusion(client, admin_token, policy["id"])

    resp = client.patch(
        f"/policies/{policy['id']}/exclusions/{created['id']}",
        headers=admin_token,
        json={"target_value": None},
    )

    assert resp.status_code == 422
    assert "target_value" in resp.json()["detail"]


def test_delete_rule_exclusion_admin_returns_204(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """An admin can delete an exclusion and it can no longer be fetched."""
    policy = _create_policy(client, admin_token, name="Delete policy")
    created = _create_rule_exclusion(client, admin_token, policy["id"])

    delete_resp = client.delete(
        f"/policies/{policy['id']}/exclusions/{created['id']}",
        headers=admin_token,
    )
    get_resp = client.get(
        f"/policies/{policy['id']}/exclusions/{created['id']}",
        headers=admin_token,
    )

    assert delete_resp.status_code == 204
    assert delete_resp.text == ""
    assert get_resp.status_code == 404
    assert get_resp.json()["detail"] == "Rule exclusion not found"


def test_delete_rule_exclusion_viewer_forbidden(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """A viewer cannot delete an exclusion."""
    policy = _create_policy(client, admin_token, name="Delete blocked")
    created = _create_rule_exclusion(client, admin_token, policy["id"])

    resp = client.delete(
        f"/policies/{policy['id']}/exclusions/{created['id']}",
        headers=viewer_token,
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"
