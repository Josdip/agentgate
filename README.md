# AgentGate

[![CI](https://github.com/Josdip/agentgate/actions/workflows/ci.yml/badge.svg)](https://github.com/Josdip/agentgate/actions/workflows/ci.yml)

**Observe AI agent tool calls. Enforce policy. Review sensitive actions.**

AgentGate is a local security gateway for synthetic Support, Sales, and Finance agents. It controls tool execution, records policy decisions, and gives a human reviewer a dashboard for approving sensitive requests.

**Status:** working portfolio prototype. Business data and tool effects are synthetic. The demo is scripted; no LLM or paid provider account is required.

## Product direction

AgentGate aims to help small and medium businesses understand which agents they have, where those agents run, what they can access, what they are doing, and what needs attention. The planned risk view separates configured exposure from observed behavior. See [the product direction](docs/product-direction.md) and [roadmap](docs/roadmap.md); automatic discovery and company-level risk assessment are future work.

## Live dashboard and agent profile

Run fourteen cases across three agents individually from the dashboard and watch its policy result appear. Activity updates every three seconds. Maintain persistent per-agent profiles with versioned model inventory, lifetime activity, and tool permissions derived from the enforced policy. Registered models are labeled unverified until real integrations exist.

See [the interactive demo and profile guide](docs/live-demo-and-profile.md) for usage and existing-clone update instructions.

## Agent rules

Open **Rules** to view, add, edit, or remove the rules each agent actually uses. Changes are saved, versioned, and immediately enforced. Removing a rule blocks that tool; agents cannot change their own permissions. See [rule management and upgrade notes](docs/agent-rules.md), especially the handling of older pending approvals.

## Security & compliance

Inspect per-agent configured risks, blocked attempts, pending reviews and missing evidence. Each finding explains a fix and verification step. Record GDPR, HIPAA and EU AI Act applicability with a rationale; supporting gateway checks never claim legal certification. See [the assessment guide](docs/security-compliance.md).

## Theme preference

Use **Dark theme** in the header to switch between light and dark. Your choice is remembered locally; credentials are not saved. See [theme behavior and verification](docs/theme-toggle.md).

## Readable interface

The light workspace redesign is documented in [interface redesign and verification](docs/interface-redesign.md), including desktop/mobile previews, interaction checks, and accessibility limits. Backend API and approval behavior remain unchanged.

## Product pages

The overview stays focused on totals, demos, and three recent actions. [Agent inventory](http://127.0.0.1:8000/agents) has its own page. [Activity & decisions](http://127.0.0.1:8000/activity) provides server-side filters and cursor pagination with 20 actions per page. See [navigation and multi-agent demos](docs/navigation-and-agents.md) for the latest behavior and upgrade steps.

## What you can demonstrate

- A scoped document read and $25 refund execute successfully.
- A $250 refund waits for human approval.
- An unauthorized document, unapproved destination, and unknown tool are denied.
- Sales can read assigned leads but cannot issue refunds; Finance can read invoices and request supplier payments.
- A reviewer sees the rule, explanation, request metadata, and outcome.
- Agent credentials cannot approve actions; concurrent or repeated reviews cannot execute a refund twice.

## Run locally

Requires Python 3.12+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.lock
.venv/bin/pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m agentgate
```

Open [the local dashboard](http://127.0.0.1:8000); no sign-in or token entry is needed. Select **Try a $250 refund request** for a guided first action, then approve or reject it. Explore **Agents**, **Rules**, and the fourteen individual demo cases. The CLI demo is also available in another terminal:

```bash
.venv/bin/python examples/demo.py
```

The launcher generates local settings in `.env`. Credentials and SQLite data are ignored by Git. Stop the server with Ctrl+C. See [local demo access](docs/local-demo-access.md) for the trust boundary and optional authenticated mode.

![Verified local reviewer dashboard](docs/images/dashboard.png)

## Architecture

```text
Scripted agent ──agent token──> FastAPI gateway ──> Policy engine
                                     │                  │
                                     ├──> SQLite audit  └──> Synthetic tools
                                     │
Reviewer dashboard ──reviewer token──┘
```

Python/FastAPI · SQLite · browser-native JavaScript · Pytest · Ruff · GitHub Actions

The gateway assigns identity from credentials and validates strict tool schemas before execution. Approved refunds use stored requests inside a serialized transaction. This atomicity applies to the simulated tools; real external integrations require idempotency and failure recovery.

## Verification

```bash
make check
```

Tests cover authorization boundaries, malformed arguments, refund thresholds, default-deny behavior, persistence, privacy redaction, and approval replay/concurrency. The batch CLI checks its original six Support-agent outcomes; automated tests cover all fourteen dashboard cases.

## Documentation

For project work in Codex, see the [coding assistant workflow](docs/coding-agent-workflow.md)
and repository instructions in [AGENTS.md](AGENTS.md).

| Guide | Contents |
|---|---|
| [Navigation & multi-agent demos](docs/navigation-and-agents.md) | Dedicated pages, bounded activity browsing, agent policies, update guide |
| [Product direction](docs/product-direction.md) | Business goals, agent coverage, understandable activity, explainable risk |
| [Real-agent scaffold](docs/real-agent-integration.md) | Placeholder and adapter contract for future genuine agent demos |
| [Live demo & profile](docs/live-demo-and-profile.md) | Individual scenarios, profile editing, model inventory, upgrade guide |
| [Development](docs/development.md) | Setup, demo, configuration, checks, Git workflow, troubleshooting |
| [Architecture](docs/architecture.md) | Components, request lifecycle, policy table, API, state, privacy |
| [Threat model](docs/threat-model.md) | Assets, attack cases, controls, limitations |
| [Roadmap](docs/roadmap.md) | Real agent integration, production hardening, portfolio release |
| [Decision record](docs/decisions/001-local-first.md) | Why local-first deterministic enforcement |
| [Build log](docs/build-log.md) | Implementation context and development decisions |
| [Contributing](CONTRIBUTING.md) | Focused commits, testing, documentation expectations |

## Boundaries

This prototype checks tool actions, not agent intent. Blocking an unapproved destination is not proof of prompt-injection detection. It has no tenant isolation, production identity provider, real business integrations, tamper-proof audit storage, or cumulative refund budget. See the threat model before extending it.
