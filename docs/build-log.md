# Build log

## Initial implementation — November 9, 2026 (America/Chicago)

Established AgentGate as a local-first portfolio prototype. Chose a deterministic policy gateway so prevention can be demonstrated without relying on an LLM classifier. Created a private `Josdip/agentgate` GitHub repository.

Implemented exact tool/document/destination allowlists, strict refund validation, role-separated authentication, persistent audit records, serialized one-time approvals, and a browser dashboard. Added a scripted HTTP demo and security regression tests. The architecture, threat model, decision record, roadmap, and setup guide distinguish current capabilities from future work.

The workspace initially lacked Python packages, Node, and GitHub CLI. Python dependencies were installed into an ignored virtual environment. Git metadata required elevated filesystem access because the workspace's `.git` directory is protected. Browser GitHub login does not authenticate terminal Git, so terminal access was configured separately rather than copying or exposing connector credentials.

No real agent framework, paid model provider, customer records, refunds, or external delivery service is used in this milestone.

## Validation

- Ruff lint and formatting checks passed.
- 26 automated tests passed, including authorization, policy boundaries, concurrent reviews, redaction, and first-run credential generation.
- All 6 scripted HTTP demo outcomes matched expectations.
- Browser smoke test loaded real audit records and approved the pending synthetic refund; counts changed from 2 to 3 executed and from 1 to 0 pending.
- Saved the verified dashboard screenshot in `docs/images/dashboard.png`.
- The current Starlette release emits a TestClient deprecation warning for its httpx adapter; tests still pass. Migrate the test adapter in a future dependency update.
