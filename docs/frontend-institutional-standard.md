# MOSS Frontend Institutional Standard

**Purpose:** Define the release bar for a top investment-bank-grade MOSS workbench. This is not a visual beautification checklist. It is a decision-surface standard for business-critical pages.

**Scope:** Frontend page structure, evidence surfacing, responsive behavior, accessibility, browser verification, and local regression coverage.

**Non-goals:** Backend refactor, database/schema changes, auth changes, scheduler/cache changes, metric-definition changes, or retiring governance markers without source/lineage evidence.

---

## Standard

A page is flagship-ready only when a desk user can answer four questions in the first screen:

1. Can I trust this page today?
2. What is the primary business conclusion?
3. Which metrics or blockers support that conclusion?
4. Where do I go next if the conclusion is blocked or needs drill-down?

The page must keep source/date/unit/status evidence visible on desktop and mobile. Governance, stale, fallback, no-data, and temporary-exception states must not be hidden to improve visual density.

## Scorecard

Score each dimension from `0` to `4`.

| Dimension | 0 | 2 | 4 |
| --- | --- | --- | --- |
| Business trust | Metrics lack source/date/unit/status | Some evidence visible, gaps remain | All key values expose source, date, unit, status, fallback/stale/no-data semantics |
| First-screen closure | Title or navigation dominates; conclusion is below fold | Conclusion visible but primary blockers/actions are delayed | Title, controls, trust verdict, top metrics, blocker/action fit without overlap |
| Visual hierarchy | Decorative or noisy; no clear reading order | Main sections are identifiable | Calm, dense, aligned, with one obvious primary conclusion |
| Responsive resilience | Mobile overflow or critical content buried | Mobile works but is inefficient | 390px mobile, 768px tablet, and desktop are usable with no horizontal overflow |
| Accessibility/keyboard | Missing labels/focus/semantics | Basic labels and focus exist | Keyboard path, focus states, semantic labels, and non-color status cues are clear |
| Token/design-system alignment | One-off colors, radii, spacing, shadows dominate | Mostly tokenized with page-local exceptions | Existing tokens/primitives drive layout; page CSS only covers page-specific needs |
| Runtime cleanliness | Fallback route, permanent loading, blocking console errors | Minor non-blocking warnings | No fallback route, no permanent loading, no blocking console errors |

## Pass Levels

| Score | Level | Meaning |
| --- | --- | --- |
| 24-28 | Flagship-ready | Suitable as an institutional workbench reference page |
| 20-23 | Releaseable with watch items | Good enough to use, but not a flagship proof point |
| 16-19 | Acceptable but not flagship | Useful but needs a focused improvement pass |
| Below 16 | Not releaseable | Fails trust, closure, or resilience expectations |

## Required Evidence

Every flagship page needs:

- Desktop browser check at `1440px`.
- Tablet browser check at `768px`.
- Mobile browser check at `390px`.
- No horizontal overflow at each viewport.
- No fallback route or permanent loading state.
- No blocking console errors.
- Screenshot or measurement evidence for first-screen closure.
- Page-specific component tests.
- Live-route readiness/smoke tests where route contracts apply.
- `npm run lint`.
- `npm run typecheck`.
- `npm run debt:audit` for changed pages, clients, mocks, adapters, formatters, or selectors.
- `npm run build`.

## Evidence Authority

Use the project MCP evidence servers before changing metric definitions, units, formal-use status, governance markers, lineage claims, or source freshness:

- `moss-metric-contracts`
- `moss-lineage-evidence`
- `moss-data-catalog`
- `gitnexus`

If these tools are unavailable, use local code/tests/docs only for layout and display improvements, retain governance markers, and record the residual risk.

## Current Assessment

As of this plan update:

- `/cross-asset` is the strongest flagship proof point. It has browser evidence across desktop/tablet/mobile and no horizontal overflow in the latest pass.
- `/ledger-pnl` has reached page-level Gate A closure after the latest first-screen decision-stack pass. It now has targeted component tests, live-route tests, lint, typecheck, debt audit, build, and desktop/tablet/mobile browser evidence.
- `/macro-toolkit` has reached Gate B page-level closure after the mobile decision-brief and governance-gate compression pass. The mobile brief now exposes readiness, blocker, next action, and data-health signoff before the first screen gives way to deeper operations.
- `/stock-analysis` has reached Gate C page-level closure after the narrow-screen decision-order pass. Mobile and tablet now expose signal conclusion, review queue, consensus status, and closed-loop trust evidence before chart exploration.
- `/product-category-pnl` has reached Gate D page-level closure after the formal-readiness band and governed first-screen preview pass. It now exposes report date, view, basis, quality, vendor, fallback, generated-at, formal metric anchors, and a governed category-row preview before the full formal readout.
- `/pnl-attribution` has reached Gate E page-level closure after the attribution decision-strip pass. It now exposes active lens, report-date resolution, source path, view period, quality, fallback, comparison mode, next action, and product-category versus formal FI boundaries before chart-heavy drill-down.
- `/bond-analysis` has reached Gate F page-level closure after the fixed-income decision cockpit pass. It now exposes report date, period, client mode, action-attribution conclusion, warning count, DV01/duration/PnL availability, fallback/no-data language, and next action before module detail.
- The current flagship scope is `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, `/stock-analysis`, `/product-category-pnl`, `/pnl-attribution`, and `/bond-analysis`. Other routes still need their own scorecard before being described as flagship-ready.
- The next optimization layer is system hardening: mobile tabular readouts, accessibility `4/4`, and MCP-backed metric/lineage certification.
