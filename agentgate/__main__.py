"""Launch the local AgentGate discovery and governance workspace."""

import os
from pathlib import Path

import uvicorn

from .managed import create_managed_app
from .sonar_launcher import SonarLauncher


def main():
    database = Path(os.environ.get("AGENTGATE_DB", "data/discovery.sqlite3"))
    database.parent.mkdir(parents=True, exist_ok=True)
    gateway_port = int(os.environ.get("AGENTGATE_PORT", "8001"))
    standalone_port = int(os.environ.get("AGENTGATE_SONAR_PORT", "5000"))
    token_file = Path(os.environ["AGENTGATE_SONAR_TOKEN_FILE"])
    launcher = SonarLauncher(
        os.environ.get("AGENTGATE_SONAR_SOURCE", str(Path.home() / "homelab/sonar")),
        database.parent / f"{database.stem}-sonar",
        token_file,
        gateway_port,
        standalone_port,
        int(os.environ.get("AGENTGATE_MANAGED_SONAR_PORT", "5002")),
    )
    app = create_managed_app(
        database,
        os.environ["AGENTGATE_PROJECT"],
        token_file.read_text().strip(),
        Path(os.environ["AGENTGATE_REVIEWER_TOKEN_FILE"]).read_text().strip(),
        standalone_port,
        launcher=launcher,
    )
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=gateway_port,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
