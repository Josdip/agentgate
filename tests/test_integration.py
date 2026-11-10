import io
from urllib.error import HTTPError, URLError

import pytest
from fastapi.testclient import TestClient

from agentgate.app import create_app
from agentgate.client import GatewayClient, ProposedAction, run_agent
from examples.real_agent_demo import main

AGENT = "test-agent-credential-long-enough"
REVIEWER = "test-reviewer-credential-long-enough"


def test_adapter_requests_are_governed_and_pause_on_approval(tmp_path, monkeypatch):
    with TestClient(create_app(str(tmp_path / "audit.db"), AGENT, REVIEWER)) as api:
        gateway = GatewayClient(AGENT)

        def transport(request, timeout):
            response = api.post(
                "/api/actions",
                content=request.data,
                headers={
                    "Authorization": request.get_header("Authorization"),
                    "Content-Type": "application/json",
                },
            )
            assert response.status_code == 201
            return io.BytesIO(response.content)

        monkeypatch.setattr(gateway.opener, "open", transport)

        class Adapter:
            calls = 0

            def next_action(self, observations):
                self.calls += 1
                if not observations:
                    return ProposedAction(
                        tool="documents.read", arguments={"document_id": "payroll"}
                    )
                assert observations[0]["outcome"] == "denied"
                return ProposedAction(
                    tool="refunds.create", arguments={"ticket_id": "T-1001", "amount_cents": 25000}
                )

        adapter = Adapter()
        outcomes = run_agent(adapter, gateway)
        assert [action["outcome"] for action in outcomes] == ["denied", "pending"]
        assert adapter.calls == 2
        assert all(action["run_id"] == gateway.run_id for action in outcomes)
        assert all(action["result"] is None for action in outcomes)
        assert (
            len(api.get("/api/actions", headers={"Authorization": f"Bearer {REVIEWER}"}).json())
            == 2
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://127.0.0.1@evil.invalid",
        "http://localhost/path",
        "http://localhost?token=x",
    ],
)
def test_showcase_credentials_cannot_be_sent_to_external_gateway(url):
    with pytest.raises(ValueError):
        GatewayClient(AGENT, base_url=url)


def test_gateway_failure_stops_adapter_without_fallback_execution(monkeypatch):
    gateway = GatewayClient(AGENT)

    def unavailable(*args, **kwargs):
        raise URLError("offline")

    monkeypatch.setattr(gateway.opener, "open", unavailable)

    class Adapter:
        calls = 0

        def next_action(self, observations):
            self.calls += 1
            return ProposedAction(tool="documents.read", arguments={"document_id": "refund-policy"})

    adapter = Adapter()
    with pytest.raises(RuntimeError, match="must stop"):
        run_agent(adapter, gateway)
    assert adapter.calls == 1


def test_reviewer_token_is_not_a_valid_agent_integration_credential(tmp_path, monkeypatch):
    with TestClient(create_app(str(tmp_path / "audit.db"), AGENT, REVIEWER)) as api:
        gateway = GatewayClient(REVIEWER)

        def transport(request, timeout):
            response = api.post(
                "/api/actions",
                content=request.data,
                headers={
                    "Authorization": request.get_header("Authorization"),
                    "Content-Type": "application/json",
                },
            )
            assert response.status_code == 401
            raise HTTPError(request.full_url, response.status_code, "Unauthorized", {}, None)

        monkeypatch.setattr(gateway.opener, "open", transport)
        with pytest.raises(RuntimeError, match="HTTP 401"):
            gateway.submit(
                ProposedAction(tool="documents.read", arguments={"document_id": "refund-policy"})
            )


def test_unconfigured_showcase_does_not_start_any_client(monkeypatch, capsys):
    def unexpected(*args, **kwargs):
        raise AssertionError("Disabled scaffold must not create a gateway client")

    monkeypatch.setattr("examples.real_agent_demo.GatewayClient", unexpected)
    main()
    assert "NOT CONNECTED" in capsys.readouterr().out
