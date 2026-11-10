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
            }:
                os.environ.setdefault(name, value)
    print("Dashboard: http://127.0.0.1:8000 — reviewer token is in .env")
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
