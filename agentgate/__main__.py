"""Launch the local AgentGate discovery and governance workspace."""

import os
from pathlib import Path

import uvicorn

from .managed import create_managed_app


def main():
    database = Path(os.environ.get("AGENTGATE_DB", "data/discovery.sqlite3"))
    database.parent.mkdir(parents=True, exist_ok=True)
    app = create_managed_app(
        database,
        os.environ["AGENTGATE_PROJECT"],
        Path(os.environ["AGENTGATE_SONAR_TOKEN_FILE"]).read_text().strip(),
        Path(os.environ["AGENTGATE_REVIEWER_TOKEN_FILE"]).read_text().strip(),
        int(os.environ.get("AGENTGATE_SONAR_PORT", "5000")),
    )
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("AGENTGATE_PORT", "8001")),
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
