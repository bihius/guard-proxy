"""Integration tests for the custom rules router."""

from typing import Any

from fastapi.testclient import TestClient


def _create_policy(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Policy for custom rules",
) -> dict[str, Any]:
    """Helper that creates a policy for custom rule tests."""
    resp = client.post(
        "/policies",
        headers=headers,
        json={
            "name": name,
            "description": "Policy used in custom rule tests",
            "paranoia_level": 2,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 5,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_custom_rule(
    client: TestClient,
    headers: dict[str, str],
    policy_id: int,
    *,
    rule_id: int = 9000001,
    phase: str = "request_headers",
    variables: str = "REQUEST_HEADERS:User-Agent",
    operator: str = "rx",
    operator_argument: str = "(?i)curl",
    actions: str = "deny,status:403",
    comment: str | None = "Block scripted clients",
    is_active: bool = True,
) -> dict[str, Any]:
    """Helper that creates a custom rule for the given policy."""
    resp = client.post(
        f"/policies/{policy_id}/custom-rules",
        headers=headers,
        json={
            "rule_id": rule_id,
            "phase": phase,
            "variables": variables,
            "operator": operator,
            "operator_argument": operator_argument,
            "actions": actions,
            "comment": comment,
            "is_active": is_active,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_create_custom_rule_admin_returns_201(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """An admin can add a custom rule to an existing policy."""
    policy = _create_policy(client, admin_token)

    resp = client.post(
        f"/policies/{policy['id']}/custom-rules",
        headers=admin_token,
        json={
            "rule_id": 9000001,
            "phase": "request_headers",
            "variables": "REQUEST_HEADERS:User-Agent",
            "operator": "rx",
            "operator_argument": "(?i)curl",
            "actions": "deny,status:403",
            "comment": "Block scripted clients",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["policy_id"] == policy["id"]
    assert body["rule_id"] == 9000001
    assert body["phase"] == "request_headers"
    assert body["variables"] == "REQUEST_HEADERS:User-Agent"
    assert body["operator"] == "rx"
    assert body["operator_argument"] == "(?i)curl"
    assert body["actions"] == "deny,status:403"
    assert body["comment"] == "Block scripted clients"
    assert body["is_active"] is True


def test_create_custom_rule_without_comment_returns_201(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """comment is optional; omitting it creates a custom rule with no comment."""
    policy = _create_policy(client, admin_token, name="No comment")

    resp = client.post(
        f"/policies/{policy['id']}/custom-rules",
        headers=admin_token,
        json={
            "rule_id": 9000001,
            "phase": "request_headers",
            "variables": "REQUEST_HEADERS:User-Agent",
            "operator": "rx",
            "operator_argument": "(?i)curl",
            "actions": "deny,status:403",
        },
    )

    assert resp.status_code == 201
    assert resp.json()["comment"] is None


def test_create_custom_rule_viewer_forbidden(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """A viewer cannot create a custom rule."""
    policy = _create_policy(client, admin_token, name="Viewer blocked")

    resp = client.post(
        f"/policies/{policy['id']}/custom-rules",
        headers=viewer_token,
        json={
            "rule_id": 9000001,
            "phase": "request_headers",
            "variables": "ARGS",
            "operator": "rx",
            "operator_argument": ".*",
            "actions": "deny",
        },
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_create_custom_rule_missing_policy_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Creating a custom rule for a missing policy returns 404."""
    resp = client.post(
        "/policies/99999/custom-rules",
        headers=admin_token,
        json={
            "rule_id": 9000001,
            "phase": "request_headers",
            "variables": "ARGS",
            "operator": "rx",
            "operator_argument": ".*",
            "actions": "deny",
        },
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


def test_create_custom_rule_id_below_range_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """A rule_id below the reserved custom rule range is rejected."""
    policy = _create_policy(client, admin_token, name="Below range")

    resp = client.post(
        f"/policies/{policy['id']}/custom-rules",
        headers=admin_token,
        json={
            "rule_id": 8999999,
            "phase": "request_headers",
            "variables": "ARGS",
            "operator": "rx",
            "operator_argument": ".*",
            "actions": "deny",
        },
    )

    assert resp.status_code == 422


def test_create_custom_rule_id_above_range_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """A rule_id above the reserved custom rule range is rejected."""
    policy = _create_policy(client, admin_token, name="Above range")

    resp = client.post(
        f"/policies/{policy['id']}/custom-rules",
        headers=admin_token,
        json={
            "rule_id": 9100000,
            "phase": "request_headers",
            "variables": "ARGS",
            "operator": "rx",
            "operator_argument": ".*",
            "actions": "deny",
        },
    )

    assert resp.status_code == 422


def test_create_custom_rule_blank_variables_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """An empty variables field is rejected by schema validation."""
    policy = _create_policy(client, admin_token, name="Blank variables")

    resp = client.post(
        f"/policies/{policy['id']}/custom-rules",
        headers=admin_token,
        json={
            "rule_id": 9000001,
            "phase": "request_headers",
            "variables": "   ",
            "operator": "rx",
            "operator_argument": ".*",
            "actions": "deny",
        },
    )

    assert resp.status_code == 422


def test_create_custom_rule_duplicate_rule_id_returns_409(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """A policy cannot contain two custom rules with the same rule_id."""
    policy = _create_policy(client, admin_token, name="Duplicate custom rule")
    _create_custom_rule(client, admin_token, policy["id"], rule_id=9000001)

    resp = client.post(
        f"/policies/{policy['id']}/custom-rules",
        headers=admin_token,
        json={
            "rule_id": 9000001,
            "phase": "request_headers",
            "variables": "ARGS",
            "operator": "rx",
            "operator_argument": ".*",
            "actions": "deny",
        },
    )

    assert resp.status_code == 409
    assert resp.json()["detail"] == (
        "A custom rule with this ID already exists in this policy."
    )


def test_list_custom_rules_admin_and_viewer_return_200(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """Admins and viewers can list custom rules assigned to a policy."""
    policy = _create_policy(client, admin_token, name="List policy")
    _create_custom_rule(client, admin_token, policy["id"], rule_id=9000001)
    _create_custom_rule(client, admin_token, policy["id"], rule_id=9000002)

    admin_resp = client.get(
        f"/policies/{policy['id']}/custom-rules", headers=admin_token
    )
    viewer_resp = client.get(
        f"/policies/{policy['id']}/custom-rules", headers=viewer_token
    )

    assert admin_resp.status_code == 200
    assert viewer_resp.status_code == 200
    assert [item["rule_id"] for item in admin_resp.json()] == [9000001, 9000002]
    assert [item["rule_id"] for item in viewer_resp.json()] == [9000001, 9000002]


def test_list_custom_rules_missing_policy_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Listing custom rules requires an existing policy."""
    resp = client.get("/policies/99999/custom-rules", headers=admin_token)

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


def test_get_custom_rule_returns_200(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """A single custom rule can be read by both admin and viewer."""
    policy = _create_policy(client, admin_token, name="Detail policy")
    created = _create_custom_rule(client, admin_token, policy["id"])

    admin_resp = client.get(
        f"/policies/{policy['id']}/custom-rules/{created['id']}",
        headers=admin_token,
    )
    viewer_resp = client.get(
        f"/policies/{policy['id']}/custom-rules/{created['id']}",
        headers=viewer_token,
    )

    assert admin_resp.status_code == 200
    assert viewer_resp.status_code == 200
    assert admin_resp.json()["id"] == created["id"]
    assert viewer_resp.json()["id"] == created["id"]


def test_get_custom_rule_not_found_for_other_policy_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """A custom rule from another policy cannot be read under the wrong policy ID."""
    policy_one = _create_policy(client, admin_token, name="Policy one")
    policy_two = _create_policy(client, admin_token, name="Policy two")
    created = _create_custom_rule(client, admin_token, policy_one["id"])

    resp = client.get(
        f"/policies/{policy_two['id']}/custom-rules/{created['id']}",
        headers=admin_token,
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Custom rule not found"


def test_patch_custom_rule_admin_partial_update(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """PATCH updates only the specified custom rule fields."""
    policy = _create_policy(client, admin_token, name="Patch policy")
    created = _create_custom_rule(client, admin_token, policy["id"])

    resp = client.patch(
        f"/policies/{policy['id']}/custom-rules/{created['id']}",
        headers=admin_token,
        json={"is_active": False, "comment": "Temporarily disabled"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["rule_id"] == 9000001
    assert body["is_active"] is False
    assert body["comment"] == "Temporarily disabled"


def test_patch_custom_rule_viewer_forbidden(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """A viewer cannot edit a custom rule."""
    policy = _create_policy(client, admin_token, name="Patch blocked")
    created = _create_custom_rule(client, admin_token, policy["id"])

    resp = client.patch(
        f"/policies/{policy['id']}/custom-rules/{created['id']}",
        headers=viewer_token,
        json={"comment": "Should not apply"},
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_patch_custom_rule_missing_policy_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """PATCH requires an existing policy."""
    resp = client.patch(
        "/policies/99999/custom-rules/1",
        headers=admin_token,
        json={"comment": "irrelevant"},
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


def test_patch_custom_rule_missing_custom_rule_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """PATCH on a missing custom rule returns 404."""
    policy = _create_policy(client, admin_token, name="Patch missing rule")

    resp = client.patch(
        f"/policies/{policy['id']}/custom-rules/99999",
        headers=admin_token,
        json={"comment": "irrelevant"},
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Custom rule not found"


def test_patch_custom_rule_null_rule_id_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Explicitly setting rule_id to null in PATCH returns 422."""
    policy = _create_policy(client, admin_token, name="Patch null rule_id")
    created = _create_custom_rule(client, admin_token, policy["id"])

    resp = client.patch(
        f"/policies/{policy['id']}/custom-rules/{created['id']}",
        headers=admin_token,
        json={"rule_id": None},
    )

    assert resp.status_code == 422
    assert "rule_id" in resp.json()["detail"]


def test_patch_custom_rule_null_variables_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Explicitly setting variables to null in PATCH returns 422."""
    policy = _create_policy(client, admin_token, name="Patch null variables")
    created = _create_custom_rule(client, admin_token, policy["id"])

    resp = client.patch(
        f"/policies/{policy['id']}/custom-rules/{created['id']}",
        headers=admin_token,
        json={"variables": None},
    )

    assert resp.status_code == 422
    assert "variables" in resp.json()["detail"]


def test_patch_custom_rule_duplicate_rule_id_returns_409(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Changing a custom rule to another rule's ID in the same policy is rejected."""
    policy = _create_policy(client, admin_token, name="Patch duplicate rule_id")
    _create_custom_rule(client, admin_token, policy["id"], rule_id=9000001)
    second_rule = _create_custom_rule(
        client, admin_token, policy["id"], rule_id=9000002
    )

    resp = client.patch(
        f"/policies/{policy['id']}/custom-rules/{second_rule['id']}",
        headers=admin_token,
        json={"rule_id": 9000001},
    )

    assert resp.status_code == 409
    assert resp.json()["detail"] == (
        "A custom rule with this ID already exists in this policy."
    )


def test_delete_custom_rule_admin_returns_204(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """An admin can delete a custom rule and it can no longer be fetched."""
    policy = _create_policy(client, admin_token, name="Delete policy")
    created = _create_custom_rule(client, admin_token, policy["id"])

    delete_resp = client.delete(
        f"/policies/{policy['id']}/custom-rules/{created['id']}",
        headers=admin_token,
    )
    get_resp = client.get(
        f"/policies/{policy['id']}/custom-rules/{created['id']}",
        headers=admin_token,
    )

    assert delete_resp.status_code == 204
    assert delete_resp.text == ""
    assert get_resp.status_code == 404
    assert get_resp.json()["detail"] == "Custom rule not found"


def test_delete_custom_rule_viewer_forbidden(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """A viewer cannot delete a custom rule."""
    policy = _create_policy(client, admin_token, name="Delete blocked")
    created = _create_custom_rule(client, admin_token, policy["id"])

    resp = client.delete(
        f"/policies/{policy['id']}/custom-rules/{created['id']}",
        headers=viewer_token,
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"
