import hmac
import json
import os
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from agentgate.managed import create_managed_app, discover_sonar

AGENT_TOKEN = "a" * 32
REVIEWER_TOKEN = "r" * 32
AGENT = {"Authorization": f"Bearer {AGENT_TOKEN}"}
REVIEWER = {"Authorization": f"Bearer {REVIEWER_TOKEN}"}


@pytest.fixture
def gate(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    with TestClient(
        create_managed_app(tmp_path / "discovery.sqlite3", root, AGENT_TOKEN, REVIEWER_TOKEN)
    ) as client:
        yield client, root


def test_empty_inventory_scan_and_role_separation(gate, monkeypatch):
    client, _ = gate
    assert client.get("/api/overview", headers=AGENT).status_code == 401
    assert client.get("/api/overview", headers=REVIEWER).json()["agents"] == []
    assert client.post("/api/discovery", headers=AGENT).status_code == 401
    monkeypatch.setattr("agentgate.managed.discover_sonar", lambda *args: "discovered")
    assert client.post("/api/discovery", headers=REVIEWER).json()["state"] == "discovered"
    assert client.get("/api/overview", headers=REVIEWER).json()["agents"][0]["name"] == "Sonar"
    assert "Sales assistant" not in client.get("/").text


def test_probe_checks_loopback_and_validates_pairing_proof(monkeypatch):
    class Probe:
        def open(self, request, timeout):
            assert request.full_url.startswith("http://127.0.0.1:5000/api/agentgate/discovery?")
            challenge = request.full_url.split("challenge=")[1]
            proof = hmac.digest(
                AGENT_TOKEN.encode(),
                f"agentgate-sonar-v1:{challenge}".encode(),
                "sha256",
            ).hex()
            return BytesIO(json.dumps({"protocol": "agentgate-sonar-v1", "proof": proof}).encode())

    monkeypatch.setattr("agentgate.managed.build_opener", lambda *_: Probe())
    assert discover_sonar(5000, AGENT_TOKEN) == "managed"
    assert discover_sonar(5000, REVIEWER_TOKEN) == "discovered"


def propose(client, **action):
    route = f"/api/proposals/{uuid4()}"
    response = client.put(route, json=action, headers=AGENT)
    assert response.status_code == 200
    return route, response.json()


def test_review_exact_request_execute_once_and_never_log_contents(gate):
    client, root = gate
    write = {"tool": "write_file", "path": "notes.txt", "content": "unlogged text"}
    route, row = propose(client, **write)
    assert row["status"] == "denied"
    assert client.post(route + "/execute", json=write, headers=AGENT).status_code == 409
    assert (
        client.put("/api/rules/write_file", json={"mode": "review"}, headers=AGENT).status_code
        == 401
    )
    client.put("/api/rules/write_file", json={"mode": "review"}, headers=REVIEWER)
    route, row = propose(client, **write)
    assert row["status"] == "pending"
    assert not (root / "notes.txt").exists()
    assert client.post(route + "/execute", json=write, headers=AGENT).status_code == 409
    assert client.post(route + "/review", json={"approve": True}, headers=AGENT).status_code == 401
    assert client.put(route, json={**write, "content": "changed"}, headers=AGENT).status_code == 409
    assert (
        client.post(route + "/review", json={"approve": True}, headers=REVIEWER).json()["status"]
        == "ready"
    )
    assert not (root / "notes.txt").exists()
    assert (
        client.post(
            route + "/execute", json={**write, "content": "changed"}, headers=AGENT
        ).status_code
        == 409
    )
    assert client.post(route + "/execute", json=write, headers=AGENT).json()["status"] == "executed"
    assert (root / "notes.txt").read_text() == write["content"]
    assert client.post(route + "/execute", json=write, headers=AGENT).status_code == 409
    assert write["content"] not in client.get("/api/overview", headers=REVIEWER).text


def test_rejection_failure_and_changed_rules_fail_closed(gate):
    client, root = gate
    read = {"tool": "read_file", "path": "notes.txt"}
    route, _ = propose(client, **read)
    assert (
        client.post(route + "/review", json={"approve": False}, headers=REVIEWER).json()["status"]
        == "rejected"
    )
    assert client.post(route + "/execute", json=read, headers=AGENT).status_code == 409
    client.put("/api/rules/read_file", json={"mode": "allow"}, headers=REVIEWER)
    route, _ = propose(client, **read)
    client.put("/api/rules/read_file", json={"mode": "deny"}, headers=REVIEWER)
    assert client.post(route + "/execute", json=read, headers=AGENT).status_code == 409
    client.put("/api/rules/read_file", json={"mode": "allow"}, headers=REVIEWER)
    route, _ = propose(client, **read)
    assert client.post(route + "/execute", json=read, headers=AGENT).json()["status"] == "failed"
    (root / "notes.txt").write_text("hello")
    route, _ = propose(client, **read)
    assert client.post(route + "/execute", json=read, headers=AGENT).json() == {
        "status": "executed",
        "result": "hello",
    }


def test_scope_refuses_private_targets_symlinks_and_hardlinks(gate, tmp_path):
    client, root = gate
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    (root / "symlink.txt").symlink_to(outside)
    os.link(outside, root / "hardlink.txt")
    client.put("/api/rules/read_file", json={"mode": "allow"}, headers=REVIEWER)
    for name in ["symlink.txt", "hardlink.txt"]:
        read = {"tool": "read_file", "path": name}
        route, _ = propose(client, **read)
        assert (
            client.post(route + "/execute", json=read, headers=AGENT).json()["status"] == "failed"
        )
    for name in ["../outside.txt", ".env", "/etc/passwd"]:
        assert (
            client.put(
                f"/api/proposals/{uuid4()}",
                json={"tool": "read_file", "path": name},
                headers=AGENT,
            ).status_code
            == 422
        )
