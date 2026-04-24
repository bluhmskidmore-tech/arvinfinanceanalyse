# Cross Asset Investment Research Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the cross-asset module into a governed analytical investment-research surface that outputs duration, curve, credit, and instrument views for rates, NCD, and high-grade credit, while surfacing unsupported axes as explicit pending signals instead of fabricating data.

**Architecture:** Extend the existing `macro_bond_linkage.analysis` contract additively so backend owns investment-research view derivation and transmission-axis summaries. Keep `choice_macro_latest` and `choice_news_events` as input surfaces; keep frontend responsible for presentation, provenance, and pending-state rendering only. Do not introduce a parallel endpoint unless the existing additive contract proves insufficient.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, DuckDB, pytest, React, TypeScript, Vitest, React Query.

---

## Scope Split

### Tranche A: Executable Now

Build the first investment-research version using signals already present or already supported by current analytical chains:

- global rates / overseas constraint
- liquidity / short-end funding
- commodity-inflation linkage
- duration / curve / credit / instrument conclusions for:
  - rates
  - NCD
  - high-grade credit

Axes that are not yet backed by governed signals must still appear, but with `status=pending_signal`:

- equity-bond spread
- mega-cap equity weight / leadership

### Tranche B: Signal Completion

Only after the source inventory is explicitly confirmed:

- add a governed equity proxy for CSI 300 or equivalent
- add a governed large-cap / financial leadership proxy
- switch the `pending_signal` axes above to live calculations

Do not fake Tranche B inside Tranche A.

## Contract Targets

The additive backend payload should converge on the following shape:

```python
{
  "research_views": [
    {
      "key": "duration",
      "stance": "bullish|neutral|bearish|conflicted",
      "confidence": "high|medium|low",
      "summary": "...",
      "affected_targets": ["rates", "ncd", "high_grade_credit"],
      "evidence": ["..."],
      "status": "ready|pending_signal"
    }
  ],
  "transmission_axes": [
    {
      "axis_key": "global_rates|liquidity|equity_bond_spread|commodities_inflation|mega_cap_equities",
      "status": "ready|pending_signal",
      "stance": "supportive|neutral|restrictive|conflicted",
      "summary": "...",
      "impacted_views": ["duration", "curve"],
      "required_series_ids": ["..."],
      "warnings": []
    }
  ]
}
```

Frontend should consume those fields directly and stop owning long-lived research heuristics.

## Backend / Frontend Boundary

### Backend owns

- Research view derivation
- Transmission-axis derivation
- Pending-signal detection for unsupported axes
- Mapping from analytical inputs to governed investment-research outputs

### Frontend owns

- Rendering research view cards
- Rendering transmission-axis blocks
- Rendering provenance badges
- Rendering pending/no-data/fallback/stale states
- Event stream formatting from `choice_news_events`

### Frontend does not own long-term

- Core investment-research stance heuristics
- Signal-to-view mapping rules
- Asset recommendation scoring

---

### Task 1: Add additive research-view and transmission-axis schema

**Files:**
- Modify: `backend/app/schemas/macro_bond_linkage.py`
- Modify: `backend/app/services/macro_bond_linkage_service.py`
- Test: `tests/test_macro_bond_linkage.py`

**Step 1: Write the failing test**

Add a schema/API contract test that requires additive `research_views` and `transmission_axes` fields.

```python
def test_api_exposes_investment_research_additive_fields(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "macro-bond-research.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=True)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    client = _route_client()
    response = client.get("/api/macro-bond-linkage/analysis", params={"report_date": REPORT_DATE.isoformat()})
    payload = response.json()

    assert "research_views" in payload["result"]
    assert "transmission_axes" in payload["result"]
    assert {"duration", "curve", "credit", "instrument"} <= {row["key"] for row in payload["result"]["research_views"]}
```

**Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_macro_bond_linkage.py::test_api_exposes_investment_research_additive_fields -q
```

Expected: FAIL because the response currently has no additive research-view fields.

**Step 3: Write minimal implementation**

Add Pydantic models:

- `MacroBondResearchView`
- `MacroBondTransmissionAxis`

Add them as additive fields on `MacroBondLinkageResponse` with empty-list defaults.

**Step 4: Run test to verify it passes**

Run the same targeted test.

Expected: PASS with empty-but-shaped additive fields.

**Step 5: Commit**

```bash
git add backend/app/schemas/macro_bond_linkage.py backend/app/services/macro_bond_linkage_service.py tests/test_macro_bond_linkage.py
git commit -m "feat: add additive research-view schema to macro bond linkage"
```

---

### Task 2: Encode pending-signal axes instead of hiding unsupported research dimensions

**Files:**
- Modify: `backend/app/core_finance/macro_bond_linkage.py`
- Modify: `backend/app/services/macro_bond_linkage_service.py`
- Test: `tests/test_macro_bond_linkage.py`

**Step 1: Write the failing test**

Require unsupported axes to appear as explicit pending signals.

```python
def test_macro_bond_linkage_marks_missing_equity_axes_as_pending_signal(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "macro-bond-pending-signal.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=True)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    payload = _route_client().get(
        "/api/macro-bond-linkage/analysis",
        params={"report_date": REPORT_DATE.isoformat()},
    ).json()["result"]

    axes = {row["axis_key"]: row for row in payload["transmission_axes"]}
    assert axes["equity_bond_spread"]["status"] == "pending_signal"
    assert axes["mega_cap_equities"]["status"] == "pending_signal"
```

**Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_macro_bond_linkage.py::test_macro_bond_linkage_marks_missing_equity_axes_as_pending_signal -q
```

Expected: FAIL because those axes are not emitted yet.

**Step 3: Write minimal implementation**

Add backend helper logic that always emits the five target axes:

- `global_rates`
- `liquidity`
- `equity_bond_spread`
- `commodities_inflation`
- `mega_cap_equities`

If required signals are missing, emit:

```python
{
    "axis_key": "equity_bond_spread",
    "status": "pending_signal",
    "stance": "neutral",
    "summary": "Pending governed equity spread proxy; do not infer from unrelated signals.",
    "impacted_views": ["duration", "credit"],
    "required_series_ids": ["CA.CSI300"],
    "warnings": ["missing governed proxy series"]
}
```

Representative implementation location:

- add helper dataclass / dict builder inside `backend/app/core_finance/macro_bond_linkage.py`
- serialize through `backend/app/services/macro_bond_linkage_service.py`

**Step 4: Run test to verify it passes**

Run the targeted test again.

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/core_finance/macro_bond_linkage.py backend/app/services/macro_bond_linkage_service.py tests/test_macro_bond_linkage.py
git commit -m "feat: emit pending-signal transmission axes for unsupported equity research inputs"
```

---

### Task 3: Compute duration / curve / credit / instrument research views on the backend

**Files:**
- Modify: `backend/app/core_finance/macro_bond_linkage.py`
- Modify: `backend/app/services/macro_bond_linkage_service.py`
- Test: `tests/test_macro_bond_linkage.py`

**Step 1: Write the failing test**

Add a service/API test that checks real research view output for supported axes.

```python
def test_macro_bond_linkage_emits_supported_research_views(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "macro-bond-research-views.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=False)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    payload = _route_client().get(
        "/api/macro-bond-linkage/analysis",
        params={"report_date": REPORT_DATE.isoformat()},
    ).json()["result"]

    views = {row["key"]: row for row in payload["research_views"]}
    assert views["duration"]["status"] == "ready"
    assert views["curve"]["status"] == "ready"
    assert views["credit"]["status"] == "ready"
    assert views["instrument"]["status"] == "ready"
    assert views["instrument"]["affected_targets"] == ["rates", "ncd", "high_grade_credit"]
```

**Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_macro_bond_linkage.py::test_macro_bond_linkage_emits_supported_research_views -q
```

Expected: FAIL because backend does not derive those views yet.

**Step 3: Write minimal implementation**

Add additive research-view heuristics in `backend/app/core_finance/macro_bond_linkage.py` using:

- `rate_direction_score`
- `liquidity_score`
- `growth_score`
- `inflation_score`
- top correlation families / tenors

Representative rules:

```python
if rate_direction_score < -0.25 and liquidity_score > 0.10:
    duration_stance = "bullish"
elif rate_direction_score > 0.25:
    duration_stance = "bearish"
else:
    duration_stance = "neutral"

if liquidity_score > 0.10 and rate_direction_score >= 0:
    curve_stance = "front_end_preferred"
else:
    curve_stance = "neutral"
```

`credit` should only target high-grade credit in this tranche. If the top supported correlation is `credit_spread`, the summary may mention spread sensitivity, but must not expand into full credit-universe guidance.

`instrument` must map only to:

- `rates`
- `ncd`
- `high_grade_credit`

**Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests/test_macro_bond_linkage.py::test_macro_bond_linkage_emits_supported_research_views -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/core_finance/macro_bond_linkage.py backend/app/services/macro_bond_linkage_service.py tests/test_macro_bond_linkage.py
git commit -m "feat: derive backend investment research views from macro bond linkage inputs"
```

---

### Task 4: Extend frontend API contracts and adapter to consume backend-owned research views

**Files:**
- Modify: `frontend/src/api/contracts.ts`
- Modify: `frontend/src/test/ApiClient.test.ts`
- Modify: `frontend/src/features/cross-asset/lib/crossAssetDriversPageModel.ts`
- Test: `frontend/src/test/crossAssetDriversPageModel.test.ts`

**Step 1: Write the failing test**

Add a frontend model test that expects server-owned research views to be consumed directly.

```typescript
it("prefers backend research views over local heuristic fallback", () => {
  const rows = buildResearchSummaryCards({
    researchViews: [
      { key: "duration", status: "ready", stance: "bullish", confidence: "high", summary: "..." },
    ],
  });

  expect(rows[0].label).toBe("久期");
  expect(rows[0].summary).toContain("...");
});
```

**Step 2: Run test to verify it fails**

Run:

```powershell
npm run test -- crossAssetDriversPageModel.test.ts
```

Expected: FAIL because frontend contracts/model do not know about `research_views`.

**Step 3: Write minimal implementation**

- Extend `MacroBondLinkagePayload` in `frontend/src/api/contracts.ts`
- Update mock contract shape in `frontend/src/test/ApiClient.test.ts`
- Add adapter/model helpers in `crossAssetDriversPageModel.ts` for:
  - research summary cards
  - transmission-axis cards
  - pending-signal display

**Step 4: Run test to verify it passes**

Run the targeted Vitest file again.

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/api/contracts.ts frontend/src/test/ApiClient.test.ts frontend/src/features/cross-asset/lib/crossAssetDriversPageModel.ts frontend/src/test/crossAssetDriversPageModel.test.ts
git commit -m "feat: wire frontend contracts and adapters for backend research views"
```

---

### Task 5: Add first-screen research judgment sections to the page

**Files:**
- Create: `frontend/src/features/cross-asset/components/ResearchViewsPanel.tsx`
- Create: `frontend/src/features/cross-asset/components/TransmissionAxesPanel.tsx`
- Modify: `frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx`
- Modify: `frontend/src/test/CrossAssetPage.test.tsx`

**Step 1: Write the failing test**

Add a page test that requires first-screen investment-research output.

```typescript
it("renders first-screen duration curve credit and instrument views", async () => {
  renderPage();

  expect(await screen.findByText("久期判断")).toBeInTheDocument();
  expect(screen.getByText("曲线判断")).toBeInTheDocument();
  expect(screen.getByText("信用判断")).toBeInTheDocument();
  expect(screen.getByText("品种判断")).toBeInTheDocument();
  expect(screen.getByText("传导主线")).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run:

```powershell
npm run test -- CrossAssetPage.test.tsx
```

Expected: FAIL because the page currently has judgment copy, but not explicit first-screen research-view sections.

**Step 3: Write minimal implementation**

Add two presentational components:

- `ResearchViewsPanel.tsx`
  - four cards: 久期 / 曲线 / 信用 / 品种
  - display `stance`, `confidence`, `summary`, `status`
- `TransmissionAxesPanel.tsx`
  - one block per axis
  - supported axes show stance and summary
  - unsupported axes show `pending_signal`

Place them above the current KPI/driver body so the page starts with investment-research conclusions rather than raw evidence.

**Step 4: Run test to verify it passes**

Run:

```powershell
npm run test -- CrossAssetPage.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/features/cross-asset/components/ResearchViewsPanel.tsx frontend/src/features/cross-asset/components/TransmissionAxesPanel.tsx frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx frontend/src/test/CrossAssetPage.test.tsx
git commit -m "feat: surface first-screen investment research views on cross asset page"
```

---

### Task 6: Keep events, watch list, and candidate actions aligned with research views

**Files:**
- Modify: `frontend/src/features/cross-asset/components/MarketCandidateActions.tsx`
- Modify: `frontend/src/features/cross-asset/components/CrossAssetEventCalendar.tsx`
- Modify: `frontend/src/features/cross-asset/components/WatchList.tsx`
- Modify: `frontend/src/features/cross-asset/lib/crossAssetDriversPageModel.ts`
- Test: `frontend/src/test/crossAssetDriversPageModel.test.ts`

**Step 1: Write the failing test**

Require the lower sections to reference research-view outputs instead of free-floating frontend heuristics.

```typescript
it("derives candidate actions and watch items from research views plus provenance", () => {
  const actions = buildCrossAssetCandidateActions({
    researchViews: [
      { key: "duration", stance: "bullish", status: "ready", summary: "..." },
    ],
    transmissionAxes: [
      { axis_key: "global_rates", status: "ready", stance: "restrictive", summary: "..." },
    ],
  });

  expect(actions[0].reason).toContain("duration");
});
```

**Step 2: Run test to verify it fails**

Run:

```powershell
npm run test -- crossAssetDriversPageModel.test.ts
```

Expected: FAIL because current candidate/watch logic is still primarily frontend heuristic.

**Step 3: Write minimal implementation**

Refactor the model so that:

- candidate actions reference research views first
- watch list references research views plus live KPI values
- event calendar continues to merge `choice_news_events` and warnings
- fallback/stale/analytical provenance still surfaces independently

**Step 4: Run test to verify it passes**

Run the targeted test again.

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/features/cross-asset/components/MarketCandidateActions.tsx frontend/src/features/cross-asset/components/CrossAssetEventCalendar.tsx frontend/src/features/cross-asset/components/WatchList.tsx frontend/src/features/cross-asset/lib/crossAssetDriversPageModel.ts frontend/src/test/crossAssetDriversPageModel.test.ts
git commit -m "feat: align lower cross asset sections with backend research views"
```

---

### Task 7: Verify the full Tranche A lane end to end

**Files:**
- Modify if needed: `frontend/src/test/CrossAssetDriversRoute.test.tsx`
- Modify if needed: `frontend/src/test/RouteRegistry.test.tsx`
- Modify if needed: `frontend/src/test/navigation.test.ts`
- Modify if needed: `tests/test_macro_bond_linkage.py`

**Step 1: Run the narrow backend suite**

```powershell
pytest tests/test_macro_bond_linkage.py -q
```

Expected: PASS.

**Step 2: Run the narrow frontend suite**

```powershell
npm run test -- crossAssetDriversPageModel.test.ts CrossAssetDriversRoute.test.tsx CrossAssetPage.test.tsx RouteRegistry.test.tsx navigation.test.ts
```

Expected: PASS.

**Step 3: Run typecheck**

```powershell
npm run typecheck
```

Expected: PASS.

**Step 4: Run build**

```powershell
npm run build
```

Expected: PASS.

**Step 5: Run lint and record unrelated blockers honestly**

```powershell
npm run lint
```

Expected: PASS for touched files. If the repo still has unrelated lint blockers, record them without folding them into this module's scope.

**Step 6: Commit verification/docs cleanup**

```bash
git add frontend/src/test/CrossAssetDriversRoute.test.tsx frontend/src/test/RouteRegistry.test.tsx frontend/src/test/navigation.test.ts tests/test_macro_bond_linkage.py
git commit -m "test: lock cross asset investment research lane verification"
```

---

## Tranche B: Signal Completion Plan

Only start this after the source owner explicitly confirms governed proxy availability.

### Task 8: Add governed equity spread proxy

**Files:**
- Modify: `config/choice_macro_catalog.json`
- Modify: `backend/app/tasks/choice_macro.py`
- Modify: `frontend/src/features/cross-asset/lib/crossAssetKpiModel.ts`
- Test: `tests/test_choice_macro_delivery.py`

Implement a governed proxy for `CA.CSI300` or equivalent, then switch `equity_bond_spread` from `pending_signal` to live.

### Task 9: Add governed mega-cap equity leadership proxy

**Files:**
- Modify: `config/choice_macro_catalog.json`
- Modify: `backend/app/tasks/choice_macro.py`
- Modify: `tests/test_choice_macro_delivery.py`

Implement a governed large-cap / financial leadership proxy, then switch `mega_cap_equities` from `pending_signal` to live.

Do not start Task 9 until the exact source series and policy note are confirmed.

---

## Verification Summary

The implementation is only complete when all of the following are true:

- Backend returns additive `research_views`
- Backend returns additive `transmission_axes`
- Unsupported equity axes surface as `pending_signal`, not as invented values
- Frontend first screen starts with research conclusions, not charts
- Candidate actions / watch list are aligned to research views
- Provenance badges still expose `analytical only / fallback / stale / no data`
- Backend targeted tests pass
- Frontend targeted tests pass
- Typecheck passes
- Build passes
- Lint is either green or blocked only by unrelated pre-existing repo issues

## Risks / Assumptions

- `equity_bond_spread` and `mega_cap_equities` are not currently backed by confirmed governed series in the local catalog; Tranche A must not fake them.
- The existing `macro_bond_linkage.analysis` contract is assumed to be the correct additive surface. If product later demands a separate governed research family, that should be a separate design decision.
- First tranche conclusions must remain scoped to `rates / ncd / high_grade_credit`. Do not let implementation drift into full credit-universe guidance.

