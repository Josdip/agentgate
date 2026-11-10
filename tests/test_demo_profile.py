from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from agentgate.app import create_app
from agentgate.policy import ToolCall, tool_permissions
from agentgate.profile import ProfileUpdate
from agentgate.scenarios import scenarios
from agentgate.store import Store

AGENT = "test-agent-credential-long-enough"
REVIEWER = "test-reviewer-credential-long-enough"


def auth(token=REVIEWER):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(str(tmp_path / "audit.db"), AGENT, REVIEWER)) as client:
        yield client


def update(revision=1):
    return {
        "revision": revision,
        "display_name": "Customer support",
        "description": "Demo agent",
        "model_connections": [{"provider": "Example provider", "model": "example-model"}],
    }


def test_each_of_exactly_six_scenarios_creates_one_action(client):
    listed = client.get("/api/demo/scenarios", headers=auth()).json()
    assert len(listed) == 6
    assert len({item["id"] for item in listed}) == 6
    for index, item in enumerate(listed, 1):
        response = client.post(f"/api/demo/scenarios/{item['id']}/run", headers=auth())
        assert response.status_code == 201
        result = response.json()
        assert result["matched"]
        assert result["action"]["outcome"] == item["expected"]
        assert result["action"]["agent_id"] == "support-agent"
        assert len(client.get("/api/actions", headers=auth()).json()) == index
    profile = client.get("/api/agent", headers=auth()).json()
    assert profile["activity"]["total_actions"] == 6
    assert profile["activity"]["denied"] == 3
    assert profile["activity"]["pending"] == 1
    assert profile["activity"]["executed"] == 2
    assert profile["activity"]["last_seen"]


@pytest.mark.parametrize("token", [None, AGENT])
def test_demo_and_profile_require_reviewer(client, token):
    headers = auth(token) if token else {}
    assert client.get("/api/demo/scenarios", headers=headers).status_code == 401
    assert client.post("/api/demo/scenarios/small-refund/run", headers=headers).status_code == 401
    assert client.get("/api/agent", headers=headers).status_code == 401
    assert client.put("/api/agent", json=update(), headers=headers).status_code == 401


def test_demo_cannot_override_request_or_run_unknown_scenario(client):
    assert client.post("/api/demo/scenarios/missing/run", headers=auth()).status_code == 404
    assert (
        client.post(
            "/api/demo/scenarios/small-refund/run", json={"amount_cents": 1}, headers=auth()
        ).status_code
        == 422
    )
    assert client.get("/api/actions", headers=auth()).json() == []


def test_demo_approval_remains_separate_and_updates_profile(client):
    action = client.post("/api/demo/scenarios/large-refund/run", headers=auth()).json()["action"]
    assert action["outcome"] == "pending" and action["result"] is None
    response = client.post(
        f"/api/actions/{action['id']}/review", json={"approve": True}, headers=auth()
    )
    assert response.json()["result"]["amount_cents"] == 25000
    profile = client.get("/api/agent", headers=auth()).json()
    assert profile["activity"]["pending"] == 0
    assert profile["activity"]["executed"] == 1


def test_profile_update_is_versioned_and_rejects_privilege_fields(client):
    initial = client.get("/api/agent", headers=auth()).json()
    assert initial["model_connections"] == []
    assert initial["tools"] == tool_permissions()
    assert initial["permissions"]["can_review_actions"] is False
    assert (
        client.put(
            "/api/agent",
            json={**update(), "permissions": {"can_review_actions": True}},
            headers=auth(),
        ).status_code
        == 422
    )
    result = client.put("/api/agent", json=update(), headers=auth()).json()
    assert result["revision"] == 2
    assert result["model_connections"][0]["verification"] == "unverified"
    assert result["history"][0]["changed_by"] == "local-reviewer"
    assert result["history"][1]["metadata"]["model_connections"] == []
    assert client.put("/api/agent", json=update(), headers=auth()).status_code == 409


@pytest.mark.parametrize(
    "connections",
    [
        [{"provider": "Test", "model": "x", "api_key": "never-store"}],
        [{"provider": "Test", "model": "x"}] * 2,
        [{"provider": "Test", "model": ""}],
        [{"provider": "Test", "model": "x"}] * 11,
    ],
)
def test_invalid_connection_inventory_is_rejected(client, connections):
    assert (
        client.put(
            "/api/agent", json={**update(), "model_connections": connections}, headers=auth()
        ).status_code
        == 422
    )
    assert client.get("/api/agent", headers=auth()).json()["revision"] == 1


def test_profile_survives_restart_and_preserves_old_actions(tmp_path):
    path = str(tmp_path / "audit.db")
    store = Store(path)
    store.submit(
        ToolCall(
            run_id="old-run", tool="documents.read", arguments={"document_id": "refund-policy"}
        )
    )
    store.update_profile(ProfileUpdate.model_validate(update()))
    restarted = Store(path)
    profile = restarted.profile()
    assert profile["revision"] == 2
    assert profile["display_name"] == "Customer support"
    assert len(profile["history"]) == 2
    assert profile["activity"]["total_actions"] == 1
    assert restarted.list()[0]["run_id"] == "old-run"


def test_concurrent_profile_updates_reject_lost_update(tmp_path):
    store = Store(str(tmp_path / "audit.db"))

    def save(_):
        try:
            store.update_profile(ProfileUpdate.model_validate(update()))
            return "saved"
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, range(2))) == ["conflict", "saved"]
    assert store.profile()["revision"] == 2
    assert len(store.profile()["history"]) == 2


def test_scenario_catalog_is_not_mutable_between_requests():
    catalog = scenarios()
    catalog[0]["arguments"]["document_id"] = "payroll"
    assert scenarios()[0]["arguments"]["document_id"] == "refund-policy"
