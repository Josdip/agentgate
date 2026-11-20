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


def test_discovery_requires_explicit_enrollment_and_active_launcher(tmp_path):
    class Launcher:
        url = "http://127.0.0.1:5002"
        active = False

        def discover(self):
            return True

        def running(self):
            return self.active

        def enroll(self):
            self.active = True

        def stop(self):
            self.active = False

    launcher = Launcher()
    root = tmp_path / "project"
    root.mkdir()
    with TestClient(
        create_managed_app(
            tmp_path / "audit.sqlite3", root, AGENT_TOKEN, REVIEWER_TOKEN, launcher=launcher
        )
    ) as client:
        assert client.post("/api/enrollment", headers=REVIEWER).status_code == 409
        assert client.post("/api/discovery", headers=REVIEWER).json()["state"] == "discovered"
        assert not launcher.active
        assert client.post("/api/enrollment", headers=AGENT).status_code == 401
        assert (
            client.put(
                f"/api/proposals/{uuid4()}",
                json={"tool": "read_file", "path": "notes.txt"},
                headers=AGENT,
            ).status_code
            == 403
        )
        assert client.post("/api/enrollment", headers=REVIEWER).json() == {
            "state": "managed",
            "url": launcher.url,
        }
        assert launcher.active
        assert (
            client.get("/api/overview", headers=REVIEWER).json()["agents"][0]["state"] == "managed"
        )
        assert 'id="theme-toggle"' in client.get("/agents").text
        assert client.get("/static/theme.js").status_code == 200
    assert not launcher.active


def test_first_run_link_is_one_use(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    with TestClient(
        create_managed_app(
            tmp_path / "data.sqlite3",
            project,
            AGENT_TOKEN,
            REVIEWER_TOKEN,
            first_run_code="valid-code",
        )
    ) as client:
        route = "/api/first-run/connection"
        assert client.post(route, json={"code": "bad-code"}).status_code == 401
        assert client.post(route, json={"code": "valid-code"}).json() == {"token": REVIEWER_TOKEN}
        assert client.post(route, json={"code": "valid-code"}).status_code == 401


def test_invalid_tool_request_is_recorded_without_untrusted_values(gate):
    client, _ = gate
    request_id = uuid4()
    url = f"/api/proposals/{request_id}"
    write = {"tool": "write_file", "path": "/outside/private.txt", "content": "private text"}
    assert client.put(url, json=write, headers=REVIEWER).status_code in {401, 422}
    assert client.get("/api/overview", headers=REVIEWER).json()["activity"] == []
    assert client.put(url, json=write, headers=AGENT).status_code == 422
    rows = client.get("/api/overview", headers=REVIEWER).json()["activity"]
    assert [(row["tool"], row["status"], row["decision"]) for row in rows] == [
        ("write_file", "denied", "invalid request")
    ]
    assert "private" not in str(rows)


def test_chrome_one_use_code_can_report_only_inventory(gate):
    client, _ = gate
    code_route = "/api/connectors/chrome/code"
    observation_route = "/api/connectors/chrome/observation"
    assert client.post(code_route, headers=AGENT).status_code == 401
    code = client.post(code_route, headers=REVIEWER).json()["code"]
    discovery = {"Authorization": f"Bearer {code}"}
    assert client.get("/api/overview", headers=discovery).status_code == 401
    assert (
        client.post(
            observation_route, headers=discovery, json={"service": "chatgpt", "cookies": "secret"}
        ).status_code
        == 422
    )
    assert (
        client.post(observation_route, headers=discovery, json={"service": "chatgpt"}).status_code
        == 200
    )
    assert (
        client.post(observation_route, headers=discovery, json={"service": "chatgpt"}).status_code
        == 401
    )
    agents = client.get("/api/overview", headers=REVIEWER).json()["external_agents"]
    assert [(agent["connector"], agent["name"], agent["provider_status"]) for agent in agents] == [
        ("chrome", "ChatGPT", "Tab observed")
    ]


def test_bedrock_refresh_is_scoped_and_does_not_change_sonar(gate, monkeypatch):
    client, _ = gate
    route = "/api/connectors/bedrock/discovery"
    limits = []
    names = [("ABCDEF1234", "Example", "PREPARED")]

    def scan(region, profile):
        limits.append((region, profile))
        return "123456789012", list(names)

    monkeypatch.setattr("agentgate.managed.bedrock_agents", scan)
    assert client.post(route, json={"region": "us-east-1"}, headers=AGENT).status_code == 401
    assert (
        client.post(
            route, json={"region": "us-east-1", "profile": "--debug"}, headers=REVIEWER
        ).status_code
        == 422
    )
    assert client.post(
        route, json={"region": "us-east-1", "profile": "inventory"}, headers=REVIEWER
    ).json() == {"count": 1}
    assert client.post(route, json={"region": "us-west-2"}, headers=REVIEWER).json() == {"count": 1}
    names.clear()
    assert client.post(route, json={"region": "us-east-1"}, headers=REVIEWER).json() == {"count": 0}
    data = client.get("/api/overview", headers=REVIEWER).json()
    assert list(data["agents"]) == []
    assert len(data["rules"]) == 2
    assert len(data["external_agents"]) == 1
    assert data["external_agents"][0]["scope"] == "123456789012 · us-west-2"
    assert limits == [("us-east-1", "inventory"), ("us-west-2", ""), ("us-east-1", "")]


def test_browser_discover_enroll_report_and_revoke(gate):
    client, _ = gate
    prefix = "/api/connectors/chrome"
    observation = {"service": "chatgpt"}
    assert client.post(prefix + "/enrollment-code", headers=REVIEWER).status_code == 409
    code = client.post(prefix + "/code", headers=REVIEWER).json()["code"]
    assert (
        client.post(
            prefix + "/observation", headers={"Authorization": f"Bearer {code}"}, json=observation
        ).status_code
        == 200
    )
    assert client.post(prefix + "/enrollment-code", headers=AGENT).status_code == 401
    code = client.post(prefix + "/enrollment-code", headers=REVIEWER).json()["code"]
    auth = {"Authorization": f"Bearer {code}"}
    credential = client.post(prefix + "/enrollment", headers=auth, json=observation).json()[
        "credential"
    ]
    assert client.post(prefix + "/enrollment", headers=auth, json=observation).status_code == 401
    auth = {"Authorization": f"Bearer {credential}"}
    report = client.post(prefix + "/report", headers=auth, json=observation)
    assert report.status_code == 200
    row = client.get("/api/overview", headers=REVIEWER).json()["external_agents"][0]
    assert row["scanned"] == report.json()["reported_at"]
    assert row["provider_status"] == "Enrolled report received"
    assert client.get("/api/overview", headers=auth).status_code == 401
    assert client.get("/api/overview", headers=REVIEWER).json()["external_agents"][0]["enrolled"]
    assert client.delete(prefix + "/enrollment", headers=REVIEWER).status_code == 200
    assert client.post(prefix + "/report", headers=auth, json=observation).status_code == 401


def test_bedrock_demo_enrollment_is_labeled_and_never_calls_aws(tmp_path, monkeypatch):
    def forbidden(*args):
        pytest.fail("Fixture must never contact AWS")

    monkeypatch.setattr("agentgate.managed.bedrock_agents", forbidden)
    app = create_managed_app(
        tmp_path / "test.sqlite3", tmp_path, AGENT_TOKEN, REVIEWER_TOKEN, bedrock_fixture=True
    )
    with TestClient(app) as client:
        route = "/api/connectors/bedrock"
        request = {
            "region": "us-east-1",
            "scope": "Demo fixture · us-east-1",
            "agent_id": "DEMOAGENT1",
        }
        assert client.post(route + "/enrollment", headers=REVIEWER, json=request).status_code == 409
        assert (
            client.post(
                route + "/discovery", headers=REVIEWER, json={"region": "us-east-1"}
            ).status_code
            == 200
        )
        assert client.post(route + "/enrollment", headers=REVIEWER, json=request).status_code == 200
        discovered = client.get("/api/overview", headers=REVIEWER).json()["external_agents"][0]
        assert (discovered["connector"], discovered["enrolled"]) == ("bedrock-fixture", 1)
        assert (
            client.request(
                "DELETE", route + "/enrollment", headers=REVIEWER, json=request
            ).status_code
            == 200
        )
        assert not client.get("/api/overview", headers=REVIEWER).json()["external_agents"][0][
            "enrolled"
        ]


def test_direct_project_commands_are_bounded():
    from agentgate.sonar_runtime import project_command

    assert project_command("Read /project/welcome.txt and tell me what it says.") == (
        "read_file",
        {"path": "/project/welcome.txt"},
    )
    assert project_command('Write "hello" to review-test.txt') == (
        "write_file",
        {"path": "review-test.txt", "content": "hello"},
    )
    assert project_command("Read ../../secret.txt") is None
    assert project_command("Read welcome.txt then delete it") is None


def test_activity_retains_review_evidence_after_execution(gate):
    client, _ = gate
    action = {"tool": "read_file", "path": "missing.txt"}
    route, _ = propose(client, **action)
    assert (
        client.post(route + "/review", json={"approve": True}, headers=REVIEWER).status_code == 200
    )
    assert (
        client.post(route + "/review", json={"approve": False}, headers=REVIEWER).status_code == 409
    )
    assert client.post(route + "/execute", json=action, headers=AGENT).json()["status"] == "failed"
    row = client.get("/api/overview", headers=REVIEWER).json()["activity"][0]
    assert row["reviewer"] == "local-reviewer"
    assert row["review_decision"] == "approved"
    assert row["reviewed_at"] >= row["created"]
    assert row["status"] == "failed"
