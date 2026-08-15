# React Router Security Boundary

## Scope

This note documents the React Router v7 follow-up boundary for the frontend app.

## Current state

- `frontend/package.json` and `frontend/package-lock.json` pin `react-router-dom` and `react-router` at `7.18.2`.
- The production app entry remains client-side: `frontend/src/main.tsx` renders `App`, and `frontend/src/router/RouteRegistry.tsx` uses `createBrowserRouter` with `RouterProvider`.
- The app does not ship `@react-router/dev`, `react-router.config.*`, `entry.server.*`, `ServerRouter`, `RSCHydratedRouter`, `createRequestHandler`, or `routeRSCServerRequest` in production source.
- Production route definitions in `frontend/src/router/routes.tsx` do not declare `loader:` or `action:` route-module fields.

## Security note

The React Router maintainer advisory lists `7.18.2` as the patched v7 release,
and the v7.18.2 changelog plus maintainer PR `#15353` identify the release as a
backport of the `GHSA-qwww-vcr4-c8h2` RSC CSRF fix. The global GitHub Advisory
Database/OSV record still models one continuous `>=7.12.0,<8.3.0` range, so its
current result for `react-router@7.18.2` is a metadata false positive pending the
upstream split-range correction.

The client-only, no-RSC boundary above remains defense in depth. The
`frontend/src/test/routerSecurityBoundary.test.ts` guard fails CI if those APIs
are introduced without review.

CI stores each raw scan with a separate machine-readable completion/coverage
receipt and adjudication output from `scripts/osv_reconciliation_gate.py`. On
2026-08-15, the pinned OSV-Scanner v2.3.0 returned no findings for the resolved
lockfiles. In accordance with the repository policy for corrected advisory
metadata, the obsolete pending exact-tuple record was removed rather than
activated or renewed. The client-only boundary test remains defense in depth;
any reintroduced finding will fail closed without a new active record.

Primary sources:

- https://github.com/remix-run/react-router/security/advisories/GHSA-qwww-vcr4-c8h2
- https://github.com/remix-run/react-router/releases/tag/react-router%407.18.2
- https://github.com/remix-run/react-router/pull/15353
- https://github.com/github/advisory-database/pull/8936
