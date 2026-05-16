# Frontend Agent Notes

Use this file for work under `frontend/`.

## Navigation

- Start with `src/router/routes.tsx` to identify the page route, then move to `src/features/<domain>/`.
- Put domain API work in the relevant domain client module under `src/api/`; keep `src/api/client.ts` as a composition boundary.
- Put mock data near the domain client or existing `src/mocks/` module. Do not add new mock payload blocks to `src/api/client.ts`.
- For page styling, read `../DESIGN.md` and prefer existing tokens, page primitives, CSS modules, or page-local style modules.

## Business display rules

- Do not calculate official finance metrics in the frontend.
- Trace displayed metrics through API response -> adapter/model -> component -> chart/table.
- Check units, precision, `null` vs `0`, date semantics, fallback/stale flags, and mock fallbacks before changing display logic.

## Verification

- From `frontend/`, use targeted Vitest first: `npm run test -- <pattern>`.
- For changed pages, API clients, mocks, adapters, formatters, or selectors, run `npm run debt:audit`.
- For normal frontend code changes, run `npm run lint` and `npm run typecheck` when the touched surface is not purely documentation.
- Use Playwright/browser checks when the change affects visible layout or interaction.
