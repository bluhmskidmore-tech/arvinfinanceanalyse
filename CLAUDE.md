# CLAUDE.md

`AGENTS.md` is the authoritative project policy. Mission and scope, navigation, business evidence, protected boundaries, file encoding, GitNexus, and the work/validation protocol live there and are **not** repeated here — read it first. This file adds only what `AGENTS.md` does not cover.

## Architecture boundaries

Preserve:

`frontend -> api -> services -> (repositories / core_finance / governance) -> storage`

- Official finance calculations belong only in `backend/app/core_finance/`.
- Frontend code must not recreate official finance metrics.
- API routes stay thin: validate, authorize, call services, and return responses.
- "Authorize" here means RBAC only (`backend/app/security/auth_context.py::ensure_user_allowed`).
  There is no authentication layer in this repo: no API key, bearer/JWT, session, or gateway token
  check exists. Identity comes from `X-User-Id`/`X-User-Role` headers (trusted only when
  `MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST` is on), then `MOSS_USER_ID`/`MOSS_USER_ROLE`, then the
  `anonymous`/`viewer` fallback. `validate_auth_startup_guardrails()` returns immediately when
  `environment == "development"`, which is the default. Do not describe any route as authenticated.
- API/service DuckDB access is read-only; writes flow through tasks.
- Changes to H/A/T mapping, issued-bond exclusion, FX mid-price conversion, 514/516/517 merging, or Formal/Scenario separation require targeted tests and an impact report.

## Reporting increment

For finance work, explain any impact on formal calculations in `backend/app/core_finance/`. Other report requirements come from `AGENTS.md`.

## Design

Before changing interface layout, color, typography, or spacing, read `DESIGN.md` and use `frontend/src/theme/designSystem.ts` plus existing page-local primitives.
