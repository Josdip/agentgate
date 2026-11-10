import pytest
from fastapi.testclient import TestClient

from agentgate.app import create_app

AGENT = "test-agent-credential-long-enough"
REVIEWER = "test-reviewer-credential-long-enough"
ORIGIN = "http://127.0.0.1"
HEADERS = {"Origin": ORIGIN, "X-AgentGate-Demo": "browser", "Sec-Fetch-Site": "same-origin"}


def app(tmp_path, demo=True):
    return create_app(str(tmp_path / "audit.db"), AGENT, REVIEWER, demo_mode=demo)


def browser(application, address="127.0.0.1"):
    return TestClient(application, base_url=ORIGIN, client=(address, 50000))


def test_factory_keeps_authentication_required_by_default(tmp_path):
    with browser(app(tmp_path, False)) as client:
        assert client.get("/api/access-mode").json() == {"mode": "authenticated"}
        assert client.post("/api/demo/session", headers=HEADERS).status_code == 404
        assert client.get("/api/agents").status_code == 401


def test_local_browser_gets_http_only_session_without_any_token_entry(tmp_path):
    with browser(app(tmp_path)) as client:
        response = client.post("/api/demo/session", headers=HEADERS)
        assert response.status_code == 200
        assert response.json() == {"mode": "local-demo"}
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie
        assert "agentgate_demo" not in response.text
        assert client.get("/api/agents", headers=HEADERS).status_code == 200
        result = client.post("/api/demo/scenarios/large-refund/run", headers=HEADERS)
        assert result.json()["action"]["outcome"] == "pending"
        action_id = result.json()["action"]["id"]
        assert (
            client.post(
                f"/api/actions/{action_id}/review", json={"approve": False}, headers=HEADERS
            ).json()["outcome"]
            == "rejected"
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"Origin": "http://attacker.invalid"},
        {"Origin": "null"},
        {"Origin": "http://127.0.0.1:9999"},
        {"Origin": None},
        {"X-AgentGate-Demo": None},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_bootstrap_rejects_missing_or_cross_origin_headers(tmp_path, changes):
    headers = {**HEADERS, **changes}
    headers = {key: value for key, value in headers.items() if value is not None}
    with browser(app(tmp_path)) as client:
        assert client.post("/api/demo/session", headers=headers).status_code == 403
        assert client.get("/api/agents", headers=HEADERS).status_code == 401


def test_remote_client_cannot_bootstrap_or_use_a_stolen_demo_cookie(tmp_path):
    application = app(tmp_path)
    with browser(application) as local:
        local.post("/api/demo/session", headers=HEADERS)
        cookie = local.cookies.get("agentgate_demo")
    with browser(application, "203.0.113.10") as remote:
        forged = {**HEADERS, "X-Forwarded-For": "127.0.0.1"}
        assert remote.post("/api/demo/session", headers=forged).status_code == 403
        assert (
            remote.get(
                "/api/agents", headers={**forged, "Cookie": f"agentgate_demo={cookie}"}
            ).status_code
            == 403
        )


def test_cookie_mutations_require_origin_and_custom_header(tmp_path):
    with browser(app(tmp_path)) as client:
        client.post("/api/demo/session", headers=HEADERS)
        for headers in (
            {},
            {"X-AgentGate-Demo": "browser"},
            {**HEADERS, "Origin": "http://attacker.invalid"},
        ):
            assert (
                client.post("/api/demo/scenarios/large-refund/run", headers=headers).status_code
                == 403
            )
        assert client.get("/api/overview", headers=HEADERS).json()["total"] == 0


def test_agent_credentials_never_borrow_the_browser_reviewer_session(tmp_path):
    with browser(app(tmp_path)) as client:
        client.post("/api/demo/session", headers=HEADERS)
        agent_headers = {**HEADERS, "Authorization": f"Bearer {AGENT}"}
        assert client.get("/api/agents", headers=agent_headers).status_code == 401
        assert (
            client.post("/api/demo/scenarios/large-refund/run", headers=agent_headers).status_code
            == 401
        )
        assert (
            client.post(
                "/api/agents/support-agent/rules", json={}, headers=agent_headers
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/actions",
                json={
                    "run_id": "x",
                    "tool": "documents.read",
                    "arguments": {"document_id": "refund-policy"},
                },
                headers=HEADERS,
            ).status_code
            == 401
        )


def test_forged_and_previous_process_cookies_are_rejected(tmp_path):
    application = app(tmp_path)
    with browser(application) as client:
        assert (
            client.get(
                "/api/agents", headers={**HEADERS, "Cookie": "agentgate_demo=forged"}
            ).status_code
            == 401
        )
        client.post("/api/demo/session", headers=HEADERS)
        cookie = client.cookies.get("agentgate_demo")
    with browser(app(tmp_path)) as restarted:
        assert (
            restarted.get(
                "/api/agents", headers={**HEADERS, "Cookie": f"agentgate_demo={cookie}"}
            ).status_code
            == 401
        )
        assert restarted.post("/api/demo/session", headers=HEADERS).status_code == 200
        assert restarted.get("/api/agents", headers=HEADERS).status_code == 200


def test_cookie_cannot_enable_reviewer_access_when_demo_mode_is_off(tmp_path):
    with browser(app(tmp_path)) as demo:
        demo.post("/api/demo/session", headers=HEADERS)
        cookie = demo.cookies.get("agentgate_demo")
    with browser(app(tmp_path, False)) as service:
        assert (
            service.get(
                "/api/agents", headers={**HEADERS, "Cookie": f"agentgate_demo={cookie}"}
            ).status_code
            == 401
        )
        assert (
            service.get("/api/agents", headers={"Authorization": f"Bearer {REVIEWER}"}).status_code
            == 200
        )


def test_demo_mode_requires_an_explicit_boolean(tmp_path):
    with pytest.raises(TypeError, match="explicit boolean"):
        create_app(str(tmp_path / "audit.db"), AGENT, REVIEWER, demo_mode="false")
