import pytest
from fastapi.testclient import TestClient

from agentgate.app import create_app

AGENT = "test-agent-credential-long-enough"
REVIEWER = "test-reviewer-credential-long-enough"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(str(tmp_path / "audit.db"), AGENT, REVIEWER)) as client:
        yield client


def call(client, **changes):
    body = {
        "run_id": "test",
        "tool": "refunds.create",
        "arguments": {"ticket_id": "T-1001", "amount_cents": 20000},
    }
    body.update(changes)
    return client.post("/api/actions", json=body, headers=auth(AGENT))


def test_roles_are_separate(client):
    assert client.get("/api/actions").status_code == 401
    assert client.get("/api/actions", headers=auth(AGENT)).status_code == 401
    assert client.post("/api/actions", json={}, headers=auth(REVIEWER)).status_code == 401
    action = call(client).json()
    path = f"/api/actions/{action['id']}/review"
    assert client.post(path, json={"approve": True}, headers=auth(AGENT)).status_code == 401
    assert (
        client.post(path, json={"approve": True}, headers=auth(REVIEWER)).json()["outcome"]
        == "executed"
    )
    assert client.post(path, json={"approve": True}, headers=auth(REVIEWER)).status_code == 409


def test_agent_cannot_impersonate_or_override(client):
    assert call(client, agent_id="admin").status_code == 422
    assert call(client, arguments={"ticket_id": "T-1001", "amount_cents": -5}).status_code == 422
    assert client.get("/api/actions", headers=auth(REVIEWER)).json() == []


def test_denied_requests_are_audited_and_not_executed(client):
    result = call(client, tool="documents.read", arguments={"document_id": "payroll"}).json()
    assert result["outcome"] == "denied"
    assert result["result"] is None
    assert client.get("/api/actions", headers=auth(REVIEWER)).json()[0]["id"] == result["id"]


def test_refund_schema_is_strict(client):
    assert call(client, arguments={"ticket_id": "T-1001", "amount_cents": "100"}).status_code == 422


def test_static_dashboard_and_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "AgentGate" in response.text
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/health", headers={"host": "untrusted.example"}).status_code == 400


def test_credentials_must_be_distinct_and_long(tmp_path):
    with pytest.raises(RuntimeError):
        create_app(str(tmp_path / "audit.db"), "same", "same")


def test_unknown_review_and_extra_fields(client):
    path = "/api/actions/missing/review"
    assert client.post(path, json={"approve": True}, headers=auth(REVIEWER)).status_code == 404
    assert (
        client.post(
            path, json={"approve": True, "arguments": {}}, headers=auth(REVIEWER)
        ).status_code
        == 422
    )
