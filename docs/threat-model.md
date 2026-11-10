# Threat model

## Assets and assumptions

Protect tool authorization, approval integrity, audit confidentiality, and simulated business records. Treat agent-generated tool names and parameters as untrusted. A malicious instruction in retrieved content may influence an agent. Human reviewer credentials and the host running AgentGate are assumed trusted.

Scope: one developer machine, one synthetic business, one support agent, one reviewer. The demo is not multi-tenant and is not exposed on a public network.

| Threat | Implemented control | Verification |
|---|---|---|
| Agent impersonates a privileged identity | Identity comes from role-specific credential; extra top-level fields forbidden | API role and impersonation tests |
| Tool invocation outside the registry | Default deny on unknown tool names | Policy tests and scripted demo |
| Access to unauthorized documents | Exact document allowlist | Policy/API tests |
| Exfiltration to an unapproved destination | Exact destination allowlist; no arbitrary network calls | Policy tests and scripted demo |
| Agent self-approves a refund | Separate reviewer credential; no approval fields accepted in tool request | API authorization tests |
| Approval request modified by reviewer | Review accepts only boolean; stored tool parameters are used | Schema and persistence tests |
| Approval replay or concurrent review | Transaction lock plus pending-only transition | Replay and concurrent review tests |
| Numeric coercion bypasses refund rules | Strict positive integer cents, bounded amount | Boundary and malformed-value tests |
| Stored content executes in dashboard | DOM text rendering, restrictive CSP | Code inspection; browser smoke check |
| Audit captures message secrets | Redacted message bodies and omitted unknown-tool arguments | Store tests |

## Explicit limitations

- Policy checks actions, not agent intent. An unapproved destination block does not prove detection of prompt injection, and permitted destinations could still receive inappropriate content.
- The scripted demo does not invoke an LLM. A model-driven prompt-injection evaluation is a future milestone.
- The refund limit is per action; splitting refunds can bypass a cumulative budget. No accounting ledger or customer ownership checks exist.
- Bearer tokens are static development credentials. No OIDC, tenant isolation, fine-grained reviewer roles, rotation UI, or TLS termination exists.
- SQLite files can be modified by a host administrator. No append-only audit export, encryption-at-rest setup, or retention automation exists.
- No rate limits, approval expiry, distributed workers, external idempotency protection, or durable external-tool error handling exist.
- A content-length check is a convenience limit, not a complete streaming-body or denial-of-service defense. Use a hardened server/proxy before network deployment.
- Invalid authentication and malformed requests are rejected but are not part of the persisted activity list.

## Safe demonstration

Use only synthetic data and simulated tools. Keep the server bound to `127.0.0.1`. Tokens are generated into the ignored `.env` file with owner-only permissions by the local launcher. Never paste a real production API key into this project or commit `.env` or databases.
