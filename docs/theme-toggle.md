# Light and dark themes

The header's **Dark theme** button switches the whole workspace between light and dark. Light is the default until a preference is saved. The control has a visible focus indicator, a minimum 44px target, and `aria-pressed` state; native button keyboard controls work.

The choice persists in `localStorage` under `agentgate.theme`. Only `light` and `dark` are accepted. Storage failures are caught so the toggle still works for the current page. No credentials or workspace records are stored by this feature; reviewer tokens remain in memory as before.

A small self-hosted script applies the saved choice before styles load. It respects the existing Content Security Policy; no inline scripts, framework, external assets, or API changes are introduced. Semantic CSS colors cover native form controls, tables, evidence, pending approvals, stale/error states, and decision badges. Mobile header controls wrap without hiding the demo label.

## Verification

- `make check`: 55 Python tests and Ruff checks pass (existing TestClient deprecation warning remains).
- `node --test tests/interface.test.cjs`: nine tests pass, including four theme cases: both toggle directions, restoration before DOM ready, invalid saved values, and blocked browser storage.
- Browser: mouse and Space-key toggle, visible keyboard focus, persistence after reload, navigation without losing the theme, connected demo execution, approval context, and return to light checked.
- Default desktop and 390px mobile checked; toggle height was 44px and no horizontal page overflow was observed. Viewport override reset and temporary port-8011 server stopped.
- Checked light/dark text pairs exceed 4.5:1, including form text, links, code, table headings, and all decision badges. Dark body contrast is 15.13:1, supporting text on panels 8.06:1, primary buttons 8.56:1; dark input boundaries are 5.17:1. These checks are not a complete accessibility audit; the broader zoom/screen-reader limits in the interface guide still apply.

## Previews

- [Dark agent list](images/themes/dark-agents.png)
- [Dark approval context](images/themes/dark-activity.png)
- [Mobile header and controls](images/themes/dark-mobile.png)

The change is on `codex/theme-toggle`, building on `codex/readable-interface`. Neither branch is merged to `main` by this task.
