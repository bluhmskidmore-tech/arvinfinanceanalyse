---
name: moss-page-contract-tieout
description: Use when implementing, reviewing, or closing a MOSS page contract, page-visible metric, endpoint DTO, loading/empty/stale/fallback state, or browser-visible business workflow.
---

# MOSS Page Contract Tie-Out

Use this skill when a MOSS page must prove that what users see matches the governed page contract. It adapts statement/NAV tie-out patterns: the page is the thing under test; the contract and evidence are the source of truth.

## Workflow

1. Identify the page ID, route, primary business question, and required sections from `docs/page_contracts.md` or `moss-metric-contracts`.
2. List the endpoint DTOs, metric IDs, golden samples, and state requirements the page depends on.
3. Verify each displayed metric:
   - exists in the metric dictionary when it is formal
   - preserves unit, precision, and date semantics
   - exposes `result_meta` meaning where required
   - shows fallback, stale data, no data, and loading failure visibly
4. Trace the page path:
   `route -> query/client -> adapter -> selector/view model -> component -> table/chart/card`.
5. Fix only the current page or workflow unless evidence shows a shared layer is the root cause.
6. Add focused tests for changed adapters, selectors, formatters, components, or API contracts.
7. For visible UI changes, verify in the browser against the local app when the target route is known.

## Do Not

- Do not hide fallback, stale, or fail-closed status in debug-only surfaces.
- Do not create new formal metrics from narrative text, labels, UI structure, or preview/vendor fields.
- Do not add frontend calculations that duplicate formal backend logic.

## Completion Evidence

Final reporting should include the page/workflow fixed, root cause, changed files, checks run, and any residual contract gaps.
