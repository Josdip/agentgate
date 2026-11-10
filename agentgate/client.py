"""Local showcase integration contract. Agent adapters propose; the gateway executes."""

import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from pydantic import Field

from .policy import StrictModel, ToolCall


class ProposedAction(StrictModel):
    tool: str = Field(min_length=1, max_length=80)
    arguments: dict


class AgentAdapter(Protocol):
    def next_action(self, observations: list[dict]) -> ProposedAction | None:
        """Propose a tool request, or return None when the task is complete."""
        ...


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GatewayClient:
    def __init__(self, token: str, base_url="http://127.0.0.1:8000", run_id=None):
        url = urlsplit(base_url)
        if (
            url.scheme != "http"
            or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in {"", "/"}
        ):
            raise ValueError("The showcase client requires a loopback HTTP gateway URL.")
        if not token:
            raise ValueError("An agent token is required; do not use the reviewer token.")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.run_id = run_id or f"showcase-{uuid4().hex[:12]}"
        self.opener = build_opener(NoRedirect())

    def submit(self, proposed: ProposedAction):
        call = ToolCall(run_id=self.run_id, tool=proposed.tool, arguments=proposed.arguments)
        request = Request(
            f"{self.base_url}/api/actions",
            method="POST",
            data=call.model_dump_json().encode(),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with self.opener.open(request, timeout=10) as response:
                return json.load(response)
        except HTTPError as exc:
            # Avoid echoing credentials or server response bodies.
            raise RuntimeError(f"Gateway rejected the request (HTTP {exc.code}).") from None
        except URLError:
            raise RuntimeError("Local gateway unavailable; the agent must stop.") from None


def run_agent(adapter: AgentAdapter, gateway: GatewayClient, max_steps=6):
    if not 1 <= max_steps <= 100:
        raise ValueError("Choose a step limit between 1 and 100.")
    observations = []
    for _ in range(max_steps):
        proposed = adapter.next_action(list(observations))
        if proposed is None:
            break
        action = gateway.submit(proposed)
        observations.append(action)
        # Do not retry or execute a pending refund; it belongs to the reviewer now.
        if action["outcome"] == "pending":
            break
    return observations
