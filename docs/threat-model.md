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

## Dashboard demo and inventory boundary

The reviewer can now trigger six predefined synthetic scenarios. Those endpoints accept no tool parameters or identities from the browser; unknown scenario IDs and request bodies are rejected. The agent credential cannot run reviewer demo endpoints, read profile metadata, or edit inventory. Refund approval remains a separate operation.

Profile updates allow metadata only and cannot grant tool permissions or set verification state. A revision precondition prevents concurrent edits from silently overwriting each other. Profile history retains past values, including removed model entries. Provider/model names are unverified declarations: do not infer an active LLM connection or automatic discovery. No credentials are collected by the inventory form.

## Future real-agent adapter scaffold

The scaffold is disabled by default and makes no provider/gateway calls. Its local client refuses non-loopback URLs and redirects, sends only the agent credential, returns denied results to the adapter, pauses on pending approvals, and stops on transport errors. Real adapters must not execute tools directly or receive reviewer credentials. The proposed step limit does not bound model token usage or costs; provider budgets/timeouts are required when implementing the adapter. The current showcase slot is static guidance rather than proof of a live integration.

## Multiple demo identities

Sales, Finance, and Support have separate server-owned permission scopes. Optional distinct Sales/Finance credentials bind external calls to those identities; caller-supplied identity remains invalid. Reviewer demos are fixed to the catalog's identity. Profile edits cannot change tools, scopes, deployment claims, or credentials. Finance payments are synthetic and require separate reviewer approval above $500. Scoping and pagination protect the product flow, but this remains one synthetic business rather than tenant isolation.
