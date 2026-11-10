# AgentGate interface requirements

Owner requirement: make AgentGate friendlier and easier to read. Look to Geordie
AI for inspiration, but do not copy its interface. This is a design brief, not an
implemented redesign.

## Reference boundary

Reviewed Geordie's public website and public dashboard imagery on November 10,
2026: https://www.geordie.ai/. No access to its private application was used.
Take general principles: clear hierarchy, concise summaries, and understandable
agent/risk context. Create original layouts, writing, components, colors, and
branding. Do not reuse Geordie assets, distinctive illustrations, typography
treatments, proprietary feature names, or screen compositions.

## Original visual direction

Use a calm, practical operations workspace: pale slate background, white content
surfaces, deep ink text, and restrained blue primary actions. Reserve red and
amber for security severity or decisions that need attention. Keep green for
verified successful outcomes; do not imply that an unassessed agent is secure.
Use a system sans-serif font, generous spacing, subtle borders, and a consistent
spacing scale. A dark theme can follow after the core screens are readable.

Default body text should be 16px with approximately 1.5 line height. Supporting
text should generally stay at 14px or larger. Keep long explanations at readable
line lengths; reserve monospace for technical identifiers and code. Avoid
all-uppercase paragraphs, oversized marketing headings inside the workspace,
and repeated decorative cards that make related information harder to compare.

## Information structure

For the existing prototype, retain the supported Overview, Agents, and Activity
routes. Give navigation an obvious current-page state. Introduce Findings,
Threat updates, and Policies only when their underlying features exist; keep
conceptual screens clearly labeled as previews.

- Overview: lead with actions needing attention, then agent coverage and recent
  activity. Present a few useful totals with scope/time context. Place scripted
  demonstrations in a clearly labeled secondary area.
- Agents: searchable list with name, purpose, owner, connection/observation state,
  last activity, and assessed exposure when supported. Use consistent columns
  for comparison and a readable stacked layout on small screens.
- Agent detail: plain-language summary followed by access, findings, and activity.
  Keep technical configuration and raw records available on expansion.
- Activity: readable action descriptions, explicit decision labels, filters,
  timestamps, and expandable technical evidence. Preserve pagination and filters.
- Future finding detail: explain what could happen, why this agent is affected,
  evidence and confidence, recommended fix, and how the fix can be verified.
  Keep severity, applicability, and compromise status distinct.

## Friendly security writing

Use descriptive actions such as "Review request", "View evidence", and "Review
proposed fix". Explain acronyms at first use. For example, explain SSRF as a tool
being tricked into requesting an internal service, alongside its technical name.
Use precise messages: "No findings in the checks completed" rather than "Safe".

Empty states should explain the next step. Distinguish not connected, loading,
no results, unavailable, and insufficient evidence. Show last update and stale
data where relevant. A zero count requires successful loading; use an explicit
unknown/unavailable state when data could not be fetched.

## Interaction and accessibility acceptance

- Support keyboard navigation, visible focus, semantic headings/landmarks, and
  labeled controls. Expand focus treatment to links, summaries, and textareas.
- Target WCAG AA contrast: 4.5:1 for normal text and 3:1 for large text and
  meaningful UI boundaries. Verify actual combinations during implementation.
- Never communicate severity or state by color alone. Add readable labels/icons.
- Make primary touch targets approximately 44px tall; verify at 200% zoom and
  narrow screens without losing actions or essential content.
- Preserve context during polling: no focus theft, disruptive layout jumps, or
  replacement of text the user is editing.
- Review approvals must show agent, requested action, target, consequences,
  policy reason, and current state. Keep approval separate from profile editing
  and proposed remediation; do not alter authorization to simplify the UI.
- Keep synthetic data, unverified inventory, planned integrations, and coverage
  limitations visible and understandable without dominating every section.

## Implementation scope and verification

First redesign the existing HTML/CSS/JavaScript screens without changing API
contracts. Preserve element IDs required by `app.js`, reviewer token handling,
authorization, scenario execution, profile editing, and approval behavior.
No framework migration is required for this visual work.

Inspect the current implementation before editing. Validate connected and
disconnected screens, loading/error/empty states, agent search/profile editing,
activity filters/pagination, and approvals. Check desktop/mobile layouts,
keyboard flow, zoom, and contrast; save screenshots for visual review. Run the
repository's required checks and document any verification limits.
