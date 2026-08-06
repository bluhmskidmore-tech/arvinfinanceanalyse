# React Router Security Boundary

## Scope

This note documents the React Router v7 follow-up boundary for the frontend app.

## Current state

- `frontend/package.json` and `frontend/package-lock.json` pin `react-router-dom` and `react-router` at `7.18.2`.
- The production app entry remains client-side: `frontend/src/main.tsx` renders `App`, and `frontend/src/router/RouteRegistry.tsx` uses `createBrowserRouter` with `RouterProvider`.
- The app does not ship `@react-router/dev`, `react-router.config.*`, `entry.server.*`, `ServerRouter`, `RSCHydratedRouter`, `createRequestHandler`, or `routeRSCServerRequest` in production source.
- Production route definitions in `frontend/src/router/routes.tsx` do not declare `loader:` or `action:` route-module fields.

## Security note

`npm audit` still reports the upstream advisory `GHSA-qwww-vcr4-c8h2` on `react-router@7.18.2`. In this codebase that advisory is not currently reachable because the app is not using React Router framework/RSC server APIs. The new `frontend/src/test/routerSecurityBoundary.test.ts` guard is intended to fail CI if those APIs are introduced later without an explicit review and follow-up.
