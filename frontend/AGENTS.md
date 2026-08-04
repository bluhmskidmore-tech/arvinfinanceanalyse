# Frontend AGENTS.md

These rules apply to work under `frontend/`.

## Classify the change first

Use the lightest tier that safely covers the task. Escalate only when evidence crosses a boundary.

### Tier 1: visual-only

Copy, spacing, color, typography, responsive layout, and presentation changes that do not alter data access, business meaning, calculations, filters, dates, units, or displayed values.

- Inspect the page/component and its local styles or tokens.
- Do not perform metric-contract, lineage, catalog, or full data-flow tracing unless the visual work exposes a correctness issue.
- Use the narrowest relevant lint/typecheck plus a browser or component check.
- Do not add business-logic tests when business logic did not change.

### Tier 2: page-local business display

A single page changes an adapter, formatter, selector/computed model, filter, metric presentation, date, unit, fallback, or state behavior.

- Trace only the affected metric path.
- Use relevant metric-contract and lineage evidence.
- Query the catalog only when source columns, availability, or report dates are material.
- Add or update the smallest useful adapter, formatter, selector/model, or component-path test.
- Run page/workflow-scoped checks first.

### Tier 3: shared or cross-page business logic

Shared clients, selectors, formatters, formal calculations, cross-page state, or other code used by multiple workflows.

- Follow root GitNexus impact requirements before editing shared symbols.
- Check affected contracts, lineage, dates, units, fallbacks, and downstream consumers.
- Warn before HIGH or CRITICAL impact edits.
- Widen tests/build checks in proportion to the demonstrated blast radius.

## Navigation and architecture

- Start at `src/router/routes.tsx`, then move to `src/features/<domain>/`.
- Keep official finance calculations out of the frontend.
- Put new or materially changed endpoint implementations in the relevant domain client under `src/api/`; keep `src/api/client.ts` as a composition boundary.
- Keep domain mocks near the domain client or in an existing `src/mocks/` module. Do not add mock payload blocks to `src/api/client.ts`.

## Affected metric verification

For each metric affected by the change, trace the relevant path:

`API response -> adapter/transformer -> store/state -> selector/computed model -> component -> chart/table`

Check only applicable risks:

- unit and conversion: 元 / 万元 / 亿元 / % / bp
- precision, rounding, and Decimal/float/string serialization
- `null` vs `0` vs `undefined` vs `NaN`
- trade date vs natural date; daily vs month-end vs YTD
- `as_of_date`, fallback/cached date, and stale state
- mock or hard-coded fallbacks
- duplicate frontend calculations
- inconsistent filters across cards, charts, and tables

Explicitly surface material no-data, stale-data, fallback-date, loading-failure, and unconfirmed-definition states.

## UI and debt guardrails

- Each page should answer one primary business question first, with the main conclusion visible on the first screen.
- Read `../DESIGN.md` before changing layout, color, typography, or spacing.
- Prefer design tokens, page primitives, CSS modules, or page-local style modules.
- Do not add repeated `style={{ ... }}` layout blocks. A truly local, non-repeated dynamic inline style is acceptable.
- Do not add visual complexity unless it improves a decision.
- Do not raise frontend debt baselines without explicit justification.

## Evidence and validation

- Tier 1 requires no business-data MCP evidence unless business behavior is exposed or changed.
- Tier 2 uses `moss-metric-contracts` and `moss-lineage-evidence` for the affected metric; use `moss-data-catalog` only when source/date availability matters.
- Tier 3 also uses GitNexus context/impact and checks affected downstream consumers.
- Use Playwright/browser verification when visible behavior changes.
- Run targeted Vitest first: `npm run test -- <pattern>`.
- Run `npm run debt:audit` when changing pages, API clients, mocks, adapters, formatters, or selectors.
- Run `npm run lint` and `npm run typecheck` for normal frontend code changes; documentation-only work is exempt.
