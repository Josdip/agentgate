# Security & compliance

Open **Security & compliance** and choose an agent. This is a working, limited
assessment of saved gateway permissions and synthetic activity, not a compliance
certificate, live vulnerability scanner, or legal determination.

## What changes with the evidence

- An allow rule with a positive monetary threshold produces a configured-exposure
  finding. Changing it to review every request, setting the limit to zero, or
  removing it clears that finding on the next refresh.
- Monetary access also highlights the known lack of a cumulative budget. Review
  for every request reduces autonomy but does not implement accounting controls.
- Denied attempts and pending requests produce separate findings. Approving or
  rejecting a pending request removes the current pending signal. Blocked history
  remains visible; it does not mean compromise or prompt injection was detected.
- Missing live-model evaluations and dependency versions remain unknown. Declaring
  a model in inventory cannot make those checks pass.

Each finding provides evidence, suggested action, a way to verify the change, and
a guidance source. Links open agent-specific Rules and Activity. The latest five
records link to their run evidence; aggregate counts include the entire agent
history, not just the Activity page or its first 200 records.

## Regulations and applicability

The initial curated catalog covers GDPR, the HIPAA Security Rule, and the EU AI
Act. Scope depends on the business, data, location, role and intended use. It
cannot be inferred from a Support, Sales or Finance label. The default is
**Not determined**. Reviewers can record **Applies** or **Does not apply**, with
a rationale, separately for each agent and regulation. These are declarations,
not independently verified legal conclusions. No production data is needed.

Regulation cards explain scope, relevant control topics, official references,
and next steps. Supporting controls report **Present in gateway**, **Gap**, or
**Needs evidence**. The voluntary demo baseline of reviewing every monetary
action is not a universal requirement of these regulations. Legal compliance
stays **Not assessed**, including when a regulation is declared out of scope.
Contracts, lawful basis, organisational policies, training, retention, incident
response, real infrastructure safeguards and full regulatory coverage require
separate evidence and qualified review. EU AI Act duties and dates must be
checked against the current official guidance for the actual use case.

## Demo tour

1. Choose Support in Security & compliance and expand a suggested fix.
2. On Overview, run **Attempt payroll access**, then return. A blocked-attempt
   finding and recent decision evidence appear without a claim of compromise.
3. On Rules, change the refund rule to require review for every request.
4. Return to Security & compliance. The automatic-spending finding disappears;
   the historical attempt and missing budget/model evidence remain.
5. Expand a regulation, save its applicability and rationale, and switch agents.
   Declarations persist independently; they never modify tool permissions.

## Implementation and trust boundary

`security.py` owns the versioned curated catalog and deterministic checks.
`Store.security()` reads policy, profile, declarations and activity in a single
SQLite snapshot. The catalog version, policy/profile revisions, evaluation time,
owner and bounded decision references are returned. Findings are recomputed;
there is no historical finding lifecycle, acknowledgement system, advisory feed
or background scheduler. Guidance sources are curated as of 2026-11-10, not live
threat intelligence. No data or telemetry is sent to external sources.

Reviewer-only endpoints:

- `GET /api/agents/{agent_id}/security`
- `PUT /api/agents/{agent_id}/compliance/{framework}` with strict fields
  `revision`, `applicability`, `rationale` (10–500 characters).

Declarations use compare-and-swap revisions, serialised writes and persistent
history in `compliance_scope_history`. Unknown agents/frameworks fail closed.
Clients cannot mark themselves compliant or upload executable detection rules.
The default local demo browser has reviewer privileges; this does not create
production policy-administrator roles or tenant isolation. Text uses safe DOM
rendering. Polling preserves unchanged drafts and expanded findings; changing
agents discards unsaved drafts. A concurrent applicability change preserves your draft; a stale save is rejected. Use Reload saved applicability to discard the draft and load the latest saved values. Disconnect removes rendered assessment data.

## Sources

Official regulatory references and OWASP guidance, reviewed 2026-11-10:

- [GDPR, including Articles 3 and 32](https://eur-lex.europa.eu/eli/reg/2016/679/oj)
- [HHS Security Rule summary](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html)
- [HHS covered entities and business associates](https://www.hhs.gov/hipaa/for-professionals/covered-entities/index.html)
- [European Commission AI Act overview](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai)
- [OWASP excessive agency guidance (2025 edition)](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)
- [OWASP prompt injection guidance (2025 edition)](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)

These are selected control topics, not an exhaustive mapping or reproduced legal
text. Changes to the catalog require code review and a catalog version update.

## Verification

`make check`: 102 Python tests plus Ruff lint/format checks.
`make check-interface`: 17 tests, including draft preservation during polling,
agent switching and clearing assessment data on disconnect. Backend tests cover
reviewer-only access, unknown scope, strict inputs, concurrent declaration writes,
persistence, remediation and counts beyond 200 actions.

Browser verification used a disposable database: saving applicability, generating
a blocked case, following the Rules link, changing a refund to require review,
and observing the exposure finding disappear at policy revision 2. Checked light
desktop and dark 390px mobile layouts without horizontal overflow. Semantic
labels and navigation focus were inspected; this is not a full accessibility audit.

[Desktop preview](images/security/desktop.png) · [Mobile dark preview](images/security/mobile-dark.png)
