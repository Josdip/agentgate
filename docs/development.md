# Development guide

## Prerequisites

Python 3.12 or later and Git. No model API key, Node.js, or external database is required.

## Reproducible environment

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.lock
.venv/bin/pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m agentgate
```

The launcher creates `.env` with two random credentials, creates `data/agentgate.db`, and starts on `http://127.0.0.1:8000`. Environment variables override `.env` values. Never reuse the two tokens. If tokens are missing, shorter than 24 characters, or identical, startup fails.

You can run all six cases individually from the dashboard after connecting. See [live demo and profile](live-demo-and-profile.md). To run the optional batch CLI, use a second terminal:

```bash
.venv/bin/python examples/demo.py
```

The script prints six expected outcomes: two executions, one pending review, and three denials. Every invocation gets a new run ID and adds six new records. It submits real HTTP requests to the local gateway, but all business tool effects are simulated.

Open the dashboard, copy `AGENTGATE_REVIEWER_TOKEN` from your local `.env` into the reviewer access field, and connect. Inspect denied requests and approve or reject the $250 refund. Activity updates automatically every three seconds while the tab is visible; Refresh also retrieves activity. An action can only be reviewed once.

Stop the server with Ctrl+C. Audit data persists across restarts. To start a clean demonstration, stop the server and set `AGENTGATE_DB` to a new local database path. Rotating credentials requires updating `.env` and restarting.

## Checks

```bash
make check
```

Or run Ruff lint, Ruff formatting checks, and Pytest separately as shown in the Makefile. CI runs these checks on pushes and pull requests. The checked-in `requirements-dev.lock` pins the complete tested development environment; `pyproject.toml` expresses supported dependency ranges. Update the lock in an isolated environment and rerun all checks when upgrading dependencies.

## Project map

```text
agentgate/              API, policy, profile persistence, scenario catalog, launcher
agentgate/static/       Reviewer dashboard (no build step)
examples/demo.py        Scripted support-agent tool requests
tests/                 Policy, persistence, concurrency, authorization tests
docs/                  Architecture, security model, roadmap, decisions
.github/workflows/      Automated checks
```

## Working with Git

Use `codex/` feature branches for future work. Make commits around coherent behaviors and their tests. The initial implementation is divided into scope/design, enforcement/storage, API/dashboard, and reproducible demo/documentation. Do not squash away useful history for the portfolio.

GitHub browser sign-in and the connected GitHub app are separate from terminal Git authentication. For ordinary pushes on a fresh machine, configure SSH or GitHub CLI with `gh auth login` followed by `gh auth setup-git`.

## Troubleshooting

- **401:** the agent and reviewer credentials differ; make sure each client uses the correct one. Restart after credential changes.
- **422:** check the strict parameter schemas in `policy.py` or `/openapi.json`; cents must be an integer.
- **409 on review:** another reviewer already decided the action. Refresh.
- **Port 8000 in use:** stop the previous local instance before restarting.
- **Tests stall only in a restricted runner:** run in a context that permits local async/thread operations; the full API suite uses FastAPI's TestClient.
- **Empty dashboard:** connect with the reviewer credential, run the demo, and refresh.

For a future model-driven showcase, start with [the real-agent integration scaffold](real-agent-integration.md). Its unconfigured default safely prints setup guidance without making requests.
