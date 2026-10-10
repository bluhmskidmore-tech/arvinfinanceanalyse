# Bond Analysis Foundation Design

## Scope

This design sets up a standalone front-end foundation for a bond analysis and trading surface inside `frontend/src/bond-analysis-foundation/`. The goal is not to refactor the existing MOSS workbench. The goal is to produce a reusable bundle that gives later design work a typed data contract, clear API seams, and compile-safe React skeletons.

## Architecture

The bundle is intentionally thin:

- `data-structures/` owns type contracts for bonds, portfolios, market data, orders, and user preferences.
- `react-components/services/api.ts` owns the REST/WebSocket contract in one place, so hooks and components do not invent URL shapes.
- `react-components/context/BondContext.tsx` owns cross-cutting UI state: preferences, watchlist, selected bond, selected portfolio.
- `react-components/hooks/` binds the API service to React Query and the context state.
- `react-components/` contains presentational shells for layout, dashboard, bonds, charts, trading, and advanced analysis.

This keeps the communication path explicit:

`API response -> typed model -> service -> hook/context -> component`

## UX Direction

The visual baseline is a controlled high-tech trader cockpit rather than a generic admin panel. The skeleton uses large first-screen conclusions, dense metric blocks, explicit fallback/stale messaging, and segmented work areas so later design work can add richer animation without redesigning information hierarchy.

## Error Handling

The service throws `ApiError` with status and details. Components are expected to surface:

- no data
- stale/fallback state
- explicit loading
- fetch failure

No silent placeholder metric should masquerade as formal truth.

## Testing

The initial TDD slice locks three contracts:

1. API service query serialization, POST body handling, and API error propagation
2. Context state transitions for watchlist, theme, and selected bond
3. Representative rendering and interaction flow for dashboard, layout/table, and order form

This is enough to make later implementation changes measurable without coupling the new bundle to existing business pages.
