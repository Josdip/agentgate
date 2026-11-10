# Coding with the AgentGate assistant

Open this repository folder in Codex. `AGENTS.md` supplies project guidance;
Codex supplies the running model and coding tools. This setup does not create a
separate agent service or route Codex's tools through AgentGate enforcement.

## Environment

Requires Python 3.12+ and Git. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.lock
.venv/bin/pip install --no-deps --no-build-isolation -e .
make check
```

Start the local prototype with `.venv/bin/python -m agentgate`. See
[development](development.md) for reviewer connection and synthetic demos. Keep
local tokens and databases out of commits. No model API key is required for this
prototype; Codex authentication is separate from application configuration.

## Task cycle

1. Describe a feature, bug, or security issue and the expected result.
2. Inspect the checkout and fetch upstream changes. For a new task, start a
   focused branch from current upstream `main` after preserving local work:

   ```bash
   git status --short
   git fetch origin
   git switch -c codex/describe-the-task origin/main
   ```

   For an existing clean task branch, `git pull --ff-only` updates it from its
   configured upstream. Divergence requires inspection rather than force/reset.
3. Implement, test, and review the final diff. Run `make check`.
4. Stage explicit task paths, commit descriptively, and push the task branch:

   ```bash
   git diff --check
   git diff
   git add path/to/changed-file
   git diff --cached
   git commit -m "feat(area): describe behavior"
   git push -u origin HEAD
   ```

5. Review the branch on GitHub and check CI. Merging and deployment are separate
   decisions. Existing CI already runs Ruff lint/format checks and Pytest on
   pushes and pull requests.

Git transport needs its own authentication on each machine. Do not paste tokens
into chat or remote URLs. The connected GitHub app and terminal Git may have
different credentials or permissions.

## Example requests

- "Implement [idea], test the behavior, review the diff, and push a task branch."
- "Reproduce [bug], fix the cause, and add a regression test."
- "Review authorization boundaries. Fix confirmed issues with regression tests."
- "Improve the existing dashboard using docs/interface-direction.md. Preserve
  authentication, approval behavior, and the current API."

The [security direction](security-product-direction.md) and
[interface direction](interface-direction.md) capture future scope. Read those
alongside current architecture; they are not evidence that features exist.
