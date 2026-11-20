# Roadmap and support matrix

## First end-to-end milestone

A fresh local demo discovers and enrolls Sonar, ChatGPT in Chrome, and a
clearly labeled AWS Bedrock fixture. The inventory distinguishes discovery,
enrollment, and coverage. Demonstrate one authorized read and one blocked
write through Sonar and inspect its metadata trail. Browser and cloud
enrollment are inventory workflows. AgentGate's only governed integration
in this demo is Sonar project file reads and writes.

| Track | Documented | Implemented | Verification and next gap |
| --- | --- | --- | --- |
| Local Sonar | [Setup and isolation](local-sonar-governance.md) | Local discovery, isolated launch, history snapshot, file policies, human review and audit | Live Ollama onboarding and file enforcement were verified in the first-run milestone. Repeat the operator walkthrough on this branch. |
| Chrome | [Extension setup](external-discovery.md#chatgpt-in-chrome) | A one-use discovery report, explicit enrollment, revocable credential scoped to future manual reports | API and extension tests use fixtures. Live Chrome and operator testing are pending. Tool actions have no enforcement integration. |
| AWS Bedrock | [CLI and demo mode](external-discovery.md#aws-bedrock-agents) | Read-only discovery and enrollment with an account and region recheck. Explicit demo fixture for offline presentations | Tests verify the fixture and mocked inventory client. An authorized AWS account and live enrollment have not been verified. Tool actions have no enforcement integration. |

The synthetic support, sales and finance application remains available for
compatibility tests. The default launcher uses the real-agent workspace.

## Baseline gaps

The managed workspace uses a shared local reviewer credential. Named users and
reviewer attribution are pending. The file proposal ledger records a relative
path, size, and fingerprint for valid requests. Invalid requests use a redacted
label. Per-deployment path minimization and retention controls are pending.
The historical architecture guide describes the compatibility application.
The current launcher and data boundary are documented in
[Local Sonar governance](local-sonar-governance.md).

## Next increments

- **Local:** Repeat history migration and denied-action checks across
  supported Linux setups. Track connector freshness and verify each governed
  tool separately.
- **Browser:** Validate the unpacked extension in Chrome, then add an
  organization-approved browser deployment path. Evaluate governance at one
  supported external tool endpoint.
- **Cloud:** Verify authorized Bedrock discovery and enrollment against a live
  account. Select one protected tool with an attributable workload identity.
- **Shared administration:** Add named users and reviewer roles, durable
  connector identities and freshness, manual registration, contextual policy
  precedence, and audit privacy coverage. Threat indicator and anomaly work
  follows reliable metadata collection. SSO and multi-tenancy remain future work.
