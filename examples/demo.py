"""Replay scripted tool attempts. No model provider or real customer data required."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from agentgate.scenarios import scenarios


def main():
    token = os.environ.get("AGENTGATE_AGENT_TOKEN")
    if not token and Path(".env").exists():
        token = next(
            (
                line.split("=", 1)[1]
                for line in Path(".env").read_text().splitlines()
                if line.startswith("AGENTGATE_AGENT_TOKEN=")
            ),
            None,
        )
    if not token:
        raise SystemExit("Start python -m agentgate first to create local credentials.")
    run_id = f"demo-{uuid4().hex[:8]}"
    for item in scenarios():
        label, tool, arguments, expected = (
            item[key] for key in ("name", "tool", "arguments", "expected")
        )
        request = Request(
            "http://127.0.0.1:8000/api/actions",
            method="POST",
            data=json.dumps({"run_id": run_id, "tool": tool, "arguments": arguments}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=10) as response:
                action = json.load(response)
        except HTTPError as exc:
            raise SystemExit(
                f"Gateway returned HTTP {exc.code}; check credentials and configuration."
            ) from None
        except URLError:
            raise SystemExit(
                "Cannot reach local gateway. Start python -m agentgate first."
            ) from None
        if action["outcome"] != expected:
            raise SystemExit(f"FAIL: {label}: expected {expected}, got {action['outcome']}")
        print(f"{label:25} {action['outcome']:10} {action['rule']}")
    print(f"\n6/6 scripted outcomes matched. Run: {run_id}")
    print("Open the dashboard to approve or reject the large refund.")


if __name__ == "__main__":
    main()
