# Readable interface pass

Implemented on `codex/readable-interface` using the owner's interface/security direction and coding workflow. This changes the existing prototype screens; it does not add findings, threat feeds, discovery, or exposure assessments.

## What changed

- Pale slate workspace, white surfaces, deep text, restrained blue actions, and original AgentGate styling. Body text is 16px; supporting text is 14px or larger. Security states use readable labels as well as color.
- Overview starts with requests needing review, then totals, coverage, and recent activity. Scripted demos and the unconnected adapter scaffold are secondary expandable sections.
- Agents use consistent table columns for purpose, owner, simulated location, observation, and last activity. Mobile rows stack with visible field labels. Agent detail omits the directory so access and profile editing are easier to find.
- Activity retains server-side filters, 20-record cursor pagination, evidence, and approval behavior. Decision labels distinguish blocked, awaiting review, rejected, and simulated execution.
- Pending approvals show agent, requested action/amount, target, policy reason, current state, and simulated consequences before separate approve/reject buttons.
- Disconnected/loading/unavailable/no-results states explain the next step. Zero counts require a successful load. Failed refreshes retain cached data with an explicit stale warning and last-success time.
- Keyed rendering preserves evidence expansion and focus on unchanged records. Profile drafts survive polling. Route changes discard stale responses; disconnect guards cover late responses and post-action refresh messages. Tokens remain in memory only.
- Keyboard support includes a skip link, current-page navigation state, visible focus on links/summaries/inputs/buttons/textareas, focus after navigation, and a useful focus target when a reviewed item leaves a filtered list.

Backend routes, schemas, policy, authorization, and executors are unchanged. Existing element IDs and reviewer/agent separation are preserved. All business effects remain synthetic and model registrations remain unverified.

## Verification

- `make check`: Ruff checks and all 55 Python tests pass. The existing upstream Starlette/httpx TestClient deprecation warning remains.
- `node --check agentgate/static/app.js`: passes.
- `node --test tests/interface.test.cjs`: five dependency-free state regressions pass. They exercise disconnect during response parsing, unavailable data, stale cached totals, evidence/focus preservation on row changes, and disconnect during a completed demo's refresh. Tests use a small DOM double; they do not replace browser checks.
- `make check-interface` runs those JavaScript checks locally with Node.js 18+; no npm packages or frontend build are required. Normal application use and Python checks do not require Node. CI also runs the interface tests on its existing Node-enabled runner.
- Browser checks: initial disconnected/empty state, invalid credentials, all fourteen cases, finance approval, support rejection, agent search, profile editing/model inventory, unsaved draft preservation after an incoming action, evidence/focus preservation after a new request, search-empty guidance, cursor navigation on 41 QA records, keyboard sign-in, and disconnect cleanup.
- Server stopped during a refresh: cached data stayed visible with a stale warning; recovery was checked after restarting. The temporary server used port 8011 and was stopped after QA. Production/local port 8000 was not used by QA.
- Desktop at the default 1280px viewport and narrow 390px layout were visually checked. Activity filters and stacked agent rows had no horizontal page overflow. The checked inputs/buttons met the 44px minimum target.
- A 640px reflow check represented half the default desktop width (200%-equivalent reflow). Native browser zoom shortcuts did not change the in-app browser scale; actual 200% native zoom remains unverified. Viewport overrides were reset.

### Contrast checks

WCAG relative-luminance calculations for the actual CSS values:

| Pair | Ratio |
|---|---:|
| Body ink on workspace | 13.22:1 |
| Supporting text on workspace | 5.60:1 |
| Primary action text/background | 6.62:1 |
| Link on white | 7.32:1 |
| Blocked / awaiting-review / executed badges | 6.25 / 6.06 / 6.54:1 |
| Neutral badge | 5.72:1 |
| Input boundary on white | 3.14:1 |
| Focus outline on white | 6.62:1 |

These checks cover primary text, labels, badges, controls, and focus styling. They are not a complete WCAG audit. A full screen-reader audit and native browser zoom check remain follow-up validation.

## Review screenshots

Captured with disposable synthetic QA data; tokens are not visible.

- [Overview](images/interface/overview.png)
- [Agent comparison](images/interface/agents.png)
- [Decision context](images/interface/activity.png)
- [Mobile agent rows](images/interface/mobile-agents.png)
- [Disconnected state](images/interface/disconnected.png)

## Run the task branch locally

From this checkout (or a clean clone after fetching the branch):

```bash
git fetch origin
git switch codex/readable-interface
.venv/bin/python -m agentgate
```

Keep the existing `.env` and database. Reconnect after reloading the browser. Merging into `main` and deployment remain separate, explicitly authorized decisions.
