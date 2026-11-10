# Roadmap

Product direction: [simple, evidence-based agent oversight for small and medium businesses](product-direction.md).

## Delivered: local governance foundation

Deterministic policy, agent/reviewer credentials, persistent audit, one-time approvals, six individually runnable dashboard cases, auto-refresh, three seeded agent profiles, versioned declared model inventory, and policy-derived tool permissions. Tools remain synthetic. A real-agent adapter scaffold is available; no model integration is connected by default.

## Delivered: initial multi-agent business view

Dedicated inventory/profile pages, an overview limited to three recent actions, and a separate server-filtered paginated activity page. Support, Sales, and Finance have distinct effective permissions, versioned metadata, and fourteen total demo cases. Optional credentials bind direct API calls to their registered identities. Deployment locations remain simulated.

## Next: broader registry and business workflows

Extend the seeded registry with onboarding, lifecycle management, verified cloud/endpoint/browser sources, and reporting freshness. Add a company overview showing known/active agents and coverage gaps. Bind credentials to individual agents before accepting multi-agent events; never trust caller-supplied identity. Scope profiles and activity per agent and retain the existing support-agent demo data.

Show configured tool/model connections separately from verified and observed usage. Translate activity into concise business language with technical evidence available on demand. Add a “Needs attention” workflow for consequential decisions.

## Next: explainable risk

Assess configured exposure and observed behavior separately. Use Low/Medium/High/Unknown with explanations, timestamps, source coverage, and suggested actions. Persist versioned assessment inputs/results; distinguish blocked attempts from completed actions. Add scenario-based evaluation of risk labels and false positives. No telemetry must not imply safety.

## Real-agent showcase integration

Implement `ShowcaseAgent.next_action` in `examples/real_agent_demo.py`, configure a provider outside the browser, and route tool proposals through `GatewayClient`. Begin with one real support agent and synthetic tools. Demonstrate malicious instructions in retrieved content and record actual observed outcomes. Evaluate realistic boundaries without claiming universal prompt-injection detection.

The dashboard integration area is a placeholder with setup guidance, not a process launcher or connection monitor. See [the integration guide](real-agent-integration.md).

## Broader deployment coverage

Add a cloud connector, then endpoint and browser reporting incrementally. For each source, document discovery prerequisites, stable identity mapping, deduplication, permission requirements, telemetry freshness, and observation versus enforcement capabilities. Do not imply complete company discovery from gateway traffic alone.

## Service hardening and product validation

Tenant isolation, PostgreSQL migrations, OIDC/RBAC, scoped short-lived credentials, approval expiry, retention controls, rate limits, deployment and backups. Add idempotency and durable external-side-effect processing before real business tools. Validate onboarding and business terminology with prospective SMB users; publish reproducible evaluation results and an honest portfolio walkthrough.
