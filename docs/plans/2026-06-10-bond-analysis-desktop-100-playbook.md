# Bond Analysis Desktop 100-Point Playbook

## Scope

This playbook is for `/bond-analysis` desktop only.

It covers the institutional cockpit in:

- `frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.tsx`
- `frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.module.css`
- `frontend/src/test/BondAnalyticsInstitutionalCockpit.test.tsx`

It does not cover mobile layout, backend metric definitions, certification, owner approval, or unrelated routes.

## Target

The target is not a prettier generic dashboard. The target is an institutional fixed-income desk page:

- conclusion first
- evidence visible
- missing data explicit
- dense but readable
- no invented judgment
- no frontend-made official metric
- every drilldown boundary clear

The page is "100 points" only when a desk user can answer, in the first screen:

1. What bond readout is available for the report date?
2. Is the displayed date exact, fallback, loading, or unavailable?
3. Which core fields are returned, and which are still evidence gaps?
4. Where can the user drill down for curve, DV01, holdings, return decomposition, and attribution?
5. Which values are backend facts rather than frontend judgment?

## Non-Negotiable Boundaries

Do not cross these lines to make the page look smarter:

- Do not create investment recommendations in the frontend.
- Do not invent risk thresholds, traffic lights, KRD reads, liquidity scores, or curve calls.
- Do not turn `null`, `undefined`, `NaN`, empty strings, or loading states into zero.
- Do not borrow `/bond-dashboard` evidence to certify `/bond-analysis`.
- Do not hide missing data behind decorative charts or placeholder trends.
- Do not add mock data to `frontend/src/api/client.ts`.
- Do not change backend contracts just to help the screen look complete.

Allowed:

- Rephrase backend-returned facts into clearer readouts.
- Show missing fields as evidence gaps.
- Make layout denser, more aligned, and more readable.
- Add tests that lock null handling, labels, and drilldown boundaries.

## 100-Point Rubric

### 1. Business Truth Boundary - 20 points

Full score means:

- All displayed values come from backend responses or existing adapters.
- Missing fields stay visibly missing.
- Fallback dates are labeled as fallback.
- The page never presents a frontend inference as a business verdict.
- Empty panels explain what is missing and why the page is not filling it.

Common deductions:

- `Math.abs(null)` or equivalent turns a missing value into zero.
- A card says "safe", "high risk", "actionable", or similar without backend support.
- A chart renders a fake flat trend when no trend exists.
- A stale/fallback snapshot looks like the current report date.

### 2. First-Screen Decision Hierarchy - 20 points

Full score means:

- The topbar gives identity, report date, data state, and core readout without truncation.
- The daily judgment strip reads like an evidence desk, not a marketing hero.
- The KPI rail is compact and immediately scannable.
- The first screen makes the difference between returned facts and gaps obvious.
- Users can see where to drill down next.

Common deductions:

- Main readout wraps badly or clips.
- Status fields compete visually with the conclusion.
- Too many equal-weight cards make the page feel flat.
- First screen has decoration but no stronger decision path.

### 3. Desktop Layout Discipline - 15 points

Full score means:

- Desktop grid uses stable column widths.
- Right evidence rail is wide enough for fixed-income labels and status text.
- Footer columns are weighted by importance, not equal by habit.
- Tables have clear horizontal affordance where needed.
- Cards are shallow, compact, and aligned.

Common deductions:

- Long Chinese labels collide with numbers.
- Equal thirds make supporting panels look as important as lead panels.
- Dense sections have inconsistent padding.
- Page reads as unrelated cards instead of one desk surface.

### 4. Evidence Gap System - 15 points

Full score means:

- Empty, loading, error, and pending states share one visual language.
- Evidence gaps use dashed, quiet, explicit surfaces.
- Missing module states say what is missing, not just "暂无数据".
- Gap styling does not overpower returned data.

Common deductions:

- Ant Design default empty states appear inside the cockpit.
- Different modules use different empty/error language.
- Pending panels look like failure or decoration.
- Missing data is visually quieter than surrounding chrome but not hidden.

### 5. Readability At Trading-Desk Density - 15 points

Full score means:

- Numeric values use tabular alignment.
- Labels can wrap where they need to.
- Values that must remain comparable do not wrap into ambiguous units.
- Small text remains readable on desktop.
- Important details use controlled two-line clamps rather than hard clipping.

Common deductions:

- Status details are forced into one line and disappear.
- Important evidence notes overflow their cards.
- Numbers and units split in confusing ways.
- Microcopy becomes too small to scan.

### 6. Drilldown And Workflow Closure - 10 points

Full score means:

- Each major cockpit block has the expected next action.
- Buttons lead to real existing detail modules.
- The cockpit states which modules are ready and which are pending.
- No button promises a conclusion that the target module cannot support.

Common deductions:

- "Open detail" actions exist but the surrounding card does not explain why.
- Drilldown labels are generic.
- A module appears complete when its evidence is pending.

### 7. Verification Evidence - 5 points

Full score means:

- Targeted component tests pass.
- Formatter/adapter tests relevant to the changed display path pass.
- Typecheck passes.
- Lint passes.
- Frontend debt audit passes.
- Desktop browser screenshot is inspected at 1440px, 1728px, and 1920px.

No visual "100 point" claim is allowed without rendered desktop evidence.

## Implementation Strategy

### Pass 0: Freeze The Business Boundary

Before editing, confirm:

- page/workflow: `/bond-analysis` institutional cockpit
- no backend metrics are being redefined
- no official fixed-income rule is being guessed
- no mobile work this round
- no unrelated dirty files will be touched

Files to inspect first:

- `BondAnalyticsInstitutionalCockpit.tsx`
- `BondAnalyticsInstitutionalCockpit.module.css`
- `BondAnalyticsInstitutionalCockpit.test.tsx`
- `frontend/src/features/bond-analytics/adapters/bondAnalyticsAdapter.ts`
- `frontend/src/features/bond-analytics/utils/formatters.ts`

### Pass 1: First-Screen Readout

Goal: make the opening surface feel like a fixed-income desk.

Checklist:

- topbar identity is compact
- topbar readout supports two-line conclusion and detail
- report date/fallback status is impossible to miss
- daily judgment strip explains what is returned and what is pending
- KPI rail uses returned facts only

Tests to add or keep:

- fallback date text is surfaced
- missing headline state is explicit
- core readout does not convert missing values to zero

### Pass 2: Evidence Rail And Analysis Grid

Goal: make the right side feel like evidence control, not a squeezed card.

Checklist:

- analysis grid gives curve/readout enough primary width
- evidence rail has enough width for Chinese labels
- curve panel separates returned curve points from pending state
- attribution boundary note wraps cleanly
- official drilldown buttons remain tied to real modules

Do not:

- infer a curve stance
- invent a KRD readout
- create warning colors from frontend thresholds

### Pass 3: Tables And Risk Slices

Goal: make holdings and DV01 evidence readable at desk density.

Checklist:

- sticky first column remains readable
- horizontal scroll affordance is visible
- null numeric fields display as `—`
- DV01 selection does not treat missing value as zero
- rating and metric gaps are counted and labeled

Required test:

- accounting DV01 mobile/summary lead row should ignore missing DV01 instead of selecting it through `Math.abs(null)`.

Even though mobile is out of scope visually, this helper feeds the cockpit and must remain correct.

### Pass 4: Footer And Secondary Modules

Goal: reduce the "equal card pile" feeling.

Checklist:

- footer uses weighted columns
- primary return evidence is wider than supporting panels
- buttons are attached to evidence context
- unavailable trend data does not draw a fake chart
- risk readout card says "returned fields" rather than implying formal approval

### Pass 5: Polish With Restraint

Goal: make the page feel finished without becoming decorative.

Checklist:

- card radius stays restrained
- borders and shadows are quiet
- color is semantic and sparse
- no gradient/orb decoration
- no card-inside-card visual clutter unless it is a real repeated data item
- all desktop text fits or wraps intentionally

## Desktop Visual Acceptance

Inspect these widths:

- 1440 x 900
- 1728 x 1000
- 1920 x 1080

At each width, verify:

- no clipped topbar conclusion
- no clipped report-date/status details
- KPI rail is readable
- analysis right rail is not cramped
- holdings table clearly hints more columns when horizontally scrollable
- footer columns have clear hierarchy
- empty/pending panels share the evidence-gap language
- no visible overlap

## Verification Commands

From `frontend/`:

```powershell
npm run test -- src/test/BondAnalyticsInstitutionalCockpit.test.tsx src/test/bondAnalyticsFormatters.test.ts
npm run test -- src/test/BondAnalyticsInstitutionalCockpit.test.tsx src/test/BondAnalyticsFilterActionStrip.test.tsx src/test/BondAnalyticsOverviewPanels.test.tsx src/test/BondAnalyticsViewContent.test.tsx src/test/BondAnalyticsView.test.tsx src/test/WorkbenchShell.test.ts src/test/navigation.test.ts src/test/bondAnalyticsFormatters.test.ts
npm run typecheck
npm run lint
npm run debt:audit
npm run build
```

From repo root:

```powershell
git diff --check -- frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.tsx frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.module.css frontend/src/features/bond-analytics/components/BondAnalyticsFilterActionStrip.tsx frontend/src/features/bond-analytics/components/BondAnalyticsFilterActionStrip.module.css frontend/src/features/bond-analytics/components/BondAnalyticsViewContent.tsx frontend/src/features/bond-analytics/components/BondAnalyticsViewContent.module.css frontend/src/test/BondAnalyticsInstitutionalCockpit.test.tsx frontend/src/test/BondAnalyticsFilterActionStrip.test.tsx frontend/src/test/BondAnalyticsViewContent.test.tsx docs/plans/2026-06-10-bond-analysis-desktop-100-playbook.md
node frontend/.codex-tmp/verify-bond-analysis-pass4.mjs
python -m pytest tests/test_golden_samples_capture_ready.py -q
python -m pytest tests/test_bond_analysis_business_owner_approval_status.py tests/test_golden_samples_capture_ready.py -q
```

Browser evidence:

- open `http://localhost:5888/bond-analysis`
- capture desktop screenshots at the three widths above
- inspect the rendered page before claiming visual completion

If the local dev server cannot start because of environment or native toolchain failure, report that separately. Do not replace rendered evidence with code inspection and still call the visual work complete.

## Current Implementation Progress

Already completed in the current pass:

- The cockpit footer was reweighted so return evidence is the primary lane and support panels no longer sit as equal cards.
- Fake trend presentation was removed when return time series data is unavailable.
- Evidence-gap copy was made explicit for missing return time series, pending drilldowns, and returned-versus-pending fields.
- Risk footer rows now use an explicit evidence list instead of a blind `slice(0, 3)`.
- Holdings overflow affordance was added so desktop users can see that more columns are available.
- The `/bond-analysis` lower review area was converted from a loose filter card into a command strip with refresh state and collapsed advanced parameters.
- The detail disclosure now states that it is a drilldown and parameter area, not a second bottom-of-page conclusion.
- Desktop screenshot verification has passed at 1440x900, 1728x1000, and 1920x1080 through `frontend/.codex-tmp/verify-bond-analysis-pass4.mjs`.
- Targeted and expanded component tests, typecheck, lint, debt audit, and build have passed in the current evidence set.
- Golden sample capture readiness now seeds the canonical bond analytics completed-build terminal for `GS-BOND-HEADLINE-A`, `GS-BOND-ANALYSIS-ACTION-ATTR-A`, and `GS-CONCENTRATION-MONITOR-A`; `tests/test_golden_samples_capture_ready.py` passes.
- Business-owner approval status remains fail-closed while owner approval is not captured; `tests/test_bond_analysis_business_owner_approval_status.py tests/test_golden_samples_capture_ready.py` passes.
- Full page verification has passed through `scripts/codex-verify-page.ps1 -PageSlug bond-analysis -Run`, covering candidate governance tests, bond analytics backend tests, frontend tests, browser a11y smoke, typecheck, debt audit, and production build.

This is therefore no longer a pure design sketch. It is a verified candidate desktop UI implementation, but `/bond-analysis` is still evidence-pending for page closure and business certification.

## Owner Handoff Status

Current state:

- Desktop candidate implementation is ready for owner handoff.
- Visual and regression evidence can support a candidate UI review.
- Golden-sample capture readiness is verified for the relevant bond analytics samples.
- Business-owner approval is not captured.
- `formal_use_allowed=false`, `closure_approved=false`, and `certification_effect=none` must remain in force.

The remaining work is not another visual polish pass. It is an approval-capture path:

1. The owner reviews the sign-off, governance audit, and owner evidence packets.
2. The owner reviews the fixed-income convention decision draft and confirms the units, signs, date basis, clean/dirty value basis, DV01 basis, and yield convention.
3. The owner completes only `docs/pnl/bond-analysis-business-owner-approval-template.md`.
4. Every evidence review item in that template must be set to `yes` for approval.
5. `python scripts/check_bond_analysis_business_owner_approval.py --require-captured` must pass before anyone says owner approval is captured.
6. `python scripts/codex_page_readiness.py --page-slug bond-analysis` and `scripts/codex-verify-page.ps1 -PageSlug bond-analysis -Run` must be rerun after the signed template is present.
7. If the owner chooses `reject` or `request_changes`, fix only the named issue, rerun the relevant narrow checks, and keep the page fail-closed.

Do not use this handoff to widen scope into mobile layout, backend metric redesign, `/bond-dashboard` certification evidence, or formal fixed-income metric truth.

## Current Gap List

Known current gaps before final "100 point" claim:

- Spec/visual reviewer returned OKAY for the implemented desktop UI evidence; that review does not approve page closure.
- Code-quality reviewers did not return before timeout; manual diff review plus targeted/full gates were used as substitute evidence and must not be described as independent code-review approval.
- MCP metric evidence tools were not exposed in the current Codex App session, so metric definitions must not be guessed.
- `/bond-analysis` remains evidence-pending from a certification perspective; golden samples are capture-ready, but business-owner approval is not captured and formal use is still disallowed.

## How To Finish The Remaining Gap

Use this order:

1. Resolve reviewer feedback.
   - Keep the spec/visual reviewer result as candidate implementation evidence only; do not treat it as page signoff.
   - If a code-quality reviewer later returns a real high- or medium-severity finding, fix only findings tied to `/bond-analysis` desktop, evidence boundaries, golden-sample fixture correctness, or changed files.
   - Do not widen the task into mobile or backend metric redesign.

2. Lock the UI proof.
   - Re-run the pass4 desktop screenshot script after any fix.
   - Inspect the full-page, footer, and bottom review screenshots at 1440, 1728, and 1920 widths.
   - Treat any overlap, clipped Chinese text, or fake-looking empty state as a blocker.

3. Lock the regression proof.
   - Re-run the focused component tests for cockpit, filter strip, and view content.
   - Re-run the expanded bond-analysis shell tests.
   - Re-run typecheck, lint, debt audit, build, and diff whitespace checks.

4. Separate visual completion from business certification.
   - UI implementation evidence can be called visually verified only if the rendered evidence passes.
   - Business certification cannot be called complete until page contracts, metric definitions, lineage, and owner signoff are available.
   - Golden-sample capture readiness is not owner approval and must not be described as formal certification.
   - If MCP evidence remains unavailable, final wording must say so directly instead of implying metric approval.

## Done Definition

This candidate desktop implementation is ready for handoff only when:

- the cockpit follows the desktop acceptance checklist
- no business boundary is crossed
- targeted and expanded frontend checks pass
- lint, typecheck, and debt audit pass
- rendered desktop evidence has been inspected
- remaining certification/owner/MCP risks are explicitly reported
