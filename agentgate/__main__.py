"""Launch the local AgentGate discovery and governance workspace."""

import argparse
import os
import secrets
import sys
from pathlib import Path

import uvicorn

from .managed import create_managed_app
from .onboarding import local_port, setup_paths, setup_sandbox
from .sonar_launcher import SonarLauncher


def main(argv=()):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup-sandbox", action="store_true", help="Check and set up Bubblewrap.")
    parser.add_argument(
        "--first-run-link", action="store_true", help="Print a one-use local reviewer link."
    )
    parser.add_argument(
        "--fresh-session",
        action="store_true",
        help="Start an empty demo with new credentials and its own project.",
    )
    options = parser.parse_args(argv)
    first_run_code = secrets.token_urlsafe(32) if options.first_run_link else None
    try:
        if options.setup_sandbox:
            setup_sandbox()
        env = dict(os.environ)
        setup_paths(env, fresh_session=options.fresh_session)
        database = Path(env["AGENTGATE_DB"])
        database.parent.mkdir(parents=True, exist_ok=True)
        gateway_port = int(env["AGENTGATE_PORT"]) if "AGENTGATE_PORT" in env else local_port(8001)
        managed_port = (
            int(env["AGENTGATE_MANAGED_SONAR_PORT"])
            if "AGENTGATE_MANAGED_SONAR_PORT" in env
            else local_port(5002)
        )
        standalone_port = int(env.get("AGENTGATE_SONAR_PORT", "5000"))
        token_file = Path(env["AGENTGATE_SONAR_TOKEN_FILE"])
        reviewer_file = Path(env["AGENTGATE_REVIEWER_TOKEN_FILE"])
        launcher = SonarLauncher(
            env.get("AGENTGATE_SONAR_SOURCE"),
            database.parent / f"{database.stem}-sonar",
            token_file,
            gateway_port,
            standalone_port,
            managed_port,
        )
        app_options = {"launcher": launcher}
        if first_run_code:
            app_options["first_run_code"] = first_run_code
        app = create_managed_app(
            database,
            env["AGENTGATE_PROJECT"],
            token_file.read_text().strip(),
            reviewer_file.read_text().strip(),
            standalone_port,
            **app_options,
        )
    except (OSError, ValueError) as exc:
        parser.exit(1, f"AgentGate could not start: {exc}\n")
    url = f"http://127.0.0.1:{gateway_port}/agents"
    if first_run_code:
        print(
            f"Open AgentGate (one-use link, valid for 5 minutes): {url}#connect={first_run_code}",
            flush=True,
        )
    else:
        print(f"Open AgentGate: {url}", flush=True)
    print(f"Reviewer token file: {reviewer_file}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=gateway_port, proxy_headers=False)


if __name__ == "__main__":
    main(sys.argv[1:])
