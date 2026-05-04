# MOSS Read-Only Agent MVP Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Enable a safe, read-only MOSS in-system Agent that can answer page/business-data questions through existing API/service/repository boundaries, with evidence and lineage-style metadata.

**Architecture:** Keep the current FastAPI route `/api/agent/query` and existing `backend/app/agent/*` runtime. Do not build a general LLM/autonomous executor in this MVP. The Agent remains deterministic and tool-routed: request -> intent routing -> whitelisted read-only tool/service -> `AgentEnvelope` with answer, cards, evidence, and `result_meta`. Frontend adds a small page-context Agent panel that calls the existing unified API port through `/api/agent/query`.

**Tech Stack:** FastAPI + Pydantic backend; existing DuckDB/Postgres repositories only through read paths; React + Vite + React Query-style page patterns; Vitest/pytest tests.

---

## Non-negotiable boundaries

- Do not enable arbitrary SQL execution from user text.
- Do not write DuckDB/Postgres from the Agent request path.
- Do not trigger refresh/materialize tasks in v1; return suggested actions only.
- Do not add formal financial calculations to frontend or API route layer.
- API route only validates/enriches request and calls service.
- Service/tool layer may call existing read-only services/repositories.
- All answers must expose evidence: tables/endpoints used, filters, quality flag, source/cache/rule versions when available.
- Keep `frontend/src/api/client.ts` as composition boundary; if this repo's guardrail is enforced during implementation, put new Agent methods in `frontend/src/api/agentClient.ts` and only compose in `client.ts`.

## Current code evidence

Already present:
- `backend/app/api/routes/agent.py`: registered `POST /api/agent/query`; currently guarded by `settings.agent_enabled`.
- `backend/app/services/agent_service.py`: deterministic intent handlers already exist for portfolio, PnL, duration, credit, product PnL, bridge, risk tensor, market data, news.
- `backend/app/agent/schemas/agent_request.py`: `AgentQueryRequest` contains `question`, `basis`, `filters`, `position_scope`, `currency_basis`, `context`.
- `backend/app/agent/schemas/agent_response.py`: `AgentEnvelope`, `AgentEvidence`, `AgentResultMeta` already exist.
- `backend/app/agent/tools/analysis_view_tool.py`: intent router and envelope assembly already exist.
- `backend/app/agent/runtime/tool_registry.py`: registry currently wraps `AnalysisViewTool`.
- Tests already exist around agent intent routing and disabled endpoint behavior.

Important boundary note:
- `backend/app/AGENTS.md` and `tests/AGENTS.md` currently list real Agent enablement as excluded from the default repo-wide Phase 2 scope. Implementation should be treated as an explicit Agent lane, not as incidental formal-compute cleanup.

---

## MVP acceptance criteria

1. Backend disabled mode remains safe:
   - default `MOSS_AGENT_ENABLED=false` returns 503 disabled payload;
   - disabled requests are audited.

2. Backend enabled mode works for deterministic read-only intents:
   - portfolio overview;
   - PnL summary;
   - duration/DV01 risk;
   - risk tensor or PnL bridge if source data exists;
   - unknown question returns supported-query help, not an exception.

3. Agent request supports page context without breaking existing callers:
   - `context.page_id`;
   - `context.report_date` or `filters.report_date`;
   - `context.current_filters`;
   - optional explicit `context.intent` for page-driven routing.

4. Agent response is frontend-friendly:
   - answer string;
   - cards array;
   - evidence object;
   - result_meta object;
   - suggested next actions can be represented without executing them.

5. Frontend has an Agent client method and minimal UI panel:
   - sends current page context;
   - displays answer;
   - displays evidence/quality metadata compactly;
   - handles disabled 503 with a friendly message.

6. No new backend writes, no arbitrary SQL, no refresh execution.

---

## Task 1: Add explicit Agent contract tests for enabled read-only endpoint

**Objective:** Prove `/api/agent/query` can be enabled and still returns read-only evidence-bearing envelopes for deterministic intents.

**Files:**
- Modify/Test: `tests/test_agent_api_contract.py`
- Inspect: `backend/app/api/routes/agent.py`
- Inspect: `backend/app/services/agent_service.py`

**Step 1: Read existing tests**

Run:
```bash
python -m pytest tests/test_agent_api_contract.py -q
python -m pytest tests/test_agent_intent_routing.py -q
```

Expected:
- Existing tests pass or reveal current baseline issues unrelated to this task.

**Step 2: Add a failing enabled-mode test**

Add/extend a test that monkeypatches settings to `agent_enabled=True` and monkeypatches `execute_agent_query` or underlying repository handlers to return a stable `AgentEnvelope`.

Test assertions:
- HTTP status is 200.
- Response has `answer`.
- Response has `evidence.tables_used` list.
- Response has `result_meta.result_kind` starting with `agent.`.
- Response has `result_meta.formal_use_allowed` boolean.

**Step 3: Verify failure if current test scaffolding cannot enable route**

Run:
```bash
python -m pytest tests/test_agent_api_contract.py -q
```

Expected:
- New test fails only because enabled-mode route/test wiring is incomplete, not because of unrelated app startup.

**Step 4: Implement minimal route/test wiring only if needed**

If the route cannot be tested cleanly, adjust only the test setup or dependency monkeypatching. Do not change service semantics in this task unless the test exposes a real route bug.

**Step 5: Verify**

Run:
```bash
python -m pytest tests/test_agent_api_contract.py -q
python -m pytest tests/test_agent_intent_routing.py -q
```

Expected:
- Both pass.

---

## Task 2: Normalize page context fields in Agent request handling

**Objective:** Make page-driven calls reliable by standardizing `report_date`, `page_id`, and `current_filters` handling without changing existing request shape.

**Files:**
- Modify: `backend/app/services/agent_service.py`
- Modify/Test: `tests/test_agent_intent_routing.py`
- Optional: `backend/app/agent/schemas/agent_request.py` only if adding docstring/field description; avoid breaking schema.

**Step 1: Add failing tests for report_date resolution**

Add tests that construct `AgentQueryRequest` with:
```python
AgentQueryRequest(
    question="组合概览",
    context={"page_id": "balance-analysis", "report_date": "2026-03-31"},
)
```

Expected behavior:
- Handler receives/uses `2026-03-31` as explicit report date.
- `filters_applied` records `report_date_resolution="explicit"` or equivalent existing resolution field.

Also test fallback precedence:
1. `filters.report_date`
2. `context.report_date`
3. latest available date

**Step 2: Run failing test**

Run:
```bash
python -m pytest tests/test_agent_intent_routing.py -q
```

Expected:
- Fails if current `_requested_report_date` only checks one location.

**Step 3: Implement minimal helper update**

In `backend/app/services/agent_service.py`, update the existing report-date helper functions so they read:
- `request.filters.get("report_date")`
- then `request.context.get("report_date")`
- optionally `request.context.get("current_filters", {}).get("report_date")`

Do not alter each intent handler manually if a shared helper exists.

**Step 4: Verify**

Run:
```bash
python -m pytest tests/test_agent_intent_routing.py -q
```

Expected:
- Pass.

---

## Task 3: Add suggested actions to Agent response without executing them

**Objective:** Let the Agent recommend safe next steps such as “查看明细” or “建议刷新数据” without performing side effects.

**Files:**
- Modify: `backend/app/agent/schemas/agent_response.py`
- Modify: `backend/app/agent/tools/analysis_view_tool.py`
- Modify/Test: `tests/test_agent_intent_routing.py`

**Step 1: Add failing schema/envelope test**

Test that a payload containing:
```python
"suggested_actions": [
    {"type": "inspect_lineage", "label": "查看来源", "payload": {"metric_key": "total_pnl"}},
]
```

is returned in the final response as `suggested_actions`, and no action is executed.

**Step 2: Add minimal schema**

In `agent_response.py`, add:
```python
class AgentSuggestedAction(BaseModel):
    type: str
    label: str
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = True
```

Add to `AgentEnvelope`:
```python
suggested_actions: list[AgentSuggestedAction] = Field(default_factory=list)
```

**Step 3: Wire through envelope assembly**

In `analysis_view_tool.py`:
- normalize `payload.get("suggested_actions", [])`;
- include in `_finalize_envelope`;
- keep default empty list for existing callers.

**Step 4: Add one or two passive suggestions in handlers**

In `agent_service.py`, add simple suggested actions to major handlers, e.g.:
- portfolio overview: inspect detail by portfolio/cost center;
- PnL summary: inspect PnL bridge;
- stale/unknown/error: ask user to check available dates.

Do not trigger tasks.

**Step 5: Verify**

Run:
```bash
python -m pytest tests/test_agent_intent_routing.py -q
python -m pytest tests/test_agent_api_contract.py -q
```

Expected:
- Pass.

---

## Task 4: Add a frontend Agent API client module

**Objective:** Expose a typed frontend method for `/api/agent/query` while keeping the API client composition boundary clean.

**Files:**
- Create: `frontend/src/api/agentClient.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/contracts.ts` if shared types are preferred there
- Test: `frontend/src/test/ApiClient.test.ts` or create `frontend/src/test/AgentClient.test.ts`

**Step 1: Define frontend types**

In `frontend/src/api/agentClient.ts`, define minimal types mirroring backend response:
```ts
export type AgentQueryRequest = {
  question: string;
  basis?: "formal" | "scenario" | "analytical";
  filters?: Record<string, unknown>;
  position_scope?: string;
  currency_basis?: string;
  context?: Record<string, unknown>;
};

export type AgentQueryResponse = {
  answer: string;
  cards: Array<Record<string, unknown>>;
  evidence: Record<string, unknown>;
  result_meta: Record<string, unknown>;
  next_drill?: Array<Record<string, unknown>>;
  suggested_actions?: Array<Record<string, unknown>>;
};
```

**Step 2: Implement client factory**

Implement:
```ts
export type AgentClientMethods = {
  queryAgent: (request: AgentQueryRequest) => Promise<AgentQueryResponse>;
};

export function createAgentClientMethods(
  fetchImpl: typeof fetch,
  baseUrl: string,
): AgentClientMethods {
  return {
    async queryAgent(request) {
      const response = await fetchImpl(`${baseUrl}/api/agent/query`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        if (response.status === 503 && payload && typeof payload === "object") {
          throw new Error("Agent is disabled");
        }
        throw new Error(`Agent query failed (${response.status})`);
      }
      return (await response.json()) as AgentQueryResponse;
    },
  };
}
```

Exact implementation may use existing error style from `client.ts`; keep it minimal.

**Step 3: Compose into `ApiClient`**

In `client.ts`:
- import `AgentClientMethods` and `createAgentClientMethods`;
- extend `ApiClient` type with `AgentClientMethods`;
- in real client object, spread `...createAgentClientMethods(fetchImpl, baseUrl)`;
- in mock client, add a mock `queryAgent` returning a stable answer.

**Step 4: Add tests**

Test real mode:
- request goes to `/api/agent/query`;
- method is POST;
- body contains `question` and `context.page_id`.

Test disabled handling:
- mock fetch returns 503 disabled payload;
- method rejects with friendly error.

**Step 5: Verify**

Run:
```bash
cd frontend
npm test -- AgentClient
npm test -- ApiClient
npm run typecheck
```

If the test runner does not support the exact filter, use the existing repo convention for targeted Vitest tests.

---

## Task 5: Build a minimal reusable Agent panel component

**Objective:** Provide a small UI component that can be mounted on workbench pages without broad route refactor.

**Files:**
- Create: `frontend/src/features/agent/AgentPanel.tsx`
- Create: `frontend/src/features/agent/AgentPanel.styles.ts` if repeated styles are needed
- Test: `frontend/src/test/AgentPanel.test.tsx`

**Step 1: Component props**

Implement props:
```ts
export type AgentPanelProps = {
  pageId: string;
  reportDate?: string | null;
  currentFilters?: Record<string, unknown>;
  defaultQuestion?: string;
};
```

**Step 2: Component behavior**

UI requirements:
- textarea/input for question;
- submit button;
- loading state;
- answer area;
- compact evidence area showing at least quality flag and tables used;
- disabled/error state with friendly copy.

Call:
```ts
client.queryAgent({
  question,
  basis: "formal",
  filters: reportDate ? { report_date: reportDate } : {},
  context: { page_id: pageId, report_date: reportDate, current_filters: currentFilters },
})
```

**Step 3: Tests**

Test:
- renders default question;
- submits and displays answer;
- displays evidence quality flag;
- displays friendly disabled/error message.

**Step 4: Verify**

Run:
```bash
cd frontend
npm test -- AgentPanel
npm run typecheck
```

---

## Task 6: Mount Agent panel on one low-risk page first

**Objective:** Prove page-context Agent integration on a single page before broad rollout.

**Recommended page:** `frontend/src/features/workbench/pages/DashboardPage.tsx` or another stable page already using `useApiClient` and page-level data.

**Files:**
- Modify: one selected page only
- Test: corresponding page test only

**Step 1: Pick one page**

Use one page with stable tests. Do not mount globally in `WorkbenchShell` in v1 unless explicitly approved, because global mounting increases regression surface.

**Step 2: Add panel**

Render:
```tsx
<AgentPanel
  pageId="dashboard"
  reportDate={selectedReportDate ?? undefined}
  currentFilters={{ /* page filters only */ }}
  defaultQuestion="请解释当前页面最重要的经营结论"
/>
```

Keep layout simple and reuse existing page primitives/styles. Avoid repeated inline style blocks.

**Step 3: Page test**

Assert panel exists and passes expected context when submitting.

**Step 4: Verify**

Run:
```bash
cd frontend
npm test -- DashboardPage
npm run typecheck
npm run debt:audit
```

Expected:
- No debt baseline growth unless explicitly justified.

---

## Task 7: Add docs/runbook for operating the Agent

**Objective:** Make enablement and boundaries explicit so future users do not assume the Agent is a dangerous autonomous executor.

**Files:**
- Create: `docs/AGENT_MVP_RUNBOOK.md`
- Modify: `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md` only if you want to add a link; do not change authority semantics casually.

**Content required:**
- How to enable locally: `MOSS_AGENT_ENABLED=true`.
- Endpoint: `POST /api/agent/query`.
- Supported intents.
- Request/response examples.
- Safety boundaries.
- What disabled mode means.
- Troubleshooting:
  - 503 disabled;
  - no report dates;
  - unknown intent;
  - stale/fallback quality flag.

**Verify:**
```bash
python -m pytest tests/test_agent_api_contract.py -q
cd frontend && npm run typecheck
```

---

## Task 8: Final integration verification

**Objective:** Confirm backend, frontend, and documentation work together.

**Commands:**

Backend targeted:
```bash
python -m pytest tests/test_agent_api_contract.py -q
python -m pytest tests/test_agent_intent_routing.py -q
python -m pytest tests/test_agent_audit_log_contract.py -q
```

Frontend targeted:
```bash
cd frontend
npm test -- AgentClient
npm test -- AgentPanel
npm run typecheck
npm run debt:audit
```

Manual smoke, if local API is running:
```bash
curl -s -X POST http://127.0.0.1:7888/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"question":"组合概览","basis":"formal","context":{"page_id":"dashboard"}}'
```

Expected:
- If `MOSS_AGENT_ENABLED=false`, returns 503 disabled payload.
- If `MOSS_AGENT_ENABLED=true` and data exists, returns `AgentEnvelope`.
- If data missing, returns controlled error/envelope, not server crash.

---

## Implementation notes

- This MVP does not require adding an LLM provider. It is a deterministic, evidence-first system Agent.
- A future LLM layer can be added after tool contracts are stable; the LLM should choose among whitelisted tools and synthesize answers from tool outputs only.
- If later adding a true LLM, persist prompts/tool policies in docs and tests; never allow model-generated SQL against production tables.
- Consider adding `context.intent` from frontend page buttons for deterministic behavior. Free-text intent routing is acceptable as fallback, not as the only route for critical pages.

## Suggested future v2

- Add `read_metric_definition` tool from `docs/page_contracts.md` and `docs/calc_rules.md`.
- Add `read_lineage` tool for source_version/cache_version drilldown.
- Add `available_dates` tool per page/domain.
- Add report-draft generation for monthly operating analysis.
- Add confirmation-gated task suggestions, still executed only through existing task APIs.
