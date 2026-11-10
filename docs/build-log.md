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

GitHub Actions passed on the pushed implementation: [initial CI run](https://github.com/Josdip/agentgate/actions/runs/42732454724). Local `main` tracks `origin/main`; project source and meaningful commit history are synchronized. Runtime credentials, virtual environment, and SQLite files are untracked.

## Interactive demo and ongoing agent profile — November 9, 2026

Added six individual dashboard scenario controls, immediate policy results, and three-second polling for activity/profile updates. The CLI shares the scenario catalog. Reviewer-only demo endpoints accept fixed scenario IDs, reject request overrides, and preserve separate refund approval.

Added persistent agent identity metadata, declared provider/model inventory, enforced tool/permission descriptions, lifetime action totals and last activity, and versioned profile history with concurrent-edit protection. Existing SQLite audit data is preserved. Model entries remain explicitly unverified; no provider credentials or live LLM calls are introduced.

Validation: 39 automated tests pass, with the existing upstream TestClient deprecation warning. Browser testing ran all six cases individually, approved the large refund, and saved a model inventory entry at revision 2. Screenshots are in `docs/images/live-demo.png` and `docs/images/agent-profile.png`. The temporary QA service used port 8011 and was stopped after verification.

## Product direction and real-agent scaffold

Recorded the SMB product destination: a named multi-agent directory across cloud, endpoints, and browsers; model/tool inventories; understandable activity; and separate configured/observed risk with evidence and coverage labels. These broader capabilities remain roadmap items.

Added a clearly unconnected dashboard showcase area, a replaceable `ShowcaseAgent` adapter, and a loopback-only gateway client/run loop. The disabled scaffold makes no requests. Real integrations must route tool proposals through policy; pending approval pauses the loop and connection failures stop it. No provider dependency, credentials, live model, process launcher, or discovery claim was added.

Validation: 47 automated tests pass; the existing upstream TestClient deprecation warning remains. Browser verification confirmed the unconnected showcase panel and expandable implementation guidance. The temporary port-8011 server was stopped afterward. A preview is saved in `docs/images/real-agent-placeholder.png`.

## Dedicated product pages and three-agent demo

Moved inventory/profiles to `/agents` and `/agents/{id}` and all decisions to `/activity`. The overview is bounded to three recent actions with summary totals and review shortcuts. Activity now uses SQL filters, cursor pagination, and a 20-record UI page, with paused polling on older pages.

Added Sales and Finance demo identities, independent profiles/history, credential-bound API identity, scoped tools, and eight additional scenarios (fourteen total). Existing Support data and metadata survive startup. Locations are explicitly simulated; no new discovery or LLM connection is claimed.

Validation: 55 automated tests pass, including a 1,001-record cursor traversal with a concurrent arrival. Browser checks verified new cases, finance approval, dedicated pages, 20-row paging, and filtered results. The temporary port-8011 QA server was stopped. New guides and screenshots document the product flow and compatibility endpoints.

## Readable interface pass — November 10, 2026

On `codex/readable-interface`, implemented the owner's original light-workspace direction with readable type, action-first overview, comparable agent rows, explicit decision/review context, and responsive layouts. No backend/API/authorization changes or new security capability claims were introduced. Added loading/unavailable/stale guidance and context-preserving rendering, with session guards for disconnect races.

Verification: 55 Python tests and five dependency-free JavaScript state tests pass, with the existing upstream TestClient warning. Desktop/mobile browser checks covered all fourteen demos, approval/rejection, profiles, search/pagination, keyboard focus, polling preservation, and server-failure feedback. Contrast values and native-zoom verification limits are recorded in `docs/interface-redesign.md`. Screenshots use disposable QA records; the temporary server was stopped.

## Theme toggle — November 10, 2026

On `codex/theme-toggle`, added an accessible header control and full-workspace light/dark semantic palettes. Only the validated preference is persisted; blocked storage does not disable switching, and authentication/API behavior is unchanged. Builds on the readable-interface task branch without merging to main.

Verification: 55 Python tests and nine interface tests pass. Browser checks covered keyboard switching, reload persistence, navigation, connected demos, dark approval context, and a 390px mobile layout. Both palette contrast checks passed. The temporary QA server was stopped. Details and screenshots are in `docs/theme-toggle.md`.

## Editable per-agent rules — November 10, 2026

On `codex/agent-rules`, added a real Rules page with per-agent add/edit/delete, structured decisions/targets/amount limits, and versioned history. Stored rules now drive gateway decisions and profile permissions; fixed schema/identity/reviewer boundaries remain immutable. Audit records identify policy revision and concrete rule, rule edits are concurrency-checked, and old/legacy pending approvals cannot execute after permission changes. Existing data is migrated without resetting configured policies.

Validation: 80 Python tests and 11 interface tests pass. Browser checks confirmed CRUD, delete cancellation/history, a $25 refund becoming pending after a $20 limit, preserved drafts/stale edit rejection, and stale approval rejection. Both themes and 390px navigation were checked. QA used a temporary database/port 8011 and was stopped. Documentation records default-versus-custom demo expectations and prototype limits.

## Approved earlier interface/theme merges

At the owner's explicit request, merged PR #1 (readable interface) and PR #2 (theme toggle) to main, preserving their commits. The in-progress Rules work remained separate on `codex/agent-rules`, and was fast-forwarded over main's identical baseline tree without discarding edits. No deployment was performed.
