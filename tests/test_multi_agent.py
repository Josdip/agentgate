import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from agentgate.app import create_app
from agentgate.policy import ToolCall
from agentgate.registry import AGENTS
from agentgate.scenarios import scenarios
from agentgate.store import Store

SUPPORT = "support-agent-secret-long-enough"
SALES = "sales-agent-secret-long-enough"
FINANCE = "finance-agent-secret-long-enough"
REVIEWER = "reviewer-secret-long-enough"


def auth(token=REVIEWER):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(tmp_path):
    with TestClient(
        create_app(
            str(tmp_path / "audit.db"),
            SUPPORT,
            REVIEWER,
            agent_tokens={"sales-agent": SALES, "finance-agent": FINANCE},
        )
    ) as client:
        yield client


def test_all_fourteen_cases_have_correct_identity_and_policy(client):
    catalog = client.get("/api/demo/scenarios", headers=auth()).json()
    assert len(catalog) == 14
    assert {agent: len(scenarios(agent)) for agent in AGENTS} == {
        "support-agent": 6,
        "sales-agent": 4,
        "finance-agent": 4,
    }
    for case in catalog:
        response = client.post(f"/api/demo/scenarios/{case['id']}/run", headers=auth())
        assert response.status_code == 201
        result = response.json()
        assert result["matched"], case["id"]
        assert result["action"]["agent_id"] == case["agent_id"]
    assert client.get("/api/overview", headers=auth()).json()["total"] == 14
    assert len(client.get("/api/overview", headers=auth()).json()["recent"]) == 3


def test_credential_identity_enforces_agent_scope(client):
    body = {
        "run_id": "test",
        "tool": "refunds.create",
        "arguments": {"ticket_id": "T-1001", "amount_cents": 100},
    }
    response = client.post("/api/actions", json=body, headers=auth(SALES)).json()
    assert response["agent_id"] == "sales-agent"
    assert response["outcome"] == "denied"
    assert response["result"] is None
    body = {
        "run_id": "test",
        "tool": "messages.send",
        "arguments": {"destination": "sales-inbox", "message": "test"},
    }
    assert (
        client.post("/api/actions", json=body, headers=auth(SUPPORT)).json()["outcome"] == "denied"
    )
    assert (
        client.post("/api/actions", json=body, headers=auth(SALES)).json()["outcome"] == "executed"
    )
    assert (
        client.post(
            "/api/actions", json={**body, "agent_id": "support-agent"}, headers=auth(SALES)
        ).status_code
        == 422
    )


def test_finance_approvals_use_stored_payment(client):
    action = client.post("/api/demo/scenarios/finance-large-payment/run", headers=auth()).json()[
        "action"
    ]
    path = f"/api/actions/{action['id']}/review"
    assert client.post(path, json={"approve": True}, headers=auth(FINANCE)).status_code == 401
    result = client.post(path, json={"approve": True}, headers=auth()).json()
    assert result["result"] == {"amount_cents": 250000, "vendor_id": "V-1001", "simulated": True}
    assert client.post(path, json={"approve": True}, headers=auth()).status_code == 409


def test_profiles_edit_independently_and_hide_from_agents(client):
    listed = client.get("/api/agents", headers=auth()).json()
    assert {item["agent_id"] for item in listed} == set(AGENTS)
    assert client.get("/api/agents", headers=auth(SALES)).status_code == 401
    update = {
        "revision": 1,
        "display_name": "New sales name",
        "description": "Team assistant",
        "model_connections": [],
    }
    assert (
        client.put("/api/agents/sales-agent", json=update, headers=auth()).json()["revision"] == 2
    )
    assert client.get("/api/agents/support-agent", headers=auth()).json()["revision"] == 1
    assert client.get("/api/agents/finance-agent", headers=auth()).json()["revision"] == 1
    assert client.get("/api/agents/missing", headers=auth()).status_code == 404


def test_cursor_pagination_is_bounded_and_stable_with_new_arrivals(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    store.submit(
        ToolCall(
            run_id="original", tool="documents.read", arguments={"document_id": "refund-policy"}
        )
    )
    with store.connection() as db:
        db.execute(
            """INSERT INTO actions (id,created_at,agent_id,run_id,tool,arguments,outcome,rule,reason,risk,result,reviewed_at,reviewer_id) SELECT 'seed-'||value,created_at,agent_id,'seed-'||value,
            tool,arguments,outcome,rule,reason,risk,result,reviewed_at,reviewer_id
            FROM actions CROSS JOIN json_each(?)""",
            (json.dumps(list(range(1000))),),
        )
    first = store.activity(limit=20)
    assert first["total"] == 1001 and len(first["items"]) == 20
    seen = {action["id"] for action in first["items"]}
    store.submit(
        ToolCall(
            run_id="new-arrival", tool="documents.read", arguments={"document_id": "refund-policy"}
        )
    )
    cursor = first["next_cursor"]
    while cursor:
        page = store.activity(before=cursor, limit=100)
        ids = {action["id"] for action in page["items"]}
        assert not (seen & ids)
        seen |= ids
        cursor = page["next_cursor"]
    assert len(seen) == 1001
    assert store.overview()["total"] == 1002
    assert store.profile()["activity"]["total_actions"] == 1002


def test_activity_filters_and_validation(client):
    for case in scenarios():
        client.post(f"/api/demo/scenarios/{case['id']}/run", headers=auth())
    page = client.get(
        "/api/activity?agent_id=sales-agent&outcome=denied&risk=high&limit=1", headers=auth()
    ).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    assert page["next_cursor"]
    assert all(item["agent_id"] == "sales-agent" for item in page["items"])
    assert client.get("/api/activity?search=payments.create", headers=auth()).json()["total"] == 3
    assert client.get("/api/activity?search=%25", headers=auth()).json()["total"] == 0
    assert client.get("/api/activity?limit=1000", headers=auth()).status_code == 422
    assert client.get("/api/activity?before=-1", headers=auth()).status_code == 422
    assert client.get("/api/activity?outcome=invalid", headers=auth()).status_code == 422
    assert client.get("/api/activity?agent_id=unknown", headers=auth()).status_code == 404
    assert client.get("/api/activity", headers=auth(FINANCE)).status_code == 401


def test_existing_data_and_profile_edits_survive_registry_upgrade(tmp_path):
    path = str(tmp_path / "audit.db")
    store = Store(path)
    action = store.submit(
        ToolCall(run_id="legacy", tool="documents.read", arguments={"document_id": "refund-policy"})
    )
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM agent_profiles WHERE agent_id!='support-agent'")
        db.execute("DELETE FROM profile_history WHERE agent_id!='support-agent'")
        db.execute(
            "UPDATE agent_profiles SET metadata=json_set(metadata,'$.display_name','Existing custom name') WHERE agent_id='support-agent'"
        )
    upgraded = Store(path)
    assert len(upgraded.directory()) == 3
    assert upgraded.profile()["display_name"] == "Existing custom name"
    assert upgraded.list()[0]["id"] == action["id"]


def test_page_routes_and_duplicate_credentials(client, tmp_path):
    for path in ("/", "/agents", "/agents/sales-agent", "/activity"):
        assert client.get(path).status_code == 200
    with pytest.raises(RuntimeError):
        create_app(
            str(tmp_path / "bad.db"), SUPPORT, REVIEWER, agent_tokens={"sales-agent": SUPPORT}
        )
