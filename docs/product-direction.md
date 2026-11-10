# Product direction: understandable agent oversight for smaller businesses

## Product promise

Know which AI agents your business uses, what they can access, what they are doing, and what needs your attention.

The intended customer is a small or medium business using agents without a dedicated AI security team. Lead with business questions and actions, not tool-call terminology or unexplained scores. This document describes the product destination; it does not claim all features exist today.

## Required capabilities

| Business question | Intended experience | Evidence needed |
|---|---|---|
| How many agents do we have? | Count and searchable named agent directory; distinguish total known, recently active, and needing attention | Stable IDs, lifecycle status, last observed time; exclude duplicate installations |
| Where are they running? | Cloud, employee device, or browser location with owner and source | Connector/endpoint/extension reporting; label manually registered locations unverified |
| What can each agent access? | Tools, model providers/models, permissions, and understandable access summaries | Separate configured inventory from verified connections and observed tool/model use |
| What is each agent doing? | Plain-language timeline, such as “Support agent requested a $250 refund; waiting for your approval” | Timestamped events, identity, affected resource, actual outcome, inspectable technical evidence |
| How risky is it? | Explain configured exposure and observed behavior separately; show reasons and next steps | Versioned transparent rules, sensitive permissions, action history, recency and coverage |
| What should I do next? | A prioritized “Needs attention” view with approve/reject, restrict access, or investigate actions | Link each recommendation to evidence and show whether AgentGate can enforce it |

## Risk communication

Configured risk answers “What could this agent do with its current access?” Consider data sensitivity, write/delete/spending permissions, external destinations, and required human approvals.

Observed risk answers “What concerning behavior have we actually seen?” Consider unauthorized access attempts, blocked transfers, repeated violations, and unexpected access changes. A blocked attempt is different from a completed data transfer. An approved sensitive action is different from a policy violation.

Start with Low / Medium / High / Unknown, concise reasons, last assessment time, and a suggested action. Do not imply a calibrated probability or attach an unexplained 0–100 number. Show visibility coverage separately: an agent with no telemetry is Unknown, not Low risk. High configured access can remain concerning even if no violations have been observed.

Any future score must have versioned rules, reproducible examples, change history, and evidence links. Record the assessment version when storing results. Keep configured exposure and observed behavior visible even if an overall attention level is later introduced.

## Main product surfaces

1. Overview: known agents, active agents, coverage gaps, agents needing attention, recent changes.
2. Agent directory: names, owners, purpose, location, activity, configured risk, observed risk.
3. Agent profile: model/tool connections, effective permissions, human-readable activity, risk reasons, historical changes.
4. Needs attention: prioritize decisions with a clear business consequence and appropriate action.
5. Connections: onboard a reporting source and show exactly what it can observe and enforce.
6. Showcase: six scripted cases plus a separate integration scaffold for genuine agent demonstrations.

Examples of preferred language: “Tried to read payroll records; blocked,” “Can send data outside your company,” and “No activity received for two days.” Technical rule IDs remain available in expandable evidence views.

## Visibility and enforcement boundaries

A gateway sees the calls routed through it. It cannot enumerate every cloud agent, endpoint process, or browser agent automatically. Broader coverage requires explicit integrations, endpoint reporting, and browser instrumentation with suitable access. Future source onboarding must document prerequisites, freshness, deduplication, limits, and whether actions are only observed or can be blocked.

Distinguish Registered / Reporting / Stale / Disconnected. Treat “Not observed” as a visibility gap. Do not call registered model names connected without verification. Never market the current local prototype as discovering or protecting all company agents.

## Delivery priority

First make a multi-agent directory and plain-language activity useful, then add explainable configured/observed risk. Demonstrate one real agent through the integration scaffold before expanding supported environments. Add cloud, endpoint, and browser sources incrementally with clear coverage labels. Keep the six scripted cases reproducible throughout.

The first useful sales demonstration should answer: “Here are your agents, here is what each can do, here is what happened, and here is the one decision you need to make.” Validate customer demand, onboarding effort, pricing, and claims separately; these are product hypotheses rather than market research findings.
