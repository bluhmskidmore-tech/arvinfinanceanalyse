# Prompt Preflight Decisions

Date: 2026-07-05
Repository: F:\MOSS-V3

The original 13 remediation prompts were based on a 2026-05-07 snapshot. Current decisions must be based on the live dirty worktree, not the old snapshot alone.

| Prompt | Current Status | Current Decision |
| --- | --- | --- |
| 01 | Build blocker cleared | `npm run build` now passes after stock-analysis `return_10d` contract alignment. Keep dependency peer conflict and StockAnalysisPage size guard as separate issues. |
| 02 | Not executed | Backend collection currently succeeds: 5555 tests collected. Old collection-failure preflight is false. |
| 03A | Executed | `/ui/home/snapshot` was promoted to landed and covered by backend tests. Pro should verify route semantics and ownership before final closure. |
| 03B | Not executed | Mutually exclusive with 03A. |
| 04 | Rewrite candidate | Backend old STUB / zero placeholder scan did not reproduce; frontend Numeric nullability still deserves a fresh frontend-only audit. |
| 05 | Rewrite or close candidate | Current `client.ts` / mock formal-contamination evidence differs from the old prompt; one intentional test override remains. |
| 06 | Executed | Three endpoints received `response_model` after real response round-trip validation. Global API envelope coverage remains unaudited. |
| 07 | Rewrite candidate | Route registry and cube query auth state differ from the old snapshot; hardening should be re-audited against current code. |
| 08 | Rewrite candidate | Unconditional header trust is no longer present; gateway secret / proxy allowlist remains a separate security design question. |
| 09 | Close or monitor | `frontend/src/api/client.ts` is no longer the old giant client. Enforce no-growth guardrails rather than rerunning the stale prompt. |
| 10 | Keep open / decide | `bond-analysis-foundation` still has test references, so zero-reference migration preflight is false. Decide whether to retain historical test assets. |
| 11 | Blocked / rewrite after 07 | Depends on the current route-boundary decision. |
| 12 | Executed | Bond analytics Numeric / warning-code / frontend parser chain is covered by targeted backend and frontend tests. |
| 13 | Blocked by 10 | Depends on the `bond-analysis-foundation` migration decision. |

## Specific Open Questions For Pro

1. Can 03A / 06 / 12 be closed with the current evidence, or do they need additional tests?
2. Should Prompt 04 become a frontend-only Numeric nullability prompt?
3. Should Prompt 07 become a current route registry / cube query authorization hardening prompt?
4. Should Prompt 08 become a gateway-secret / proxy-allowlist security prompt?
5. Should the StockAnalysisPage size guard be treated as release-blocking technical debt or a separate cleanup lane?
