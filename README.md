# AgentGate

A portfolio project for observing and governing AI agent tool calls. AgentGate evaluates policy before executing simulated business tools and records decisions for human review.

**Status:** local development prototype. All business data and tool effects are synthetic. This is not a production security product.

## Scope

- Authenticate a support agent independently from a human reviewer.
- Allow scoped document access and small refunds.
- Deny unknown tools, unauthorized documents, and unapproved destinations.
- Queue larger refunds for one-time human approval.
- Record decisions and execution outcomes in SQLite.
- Inspect activity and approvals in a local dashboard.

## Documentation

- [Architecture](docs/architecture.md)
- [Threat model](docs/threat-model.md)
- [Development guide](docs/development.md)
- [Roadmap](docs/roadmap.md)
- [Decision records](docs/decisions/001-local-first.md)

Setup and demo instructions will accompany the runnable implementation.
