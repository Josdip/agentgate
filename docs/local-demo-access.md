# Local demo access

> Historical synthetic workspace. For the default workspace on this branch, see
> [Local Sonar governance](local-sonar-governance.md).

Start `.venv/bin/python -m agentgate` and open http://127.0.0.1:8000.
No sign-in, reviewer-token entry, model key, or external service is needed.
Select **Try a $250 refund request**, inspect the decision, and approve or reject
it. Agents shows the three sample identities; Rules changes their enforced
permissions; Activity provides searchable, paginated decisions.

## Trust boundary

This mode intentionally grants the local browser reviewer privileges, including
editing rules and approving simulated actions. Use synthetic data only. It is
not production authentication and must not be publicly hosted or connected to
real business tools. Other local programs can imitate browser requests.

The launcher binds to loopback and disables proxy-header interpretation. The
browser obtains a per-process HttpOnly, SameSite=Strict cookie scoped to `/api`.
Session creation and cookie-authorized writes require the matching Origin and
a custom header. Cookie access also checks the actual loopback client and local
hostname. No reviewer bearer credential is returned to JavaScript or saved in
browser storage. Restarting the server invalidates the session; reload or select
Retry connection. Failed mutations are not automatically replayed.

Agent API calls still require their own credential and server-owned identity.
An explicit agent bearer credential cannot borrow browser reviewer access.
Tool schemas, default deny, approval transitions, and policy revisions remain
enforced. All business effects are simulated; model inventory is unverified.

## Optional authenticated mode

Set `AGENTGATE_DEMO_MODE=0` in `.env` and restart to restore manual reviewer
credential entry. The `create_app()` factory defaults to authenticated mode;
demo access requires an explicit boolean `demo_mode=True`. Internal agent and
reviewer credentials remain distinct even in the local demo. Static bearer
credentials are development authentication, not a production identity system.

Older walkthroughs that mention entering a reviewer token describe this optional
mode. Production use still needs individual identities, roles, tenant isolation,
TLS, protected audit storage, and reliable external-tool execution.
