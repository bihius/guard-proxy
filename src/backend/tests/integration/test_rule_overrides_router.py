"""Integration tests for the rule overrides router."""

from typing import Any

from fastapi.testclient import TestClient


def _create_policy(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Policy for rules",
) -> dict[str, Any]:
    """Helper that creates a policy for rule override tests."""
    resp = client.post(
        "/policies",
        headers=headers,
        json={
            "name": name,
            "description": "Policy used in rule override tests",
            "paranoia_level": 2,
            "inbound_anomaly_threshold": 5,
            "outbound_anomaly_threshold": 5,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_rule_override(
    client: TestClient,
    headers: dict[str, str],
    policy_id: int,
    *,
    rule_id: int = 942100,
    action: str = "disable",
    comment: str | None = "False positive on search form",
) -> dict[str, Any]:
    """Helper that creates a rule override for the given policy."""
    resp = client.post(
        f"/policies/{policy_id}/rules",
        headers=headers,
        json={"rule_id": rule_id, "action": action, "comment": comment},
    )
    assert resp.status_code == 201
    return resp.json()


def test_create_rule_override_admin_returns_201(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """An admin can add a rule override to an existing policy."""
    policy = _create_policy(client, admin_token)

    resp = client.post(
        f"/policies/{policy['id']}/rules",
        headers=admin_token,
        json={
            "rule_id": 942100,
            "action": "disable",
            "comment": "False positive on search form",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["policy_id"] == policy["id"]
    assert body["rule_id"] == 942100
    assert body["action"] == "disable"
    assert body["comment"] == "False positive on search form"


def test_create_rule_override_viewer_forbidden(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """A viewer cannot create a rule override."""
    policy = _create_policy(client, admin_token, name="Viewer blocked")

    resp = client.post(
        f"/policies/{policy['id']}/rules",
        headers=viewer_token,
        json={"rule_id": 942100, "action": "disable"},
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_create_rule_override_missing_policy_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Creating an override for a missing policy returns 404."""
    resp = client.post(
        "/policies/99999/rules",
        headers=admin_token,
        json={"rule_id": 942100, "action": "disable"},
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


def test_create_rule_override_duplicate_returns_409(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """The same rule_id cannot be added twice to one policy."""
    policy = _create_policy(client, admin_token, name="Duplicate policy")
    _create_rule_override(client, admin_token, policy["id"])

    resp = client.post(
        f"/policies/{policy['id']}/rules",
        headers=admin_token,
        json={"rule_id": 942100, "action": "enable"},
    )

    assert resp.status_code == 409
    assert resp.json()["detail"] == "Rule override already exists"


def test_list_rule_overrides_admin_and_viewer_return_200(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """Admins and viewers can list overrides assigned to a policy."""
    policy = _create_policy(client, admin_token, name="List policy")
    _create_rule_override(
        client, admin_token, policy["id"], rule_id=941100, action="enable"
    )
    _create_rule_override(
        client, admin_token, policy["id"], rule_id=942100, action="disable"
    )

    admin_resp = client.get(f"/policies/{policy['id']}/rules", headers=admin_token)
    viewer_resp = client.get(f"/policies/{policy['id']}/rules", headers=viewer_token)

    assert admin_resp.status_code == 200
    assert viewer_resp.status_code == 200
    assert [item["rule_id"] for item in admin_resp.json()] == [941100, 942100]
    assert [item["rule_id"] for item in viewer_resp.json()] == [941100, 942100]


def test_list_rule_overrides_missing_policy_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Listing overrides requires an existing policy."""
    resp = client.get("/policies/99999/rules", headers=admin_token)

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


def test_get_rule_override_returns_200(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """A single override can be read by both admin and viewer."""
    policy = _create_policy(client, admin_token, name="Detail policy")
    created = _create_rule_override(client, admin_token, policy["id"])

    admin_resp = client.get(
        f"/policies/{policy['id']}/rules/{created['id']}",
        headers=admin_token,
    )
    viewer_resp = client.get(
        f"/policies/{policy['id']}/rules/{created['id']}",
        headers=viewer_token,
    )

    assert admin_resp.status_code == 200
    assert viewer_resp.status_code == 200
    assert admin_resp.json()["id"] == created["id"]
    assert viewer_resp.json()["id"] == created["id"]


def test_get_rule_override_not_found_for_other_policy_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """An override from another policy cannot be read under the wrong policy ID."""
    policy_one = _create_policy(client, admin_token, name="Policy one")
    policy_two = _create_policy(client, admin_token, name="Policy two")
    created = _create_rule_override(client, admin_token, policy_one["id"])

    resp = client.get(
        f"/policies/{policy_two['id']}/rules/{created['id']}",
        headers=admin_token,
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Rule override not found"


def test_patch_rule_override_admin_partial_update(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """PATCH updates only the specified override fields."""
    policy = _create_policy(client, admin_token, name="Patch policy")
    created = _create_rule_override(client, admin_token, policy["id"])

    resp = client.patch(
        f"/policies/{policy['id']}/rules/{created['id']}",
        headers=admin_token,
        json={"action": "enable", "comment": None},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["rule_id"] == 942100
    assert body["action"] == "enable"
    assert body["comment"] is None


def test_patch_rule_override_viewer_forbidden(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """A viewer cannot edit an override."""
    policy = _create_policy(client, admin_token, name="Patch blocked")
    created = _create_rule_override(client, admin_token, policy["id"])

    resp = client.patch(
        f"/policies/{policy['id']}/rules/{created['id']}",
        headers=viewer_token,
        json={"action": "enable"},
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"


def test_patch_rule_override_duplicate_rule_id_returns_409(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """PATCH cannot change rule_id to one already used in the same policy."""
    policy = _create_policy(client, admin_token, name="Patch duplicate")
    first = _create_rule_override(client, admin_token, policy["id"], rule_id=941100)
    second = _create_rule_override(client, admin_token, policy["id"], rule_id=942100)

    resp = client.patch(
        f"/policies/{policy['id']}/rules/{second['id']}",
        headers=admin_token,
        json={"rule_id": first["rule_id"]},
    )

    assert resp.status_code == 409
    assert resp.json()["detail"] == "Rule override already exists"


def test_patch_rule_override_missing_policy_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """PATCH requires an existing policy."""
    resp = client.patch(
        "/policies/99999/rules/1",
        headers=admin_token,
        json={"action": "enable"},
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy not found"


def test_patch_rule_override_missing_override_returns_404(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """PATCH on a missing override returns 404."""
    policy = _create_policy(client, admin_token, name="Patch missing override")

    resp = client.patch(
        f"/policies/{policy['id']}/rules/99999",
        headers=admin_token,
        json={"action": "enable"},
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Rule override not found"


def test_patch_rule_override_null_rule_id_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Explicitly setting rule_id to null in PATCH returns 422."""
    policy = _create_policy(client, admin_token, name="Patch null rule_id")
    created = _create_rule_override(client, admin_token, policy["id"])

    resp = client.patch(
        f"/policies/{policy['id']}/rules/{created['id']}",
        headers=admin_token,
        json={"rule_id": None},
    )

    assert resp.status_code == 422
    assert "rule_id" in resp.json()["detail"]


def test_patch_rule_override_null_action_returns_422(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """Explicitly setting action to null in PATCH returns 422."""
    policy = _create_policy(client, admin_token, name="Patch null action")
    created = _create_rule_override(client, admin_token, policy["id"])

    resp = client.patch(
        f"/policies/{policy['id']}/rules/{created['id']}",
        headers=admin_token,
        json={"action": None},
    )

    assert resp.status_code == 422
    assert "action" in resp.json()["detail"]


def test_delete_rule_override_admin_returns_204(
    client: TestClient, admin_token: dict[str, str]
) -> None:
    """An admin can delete an override and it can no longer be fetched."""
    policy = _create_policy(client, admin_token, name="Delete policy")
    created = _create_rule_override(client, admin_token, policy["id"])

    delete_resp = client.delete(
        f"/policies/{policy['id']}/rules/{created['id']}",
        headers=admin_token,
    )
    get_resp = client.get(
        f"/policies/{policy['id']}/rules/{created['id']}",
        headers=admin_token,
    )

    assert delete_resp.status_code == 204
    assert delete_resp.text == ""
    assert get_resp.status_code == 404
    assert get_resp.json()["detail"] == "Rule override not found"


def test_delete_rule_override_viewer_forbidden(
    client: TestClient, admin_token: dict[str, str], viewer_token: dict[str, str]
) -> None:
    """A viewer cannot delete an override."""
    policy = _create_policy(client, admin_token, name="Delete blocked")
    created = _create_rule_override(client, admin_token, policy["id"])

    resp = client.delete(
        f"/policies/{policy['id']}/rules/{created['id']}",
        headers=viewer_token,
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin role required"
