# AgentGate security product direction

Recorded November 10, 2026. These are proposed requirements, not implemented
capabilities. Geordie is a functional reference; feature parity has not been
verified. Use original implementation and product design.

## Product outcome

Interface requirement: friendly, readable, and original. See
[interface-direction.md](interface-direction.md) for navigation, visual direction,
security writing, accessibility, and implementation acceptance criteria.

Help a business discover its agents, understand their access and behavior, learn
which current threats apply to them, and reduce that exposure through specific,
verifiable fixes. Support technical operators and understandable business impact.

## Reference capabilities and differentiation

Geordie's public pages describe agent discovery/inventory, posture management,
behavioral visibility, risk intelligence, remediation, and cost intelligence.
Use these as capability areas to evaluate, not a promise of complete parity.

AgentGate's proposed emphasis is traceable threat-to-agent matching, enforced
tool boundaries, actionable remediation, and verification after a fix. A gateway
only sees actions routed through it: disclose unmanaged agents, missing telemetry,
and connectors that observe but cannot enforce. Do not claim estate-wide coverage
until discovery connectors and their limits have been verified.

## Required capability areas

1. Inventory: agent purpose/type, owner, framework/runtime and versions, model,
   deployment, tools/MCP servers/plugins, dependency inventory, credentials/scopes,
   data access, network reach, and last observed activity. Record provenance and
   freshness; distinguish declared configuration from verified configuration.
2. Posture: map accessible resources and privileges; detect unnecessary access,
   unsafe configuration, vulnerable components, and missing controls.
3. Runtime governance: validate typed tool calls, enforce allow/deny/approval,
   record outcomes, and support incident containment for integrated executors.
4. Threat intelligence: ingest trusted advisories and guidance, normalize them,
   deduplicate aliases, track corrections/withdrawals, and reevaluate affected
   agents when intelligence or inventory changes.
5. Findings: explain the affected agent, evidence, attack prerequisites, business
   impact, confidence, priority, source, remediation, and verification procedure.
6. Remediation: offer configuration/policy changes, fixed-version guidance, and
   code patches or pull requests where source access permits. Test fixes and
   record residual risk; keep applying changes separate from recommending them.
7. Operations: route material new/changed findings to owners, suppress duplicates,
   track acknowledgement and exceptions, and show overdue fixes and coverage gaps.
   Cost visibility is a later reference capability, not the initial security focus.

## Threat examples and control requirements

| Threat | Applicability evidence | Proposed controls and verification |
|---|---|---|
| SSRF | Agent can cause server-side outbound requests; destination controls absent or bypassable | Enforce approved schemes/destinations at execution, validate resolved addresses and every redirect, restrict private/link-local/metadata access unless explicitly required, and enforce network egress. Test DNS/redirect and alternate-address bypass cases in an isolated environment. |
| Direct/indirect prompt injection | Agent consumes untrusted instructions, retrieved content, repository files, or tool responses while holding consequential privileges | Separate trusted instructions from data, scope credentials/tools, enforce policy outside the model, require approval for sensitive actions, and evaluate adversarial content. Filters are additional signals, not proof of prevention. |
| Token/credential abuse | Agent receives or forwards authentication tokens, uses excessive scopes, or trusts unvalidated token claims | Define token audience/issuer/scope checks where relevant, avoid token passthrough and logging secrets, use short-lived scoped credentials, and test role separation. |
| Special-token or message-boundary injection | A model adapter constructs prompts/messages using attacker-controlled delimiters or unsafe serialization | Use supported structured message APIs, validate adapter boundaries, and test provider-specific cases. Track separately from credential/token theft. |
| Tool/MCP poisoning and supply-chain compromise | Agent loads external tool descriptions, plugins, dependencies, or changed tool definitions | Track versions and provenance, review capability changes, pin/verify artifacts where supported, isolate execution, and match advisories to installed versions. |
| Code/command injection and workspace escape | Coding agent can write files or run commands | Constrain paths including symlink behavior, isolate execution, protect credentials, bound execution and egress, and test unauthorized command/path attempts. |
| Data exfiltration and excessive agency | Sensitive data access can combine with external writes or excessive privileges | Minimize access, constrain destinations, redact audit data, enforce approvals and budgets, and test multi-step abuse paths. |
| Memory/RAG poisoning | Persistent memory or retrieval content can be written by untrusted actors | Track provenance and write permissions, isolate tenants/sessions, support rollback, and test persistence of adversarial instructions. |

"Token injection" is ambiguous. Cover both authentication-token abuse and
model-input boundary attacks until the intended term is clarified.

Agent type suggests which checks matter; actual permissions, dependencies,
configuration, and runtime evidence determine applicability. Do not mark every
browser agent vulnerable to SSRF or every coding agent compromised.

## Finding and evidence model

Keep these dimensions separate:

- Applicability: affected, potentially affected, not affected with justification,
  or unknown because required evidence is missing.
- Runtime evidence: no observed exploitation, suspicious behavior, or confirmed
  compromise supported by investigated evidence. A vulnerable version alone
  does not establish compromise.
- Remediation: open, proposed, applied, verified, accepted risk, or reopened.

Store agent ID and inventory revision, rule/advisory ID and version, source URL,
published/updated/ingested timestamps, evidence references, match rationale,
severity/confidence, owner, recommended fix, and validation result. Reopen or
reassess findings when evidence changes. Avoid an unexplained single risk score.

Example: a research agent has a URL-fetch tool without enforceable destination
restrictions. Report potential SSRF exposure with the exact configuration evidence,
recommend an executor-side destination policy and egress restrictions, and verify
with isolated boundary tests. Do not report confirmed compromise without evidence.

## Keeping intelligence current

Use vendor security advisories and GitHub Security Advisories/OSV for component
vulnerabilities, CISA KEV as an exploitation-priority input, and OWASP/MITRE ATLAS
for attack classes and defensive guidance. Not every AI attack has a CVE; keep
component advisories separate from general attack-pattern rules.

Design for scheduled ingestion (initial target: daily) plus manual refresh,
retries/backoff, source health, last-success timestamps, stale-feed warnings,
versioned records, and audit trails. This document does not create a scheduler.
Daily polling is not a guarantee of immediate or comprehensive threat detection.

Match exact ecosystem/package/version where possible; evaluate configuration and
reachability prerequisites. Treat research and news as leads requiring source
validation, not automatic proof of affectedness. Treat feed content as untrusted
data; it cannot execute commands or alter policy. Human-review new detection
rules and remediation templates before production use.

## Delivery order

1. Security findings MVP: manual/declared inventory, versioned curated threat
   rules, evidence-backed matching, per-agent findings and recommended fixes,
   and explicit unknown/coverage states. Use synthetic fixtures first.
2. Continuous updates: trusted feed ingestion, version matching, rescan jobs,
   freshness indicators, deduplication, ownership and notifications.
3. Coding-agent pilot: propose/edit/check/review on scoped task branches; add
   gateway-owned coding executors, approvals, audit and failure recovery before
   claiming enforced integration.
4. Remediation verification: generate reviewable fixes/PRs, run regression and
   adversarial tests, and verify deployment/configuration evidence after rollout.
5. Broader connectors/discovery and business dashboards; expand coverage only as
   each integration is tested. Tenant isolation, production identity, protected
   audit storage, and incident handling precede real multi-business deployment.

First milestone acceptance: one agent with declared capabilities produces
explainable matched findings; missing evidence yields unknown; a tested control
change updates the finding; all screens distinguish demo from observed state;
authorization prevents agents from approving their own sensitive actions.

## Sources reviewed

- https://www.geordie.ai/product/agent-discovery/
- https://www.geordie.ai/product/risk-intelligence/
- https://www.geordie.ai/ (broader public capability descriptions)
- https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html
- https://google.github.io/osv.dev/api/
- https://www.cisa.gov/known-exploited-vulnerabilities-catalog
