"""Replace ShowcaseAgent.next_action with a real model/framework integration later."""

import os
from pathlib import Path

from agentgate.client import GatewayClient, ProposedAction, run_agent


class ShowcaseAgent:
    ready = False

    def next_action(self, observations: list[dict]) -> ProposedAction | None:
        # TODO: Call your provider/framework here using its own environment credentials.
        # Convert its tool call to ProposedAction(tool="documents.read",
        #                                       arguments={"document_id": "refund-policy"}).
        # Pass gateway results back to the model; return None when complete.
        # Do not execute tools here or give the model reviewer credentials.
        raise NotImplementedError("No real agent has been connected yet.")


def main():
    adapter = ShowcaseAgent()
    if not adapter.ready:
        print("Real agent demo: NOT CONNECTED")
        print("Implement ShowcaseAgent.next_action in examples/real_agent_demo.py,")
        print("then set ready=True. No provider or gateway requests were made.")
        return
    token = os.environ.get("AGENTGATE_AGENT_TOKEN", "")
    if not token and Path(".env").exists():
        token = next(
            (
                line.split("=", 1)[1]
                for line in Path(".env").read_text().splitlines()
                if line.startswith("AGENTGATE_AGENT_TOKEN=")
            ),
            "",
        )
    gateway = GatewayClient(token)
    results = run_agent(adapter, gateway, max_steps=6)
    for result in results:
        print(f"{result['tool']}: {result['outcome']} — {result['reason']}")
    print(f"Run {gateway.run_id}: {len(results)} tool requests recorded; inspect the dashboard.")


if __name__ == "__main__":
    main()
