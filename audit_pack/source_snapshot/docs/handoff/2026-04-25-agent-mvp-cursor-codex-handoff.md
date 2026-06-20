# Cursor / Codex Handoff — MOSS Read-Only Agent MVP Frontend Phase

## Context

Hermes has completed the backend-first slice for the MOSS read-only Agent MVP. Continue from this plan:

- `docs/plans/2026-04-25-moss-read-only-agent-mvp.md`

Current repo path:

- Windows: `F:\MOSS-V3`
- WSL: `/mnt/f/MOSS-V3`

Follow project guardrails:

- `AGENTS.md`
- `CLAUDE.md`
- `backend/app/AGENTS.md` if touching backend
- `tests/AGENTS.md` if touching tests

Important: Agent enablement is an explicit Agent lane, not ordinary repo-wide Phase 2 formal-compute cleanup.

## Already completed by Hermes

Backend Agent MVP tasks 1-3 are implemented:

1. Existing `/api/agent/query` enabled-mode contract tests verified.
2. Agent report-date resolution now supports page context fallback:
   - `filters.report_date`
   - `context.report_date`
   - `context.current_filters.report_date`
   - latest available governed date
3. Agent response now supports passive `suggested_actions`:
   - new `AgentSuggestedAction` schema
   - `AgentEnvelope.suggested_actions`
   - envelope assembly in `AnalysisViewTool`
   - passive suggestions for portfolio overview and PnL summary
4. Fixed GitNexus question-path parsing to recognize POSIX `/path/.gitnexus` references as well as Windows-style usage.
5. Added tests for report-date context precedence and suggested action schema.

Validation already run:

```bash
uv run --project backend python -m pytest tests/test_agent_api_contract.py tests/test_agent_intent_routing.py -q
```

Result:

```text
28 passed in 31.44s
```

## Files changed by Hermes in this slice

Backend/tests:

- `backend/app/agent/schemas/agent_response.py`
- `backend/app/agent/schemas/__init__.py`
- `backend/app/agent/tools/analysis_view_tool.py`
- `backend/app/services/agent_service.py`
- `backend/app/services/gitnexus_service.py`
- `tests/test_agent_api_contract.py`
- `tests/test_agent_intent_routing.py`

Docs:

- `docs/plans/2026-04-25-moss-read-only-agent-mvp.md`
- this handoff file: `docs/handoff/2026-04-25-agent-mvp-cursor-codex-handoff.md`

Note: There were pre-existing unrelated modified files before Hermes started, mostly cross-asset / market-data / macro files. Do not touch them unless your task requires it.

## Recommended next work for Cursor/Codex

Continue from plan tasks 4-7.

### Task 4 — Frontend Agent API client

Create:

- `frontend/src/api/agentClient.ts`

Modify:

- `frontend/src/api/client.ts`
- optionally `frontend/src/api/contracts.ts` if you prefer central shared types
- frontend tests: `frontend/src/test/ApiClient.test.ts` or new `frontend/src/test/AgentClient.test.ts`

Required behavior:

- Add `queryAgent(request)` method to `ApiClient`.
- POST to `${baseUrl}/api/agent/query`.
- Request supports:
  - `question`
  - `basis?: "formal" | "scenario" | "analytical"`
  - `filters?: Record<string, unknown>`
  - `position_scope?: string`
  - `currency_basis?: string`
  - `context?: Record<string, unknown>`
- Response supports:
  - `answer`
  - `cards`
  - `evidence`
  - `result_meta`
  - `next_drill`
  - `suggested_actions`
- 503 disabled response should show friendly error, not crash with unclear text.
- Mock mode should return stable mock Agent response.

Guardrail:

- Do not grow `frontend/src/api/client.ts` with large endpoint blocks. Put actual method implementation in `agentClient.ts`; compose in `client.ts` only.

Suggested test command:

```bash
cd frontend
npm test -- AgentClient
npm test -- ApiClient
npm run typecheck
```

### Task 5 — Minimal reusable Agent panel

Create:

- `frontend/src/features/agent/AgentPanel.tsx`
- optional `frontend/src/features/agent/AgentPanel.styles.ts`
- `frontend/src/test/AgentPanel.test.tsx`

Required props:

```ts
export type AgentPanelProps = {
  pageId: string;
  reportDate?: string | null;
  currentFilters?: Record<string, unknown>;
  defaultQuestion?: string;
};
```

Required behavior:

- User can enter question.
- Submit calls `client.queryAgent({ question, basis: "formal", filters, context })`.
- Context must include:
  - `page_id`
  - `report_date`
  - `current_filters`
- Show loading state.
- Show answer.
- Show compact evidence, at least:
  - `quality_flag`
  - `tables_used`
- Show `suggested_actions` if present, as passive chips/buttons only. Do not execute backend side effects.
- Friendly disabled/error message.

### Task 6 — Mount Agent panel on one low-risk page

Recommended: choose one stable page only, not global `WorkbenchShell` yet.

Candidate:

- `frontend/src/features/workbench/pages/DashboardPage.tsx`

Do not mount globally in v1 unless explicitly approved.

Required:

- Add `AgentPanel` to selected page.
- Pass page-specific context.
- Keep layout simple and avoid repeated inline style blocks.
- Add/update the page test.

Suggested validation:

```bash
cd frontend
npm test -- DashboardPage
npm run typecheck
npm run debt:audit
```

### Task 7 — Agent runbook

Create:

- `docs/AGENT_MVP_RUNBOOK.md`

Include:

- How to enable locally: `MOSS_AGENT_ENABLED=true`
- Endpoint: `POST /api/agent/query`
- Supported intents
- Request/response examples
- Safety boundaries
- Disabled mode meaning
- Troubleshooting:
  - 503 disabled
  - no report dates
  - unknown intent
  - stale/fallback quality flag

## Important backend response shape after Hermes changes

`AgentEnvelope` now includes:

```json
{
  "answer": "...",
  "cards": [],
  "evidence": {
    "tables_used": [],
    "filters_applied": {},
    "sql_executed": [],
    "evidence_rows": 0,
    "quality_flag": "ok"
  },
  "result_meta": {
    "trace_id": "...",
    "basis": "formal",
    "result_kind": "agent.pnl_summary",
    "formal_use_allowed": true,
    "source_version": "...",
    "vendor_version": "...",
    "rule_version": "rv_agent_mvp_v1",
    "cache_version": "...",
    "quality_flag": "ok",
    "scenario_flag": false,
    "tables_used": [],
    "filters_applied": {},
    "sql_executed": [],
    "evidence_rows": 0,
    "next_drill": []
  },
  "next_drill": [],
  "suggested_actions": [
    {
      "type": "inspect_lineage",
      "label": "查看损益来源",
      "payload": {"metric_key": "total_pnl", "report_date": "2026-03-31"},
      "requires_confirmation": true
    }
  ]
}
```

## Backend validation to re-run before final handoff

```bash
uv run --project backend python -m pytest tests/test_agent_api_contract.py tests/test_agent_intent_routing.py -q
```

Expected currently:

```text
28 passed
```

## Do not do in this phase

- Do not add arbitrary SQL Agent.
- Do not wire an LLM provider yet.
- Do not enable write/refresh actions from the panel.
- Do not mount Agent globally across all pages.
- Do not refactor unrelated API clients or page layouts.
- Do not touch unrelated pre-existing cross-asset/market-data modified files.
