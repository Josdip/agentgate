"""Local development launcher: python -m agentgate."""

import os
import secrets
from pathlib import Path

import uvicorn

from .app import create_app


def main():
    config = Path(".env")
    if not config.exists():
        values = "".join(
            f"{name}={secrets.token_urlsafe(32)}\n"
            for name in ("AGENTGATE_AGENT_TOKEN", "AGENTGATE_REVIEWER_TOKEN")
        )
        # Exclusive creation and restrictive mode prevent accidental overwrites/exposure.
        with open(config, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as file:
            file.write(values)
        print("Created local credentials in .env (ignored by Git).")
    for line in config.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, value = line.split("=", 1)
            if name in {
                "AGENTGATE_AGENT_TOKEN",
                "AGENTGATE_REVIEWER_TOKEN",
                "AGENTGATE_DB",
                "AGENTGATE_SALES_TOKEN",
                "AGENTGATE_FINANCE_TOKEN",
                "AGENTGATE_DEMO_MODE",
            }:
                os.environ.setdefault(name, value)
    demo_setting = os.environ.get("AGENTGATE_DEMO_MODE", "1")
    if demo_setting not in {"0", "1"}:
        raise RuntimeError("AGENTGATE_DEMO_MODE must be 0 or 1")
    demo_mode = demo_setting == "1"
    print("Dashboard: http://127.0.0.1:8000")
    print(
        "Local demo: open the dashboard; no sign-in needed."
        if demo_mode
        else "Authenticated mode: use the reviewer credential."
    )
    uvicorn.run(create_app(demo_mode=demo_mode), host="127.0.0.1", port=8000, proxy_headers=False)


if __name__ == "__main__":
    main()
