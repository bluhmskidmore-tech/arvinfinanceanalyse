# Balance Movement Analysis Diagnostics MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the next analysis layer for the balance movement page so users can judge explanation closure, diagnostic status, and evidence lineage without inventing unsupported accounting attribution in the frontend.

**Architecture:** Keep the change page-local and evidence-driven. Reuse the existing `/ui/balance-movement-analysis` payload, derive only display diagnostics from returned fields, and keep unsupported valuation and FX translation items explicitly marked as not supported. Add pure helper functions in the page, small presentational components, CSS in the page stylesheet, and focused Vitest coverage.

**Tech Stack:** React + TypeScript, existing API contracts from `frontend/src/api/contracts.ts`, page-local CSS, Vitest + React Testing Library, Playwright browser verification.

---

## Scope

Implement these three analysis improvements:

1. Explanation closure panel: classify waterfall components into supported, unsupported, and residual buckets, then show a page-level "can we explain this movement?" judgment.
2. Diagnostic rules on the four dimension cards: add compact tags such as `主导变动`, `结构迁移`, `口径待补`, `覆盖不足`, and `残差关注`.
3. Evidence drawer: let each dimension card expose the fields, source notes, governance metadata, and limitations behind its conclusion.

Do not implement:

- Backend calculation changes.
- Database schema changes.
- New API endpoints.
- Changes to `frontend/src/api/client.ts`.
- New mock payload blocks.
- Frontend calculation of buy/sell/maturity/valuation/FX attribution.
- Any formal definition that requires `moss-metric-contracts` but is not available.

## Current Anchors

Existing implementation to build on:

- `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx`
  - `EvidenceStrip`
  - `AnalysisDimensionOverview`
  - `ResidualUnsupportedPanel`
  - `DifferenceAttributionWaterfallPanel`
  - `BasisMovementDecompositionPanel`
  - `buildBalanceMovementCsv`
  - `analysisDimensionCards`
- `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.css`
  - `.balance-movement-evidence-strip`
  - `.balance-movement-dimension-overview`
  - `.balance-movement-dimension-card`
  - `.balance-movement-residual-grid`
- `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`
  - dimension overview assertions
  - evidence strip assertions
  - residual unsupported assertions
  - CSV export assertions

## Evidence Gate Before Editing

Before implementation, try to inspect project evidence tools:

```bash
# In Codex, search for project MCP tools first.
# If unavailable, record the unavailable tools in the final report.
moss-metric-contracts
moss-lineage-evidence
moss-data-catalog
gitnexus
```

Expected for this Codex surface may be unavailable. If unavailable, continue only because this plan does not define new business metrics; it adds display diagnostics over existing returned payload fields.

---

## Task 1: Add Pure Diagnostic Model Helpers

**Files:**

- Modify: `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx`
- Test: `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`

**Step 1: Write failing tests for diagnostic derivation**

Add a test that renders the existing mock page and expects an explanation closure panel to show:

```tsx
const closure = await screen.findByTestId("balance-movement-analysis-explanation-closure");
expect(closure).toHaveTextContent("解释闭合度");
expect(closure).toHaveTextContent("已支持解释项");
expect(closure).toHaveTextContent("未支持项");
expect(closure).toHaveTextContent("未分类 / 残差");
expect(closure).toHaveTextContent("估值差");
expect(closure).toHaveTextContent("外币折算差");
expect(closure).toHaveTextContent("未支持，不反推");
```

Also assert that unsupported components are not displayed as zero-explained:

```tsx
expect(closure).not.toHaveTextContent("估值差 +0.00 亿");
expect(closure).not.toHaveTextContent("外币折算差 +0.00 亿");
```

**Step 2: Run the failing test**

Run:

```bash
cd frontend
npm run test -- BalanceMovementAnalysisPage
```

Expected: FAIL because `balance-movement-analysis-explanation-closure` does not exist.

**Step 3: Add page-local helper types**

Near the existing `AnalysisDimensionCard` type, add:

```ts
type BalanceDiagnosticTone = "ok" | "info" | "warn" | "critical" | "unknown";

type BalanceDiagnosticTag = {
  label: string;
  tone: BalanceDiagnosticTone;
};

type BalanceEvidenceItem = {
  label: string;
  value: string;
  note?: string;
};

type BalanceExplanationClosure = {
  tone: BalanceDiagnosticTone;
  headline: string;
  supportedComponents: BalanceDifferenceAttributionWaterfall["components"];
  unsupportedComponents: BalanceDifferenceAttributionWaterfall["components"];
  residualComponent?: BalanceDifferenceAttributionWaterfall["components"][number];
  residualRatioPct: number | null;
  note: string;
};
```

**Step 4: Add helper functions**

Keep them pure and page-local:

```ts
function amountToNumber(value: string | number | null | undefined) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function buildExplanationClosure(options: {
  waterfall: BalanceDifferenceAttributionWaterfall | null;
  summary: BalanceMovementPayload["summary"] | null;
}): BalanceExplanationClosure | null {
  const { waterfall, summary } = options;
  if (!waterfall) return null;

  const supportedComponents = waterfall.components.filter(
    (component) => component.is_supported !== false && !component.is_residual,
  );
  const unsupportedComponents = waterfall.components.filter(
    (component) => component.is_supported === false,
  );
  const residualComponent = waterfall.components.find((component) => component.is_residual);
  const residualAmount = amountToNumber(residualComponent?.amount);
  const totalChange = amountToNumber(summary?.balance_change_total);
  const residualRatioPct =
    residualAmount !== null && totalChange !== null && Math.abs(totalChange) > 0
      ? (Math.abs(residualAmount) / Math.abs(totalChange)) * 100
      : null;

  if (unsupportedComponents.length > 0) {
    return {
      tone: residualRatioPct !== null && residualRatioPct > 2 ? "critical" : "warn",
      headline: "存在待补口径，不能反推为已解释",
      supportedComponents,
      unsupportedComponents,
      residualComponent,
      residualRatioPct,
      note: "估值差和外币折算差缺少可闭合字段；页面只展示后端已返回的证据项。",
    };
  }

  return {
    tone: residualRatioPct !== null && residualRatioPct > 2 ? "warn" : "ok",
    headline: "现有瀑布项可用于本页解释闭合",
    supportedComponents,
    unsupportedComponents,
    residualComponent,
    residualRatioPct,
    note: "该判断是页面诊断提示，不替代正式审计归因。",
  };
}
```

Threshold note: `2%` is only a UI attention threshold for residual-to-change ratio. It must be labelled as a page diagnostic hint, not a metric definition.

**Step 5: Wire the helper in the page**

Inside `BalanceMovementAnalysisPage`, add:

```ts
const explanationClosure = useMemo(
  () => buildExplanationClosure({
    waterfall: differenceAttributionWaterfall,
    summary: detailQuery.data?.result.summary ?? null,
  }),
  [differenceAttributionWaterfall, detailQuery.data?.result.summary],
);
```

**Step 6: Run the test**

Run:

```bash
cd frontend
npm run test -- BalanceMovementAnalysisPage
```

Expected: still FAIL until the panel component is added.

---

## Task 2: Add Explanation Closure Panel

**Files:**

- Modify: `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx`
- Modify: `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.css`
- Test: `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`

**Step 1: Add component**

Place after `ResidualUnsupportedPanel` or before it if the page should read closure first:

```tsx
function ExplanationClosurePanel({ closure }: { closure: BalanceExplanationClosure }) {
  return (
    <section
      className={`balance-movement-closure balance-movement-closure--${closure.tone}`}
      data-testid="balance-movement-analysis-explanation-closure"
    >
      <div className="balance-movement-derived-panel__header">
        <div>
          <span>解释闭合度</span>
          <h2>{closure.headline}</h2>
        </div>
        <strong>{closure.unsupportedComponents.length > 0 ? "口径待补" : "可解释"}</strong>
      </div>
      <p className="balance-movement-derived-panel__summary">{closure.note}</p>
      <div className="balance-movement-closure-grid">
        <div>
          <span>已支持解释项</span>
          <strong>{closure.supportedComponents.length} 项</strong>
        </div>
        <div>
          <span>未支持项</span>
          <strong>
            {closure.unsupportedComponents.map((component) => component.component_label).join("、") || "无"}
          </strong>
        </div>
        <div>
          <span>未分类 / 残差</span>
          <strong>
            {closure.residualComponent
              ? `${formatSignedYiCell(closure.residualComponent.amount)} 亿`
              : "—"}
          </strong>
        </div>
        <div>
          <span>残差占本期变动</span>
          <strong>{closure.residualRatioPct === null ? "—" : formatPct(closure.residualRatioPct)}</strong>
        </div>
      </div>
      {closure.unsupportedComponents.length > 0 ? (
        <ul className="balance-movement-closure-list">
          {closure.unsupportedComponents.map((component) => (
            <li key={component.component_key}>
              <strong>{component.component_label}</strong>
              <span>未支持，不反推。{component.evidence_note}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
```

**Step 2: Render component**

Place it after `DifferenceAttributionWaterfallPanel` and before `ResidualUnsupportedPanel`:

```tsx
{explanationClosure ? <ExplanationClosurePanel closure={explanationClosure} /> : null}
```

**Step 3: Add CSS**

In `BalanceMovementAnalysisPage.css`, add:

```css
.balance-movement-closure {
  display: grid;
  gap: 12px;
  margin-bottom: 18px;
  padding: 16px;
  border: 1px solid #d7dfea;
  border-radius: 8px;
  background: #ffffff;
}

.balance-movement-closure--warn {
  border-color: #f3c96b;
  background: #fffaf0;
}

.balance-movement-closure--critical {
  border-color: #f3a6a6;
  background: #fff7f7;
}

.balance-movement-closure-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.balance-movement-closure-grid > div {
  min-width: 0;
  padding: 12px;
  border: 1px solid #edf1f6;
  border-radius: 8px;
  background: #fbfcfe;
}

.balance-movement-closure-grid span,
.balance-movement-closure-list span {
  color: #64748b;
  font-size: 12px;
}

.balance-movement-closure-grid strong {
  display: block;
  margin-top: 6px;
  color: #10284a;
  font-size: 15px;
}

.balance-movement-closure-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 10px 0 0;
  border-top: 1px solid #edf1f6;
  list-style: none;
}
```

Add mobile collapse inside the existing media query:

```css
.balance-movement-closure-grid {
  grid-template-columns: 1fr;
}
```

**Step 4: Run tests**

Run:

```bash
cd frontend
npm run test -- BalanceMovementAnalysisPage
```

Expected: PASS for closure tests.

**Step 5: Commit checkpoint**

Only if asked to commit:

```bash
git add frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx \
  frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.css \
  frontend/src/test/BalanceMovementAnalysisPage.test.tsx
git commit -m "Add balance movement explanation closure diagnostics"
```

---

## Task 3: Add Diagnostic Tags to Dimension Cards

**Files:**

- Modify: `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx`
- Modify: `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.css`
- Test: `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`

**Step 1: Write failing tests**

Extend the first page render test:

```tsx
expect(screen.getByTestId("balance-movement-analysis-dimension-card-business")).toHaveTextContent("主导变动");
expect(screen.getByTestId("balance-movement-analysis-dimension-card-basis")).toHaveTextContent("主导分桶");
expect(screen.getByTestId("balance-movement-analysis-dimension-card-residual")).toHaveTextContent("口径待补");
expect(screen.getByTestId("balance-movement-analysis-dimension-card-coverage")).toHaveTextContent("覆盖");
```

**Step 2: Extend card type**

```ts
type AnalysisDimensionCard = {
  key: string;
  title: string;
  metric: string;
  detail: string;
  href: string;
  tags: BalanceDiagnosticTag[];
  evidence: BalanceEvidenceItem[];
};
```

**Step 3: Add tag helpers**

```ts
function coverageTone(value: string | number | null | undefined): BalanceDiagnosticTone {
  const coverage = amountToNumber(value);
  if (coverage === null) return "unknown";
  if (coverage < 80) return "critical";
  if (coverage < 95) return "warn";
  return "ok";
}

function residualTone(ratioPct: number | null, unsupportedCount: number): BalanceDiagnosticTone {
  if (unsupportedCount > 0) return "warn";
  if (ratioPct !== null && ratioPct > 2) return "warn";
  return "ok";
}
```

**Step 4: Populate card tags**

In `analysisDimensionCards`, add:

```ts
tags: businessTopMove ? [{ label: "主导变动", tone: "info" }] : [{ label: "样本不足", tone: "unknown" }],
```

For basis:

```ts
tags: [
  { label: "主导分桶", tone: "info" },
  ...(trendMoMDriverBucket && structureShareDriverBucket && trendMoMDriverBucket !== structureShareDriverBucket
    ? [{ label: "结构迁移", tone: "warn" as const }]
    : []),
],
```

For residual:

```ts
tags: [
  {
    label: unsupportedLabels.length > 0 ? "口径待补" : "残差闭合",
    tone: residualTone(explanationClosure?.residualRatioPct ?? null, unsupportedLabels.length),
  },
],
```

For coverage:

```ts
tags: [
  { label: `期限${drilldownStatusLabel(zqtzMaturityStructure?.meta.status)}`, tone: coverageTone(zqtzMaturityStructure?.meta.coverage_pct) },
  { label: `集中度${drilldownStatusLabel(zqtzConcentrationAnalysis?.meta.status)}`, tone: coverageTone(zqtzConcentrationAnalysis?.meta.coverage_pct) },
],
```

**Step 5: Render tags**

Inside `AnalysisDimensionOverview` card:

```tsx
<div className="balance-movement-dimension-tags">
  {card.tags.map((tag) => (
    <span
      key={`${card.key}-${tag.label}`}
      className={`balance-movement-dimension-tag balance-movement-dimension-tag--${tag.tone}`}
    >
      {tag.label}
    </span>
  ))}
</div>
```

**Step 6: Add CSS**

```css
.balance-movement-dimension-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.balance-movement-dimension-tag {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  max-width: 100%;
  padding: 2px 7px;
  border-radius: 999px;
  background: #eef2f7;
  color: #475569;
  font-size: 11px;
  font-weight: 800;
  line-height: 1.5;
}

.balance-movement-dimension-tag--ok {
  background: #e8f7ef;
  color: #166534;
}

.balance-movement-dimension-tag--warn {
  background: #fff3d8;
  color: #92400e;
}

.balance-movement-dimension-tag--critical {
  background: #ffe4e6;
  color: #9f1239;
}

.balance-movement-dimension-tag--info,
.balance-movement-dimension-tag--unknown {
  background: #eef2f7;
  color: #475569;
}
```

**Step 7: Run tests**

Run:

```bash
cd frontend
npm run test -- BalanceMovementAnalysisPage
```

Expected: PASS.

---

## Task 4: Add Evidence Drawer

**Files:**

- Modify: `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx`
- Modify: `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.css`
- Test: `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`

**Step 1: Write failing tests**

Add a test:

```tsx
it("opens dimension evidence without inventing unsupported attribution", async () => {
  const user = userEvent.setup();
  renderWorkbenchApp(["/balance-movement-analysis"], {
    client: createApiClient({ mode: "mock" }),
  });

  await screen.findByTestId("balance-movement-analysis-dimension-overview");
  await user.click(screen.getByTestId("balance-movement-analysis-dimension-evidence-residual"));

  const drawer = await screen.findByRole("dialog", { name: "分析维度证据" });
  expect(drawer).toHaveTextContent("对账残差");
  expect(drawer).toHaveTextContent("估值差");
  expect(drawer).toHaveTextContent("外币折算差");
  expect(drawer).toHaveTextContent("未支持，不反推");
  expect(drawer).toHaveTextContent("trace_id");

  await user.click(screen.getByRole("button", { name: "关闭证据" }));
  expect(screen.queryByRole("dialog", { name: "分析维度证据" })).not.toBeInTheDocument();
});
```

**Step 2: Add drawer state**

Inside `BalanceMovementAnalysisPage`:

```ts
const [selectedEvidenceKey, setSelectedEvidenceKey] = useState<string | null>(null);
const selectedEvidenceCard = analysisDimensionCards.find((card) => card.key === selectedEvidenceKey) ?? null;
```

**Step 3: Add evidence items while building cards**

Business evidence:

```ts
evidence: [
  { label: "维度字段", value: "business_trend_months / product category derived rows" },
  { label: "Top 变动", value: businessTopMove ? `${businessTopMove.label} ${formatSignedYiCell(businessTopMove.deltaYuan)} 亿` : "—" },
  { label: "来源说明", value: businessTopMove ? sourceNotePreview(businessTopMove.sourceNote) : "样本不足" },
  { label: "trace_id", value: resultMeta?.trace_id ?? "—" },
],
```

Basis evidence:

```ts
evidence: [
  { label: "维度字段", value: "rows[].basis_bucket / balance_change / contribution_pct" },
  { label: "主导分桶", value: topMovementDriver?.bucket ?? "—" },
  { label: "rule_version", value: resultMeta?.rule_version ?? "—" },
  { label: "source_version", value: resultMeta?.source_version ?? "—" },
],
```

Residual evidence:

```ts
evidence: [
  { label: "维度字段", value: "difference_attribution_waterfall.components" },
  { label: "残差", value: residualWaterfallComponent ? `${formatSignedYiCell(residualWaterfallComponent.amount)} 亿` : "—" },
  { label: "未支持项", value: unsupportedLabels.join("、") || "无", note: "未支持，不反推" },
  { label: "限制", value: "估值差和外币折算差没有可闭合字段，不在前端反算。" },
],
```

Coverage evidence:

```ts
evidence: [
  { label: "期限覆盖", value: maturityCoverage },
  { label: "集中度覆盖", value: concentrationCoverage },
  { label: "期限状态", value: drilldownStatusLabel(zqtzMaturityStructure?.meta.status) },
  { label: "集中度状态", value: drilldownStatusLabel(zqtzConcentrationAnalysis?.meta.status) },
],
```

Add `resultMeta` and `explanationClosure` to `analysisDimensionCards` dependencies when used.

**Step 4: Add evidence button to each card**

Because nested interactive elements are invalid, change each card from a single anchor to a card container:

```tsx
<article className="balance-movement-dimension-card" data-testid={`balance-movement-analysis-dimension-card-${card.key}`}>
  <a href={card.href} className="balance-movement-dimension-card__jump">
    <span>{card.title}</span>
    <strong>{card.metric}</strong>
    <p>{card.detail}</p>
  </a>
  <button
    type="button"
    className="balance-movement-dimension-card__evidence"
    data-testid={`balance-movement-analysis-dimension-evidence-${card.key}`}
    onClick={() => onEvidence(card.key)}
  >
    证据
  </button>
</article>
```

Update `AnalysisDimensionOverview` props:

```ts
function AnalysisDimensionOverview({
  cards,
  onEvidence,
}: {
  cards: AnalysisDimensionCard[];
  onEvidence: (key: string) => void;
})
```

**Step 5: Add drawer component**

```tsx
function AnalysisEvidenceDrawer({
  card,
  onClose,
}: {
  card: AnalysisDimensionCard;
  onClose: () => void;
}) {
  return (
    <aside
      role="dialog"
      aria-modal="true"
      aria-label="分析维度证据"
      className="balance-movement-evidence-drawer"
      data-testid="balance-movement-analysis-evidence-drawer"
    >
      <div className="balance-movement-evidence-drawer__header">
        <div>
          <span>分析维度证据</span>
          <h2>{card.title}</h2>
        </div>
        <button type="button" onClick={onClose} aria-label="关闭证据">
          关闭
        </button>
      </div>
      <strong>{card.metric}</strong>
      <p>{card.detail}</p>
      <dl className="balance-movement-evidence-drawer__list">
        {card.evidence.map((item) => (
          <div key={`${card.key}-${item.label}`}>
            <dt>{item.label}</dt>
            <dd>
              {item.value}
              {item.note ? <span>{item.note}</span> : null}
            </dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
```

Render after the dimension overview:

```tsx
{selectedEvidenceCard ? (
  <AnalysisEvidenceDrawer
    card={selectedEvidenceCard}
    onClose={() => setSelectedEvidenceKey(null)}
  />
) : null}
```

**Step 6: Add CSS**

```css
.balance-movement-dimension-card {
  position: relative;
}

.balance-movement-dimension-card__jump {
  display: grid;
  gap: 6px;
  color: inherit;
  text-decoration: none;
}

.balance-movement-dimension-card__evidence {
  justify-self: start;
  width: fit-content;
  padding: 4px 8px;
  border: 1px solid #cfd9e6;
  border-radius: 6px;
  background: #ffffff;
  color: #10284a;
  font-size: 12px;
  font-weight: 800;
}

.balance-movement-evidence-drawer {
  position: fixed;
  top: 0;
  right: 0;
  z-index: 40;
  display: grid;
  gap: 14px;
  width: min(420px, 100vw);
  height: 100vh;
  padding: 20px;
  overflow: auto;
  border-left: 1px solid #d7dfea;
  background: #ffffff;
  box-shadow: -18px 0 40px rgba(15, 23, 42, 0.14);
}

.balance-movement-evidence-drawer__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
}

.balance-movement-evidence-drawer__list {
  display: grid;
  gap: 10px;
  margin: 0;
}

.balance-movement-evidence-drawer__list div {
  padding: 10px;
  border: 1px solid #edf1f6;
  border-radius: 8px;
  background: #fbfcfe;
}

.balance-movement-evidence-drawer__list dt {
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.balance-movement-evidence-drawer__list dd {
  margin: 4px 0 0;
  color: #10284a;
  font-size: 13px;
  line-height: 1.45;
}
```

**Step 7: Run tests**

Run:

```bash
cd frontend
npm run test -- BalanceMovementAnalysisPage
```

Expected: PASS.

---

## Task 5: Extend CSV Export With Diagnostics

**Files:**

- Modify: `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx`
- Test: `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`

**Step 1: Write failing CSV assertions**

Extend the existing CSV export test:

```tsx
expect(csv).toContain("diagnostic");
expect(csv).toContain("explanation_closure");
expect(csv).toContain("unsupported_components");
expect(csv).toContain("口径待补");
expect(csv).toContain("residual_ratio");
```

**Step 2: Update CSV builder signature**

Add:

```ts
explanationClosure: BalanceExplanationClosure | null;
dimensionCards: AnalysisDimensionCard[];
```

**Step 3: Add rows to CSV**

Append after current `dimension` rows:

```ts
["diagnostic", "explanation_closure", explanationClosure?.headline, explanationClosure?.note],
["diagnostic", "residual_ratio", explanationClosure?.residualRatioPct === null ? "" : formatPct(explanationClosure?.residualRatioPct), "页面诊断阈值，不是正式指标"],
...dimensionCards.flatMap((card) =>
  card.tags.map((tag) => ["diagnostic", `${card.key}_tag`, tag.label, tag.tone]),
),
```

Guard nullable formatting:

```ts
const residualRatioText =
  explanationClosure?.residualRatioPct === null || explanationClosure?.residualRatioPct === undefined
    ? ""
    : formatPct(explanationClosure.residualRatioPct);
```

**Step 4: Pass new values from `handleExportCsv`**

```ts
explanationClosure,
dimensionCards: analysisDimensionCards,
```

**Step 5: Run tests**

Run:

```bash
cd frontend
npm run test -- BalanceMovementAnalysisPage
```

Expected: PASS.

---

## Task 6: Responsive Polish And Accessibility Check

**Files:**

- Modify: `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.css`
- Test: browser verification only unless tests reveal regressions

**Step 1: Check desktop**

Run or reuse the local dev server, then open:

```text
http://localhost:5888/balance-movement-analysis
```

Verify:

- First screen shows evidence strip, conclusion, dimension overview, and diagnostic tags.
- Closure panel is visible below waterfall.
- Evidence drawer opens and closes.
- No text overlaps in cards, tags, or drawer.
- CSV button still downloads.
- Browser console has zero warnings/errors.

**Step 2: Check mobile width**

Use Playwright/browser viewport around `390x844`.

Verify:

- Dimension cards stack.
- Tags wrap without overflow.
- Evidence drawer fits within viewport width.
- Closure grid collapses to one column.

**Step 3: Fix only local style issues**

Do not restyle unrelated page sections. Keep CSS in `BalanceMovementAnalysisPage.css`.

---

## Task 7: Final Verification

**Files:** no edits expected

Run:

```bash
cd frontend
npm run test -- BalanceMovementAnalysisPage
npm run typecheck
npm run debt:audit
```

From repo root:

```bash
git diff --check -- frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.css frontend/src/test/BalanceMovementAnalysisPage.test.tsx
```

Browser verification:

```text
http://localhost:5888/balance-movement-analysis
```

Expected:

- All focused tests pass.
- Typecheck passes.
- Debt audit reports no growth over baseline.
- Browser shows no console warnings/errors.
- CSV download includes diagnostic rows and keeps UTF-8 BOM.

---

## Final Report Template

Use this structure:

```text
已完成余额变动分析页的诊断增强：
- 新增解释闭合度面板，区分已支持解释项、未支持项、残差。
- 4 张分析维度卡新增诊断标签。
- 新增维度证据抽屉，展示字段、来源、治理元数据和限制说明。
- CSV 导出补充 diagnostic 行。

未做：
- 未新增后端口径。
- 未修改数据库。
- 未修改 client.ts。
- 未在前端反推估值差或外币折算差。

验证：
- npm run test -- BalanceMovementAnalysisPage: PASS
- npm run typecheck: PASS
- npm run debt:audit: PASS
- browser: PASS

剩余风险：
- 若 moss-* MCP 仍不可用，正式指标口径未通过外部契约服务复核；本次仅为页面诊断展示。
```
