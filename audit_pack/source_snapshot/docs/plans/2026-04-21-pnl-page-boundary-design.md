# PnL Page Boundary Design

## Goal

Make the three PnL-facing pages understandable without requiring users to reverse-engineer backend services.

This design does not change calculations.
It only fixes page identity, wording, and boundary rules so users can tell:

1. which page shows business-category profit,
2. which page shows formal detailed profit,
3. which page explains profit movement.

## Recommended approach

Use explicit page separation, not page merging.

There are two other possible approaches:

1. Merge `/pnl`, `/pnl-bridge`, and `/product-category-pnl` into one large workbench.
2. Keep the current structure, but make the page purpose and basis explicit.

Recommendation: keep the current structure and make the purpose explicit.

Reason:

- The backend already exposes three different read models.
- The pages are already wired to the correct routes.
- The main problem is user interpretation, not route absence.
- A merge would create a larger page with even more mixed concepts.

So the lowest-risk path is not "build a new page." It is "make each page admit exactly what it is."

## Final mapping

### 1. `/product-category-pnl`

Purpose:
- Answer: "Which business category made or lost money?"

Data nature:
- System-layer business-category profit view.
- Built from ledger reconciliation and daily-average balance logic.
- Can show formal baseline plus scenario preview.

Page title:
- `产品分类损益`

Subtitle:
- `按业务分类查看损益、FTP 和净收入。用于经营分析，不等同于逐笔损益明细。`

Badge:
- `System Layer`

Forbidden wording:
- `正式损益明细`
- `逐笔损益`
- `PnL Bridge`

### 2. `/pnl`

Purpose:
- Answer: "What does the formal detailed PnL look like for this report date?"

Data nature:
- Formal detailed profit read model.
- Shows FI rows and non-standard bridge rows.
- This is the page for detailed formal profit data, not business-category management reporting.

Page title:
- `正式损益明细`

Subtitle:
- `查看正式口径损益汇总与明细，包括 FI 明细和非标桥接行。页面只展示后端结果，不在前端重算。`

Badge:
- `Formal Detail`

Forbidden wording:
- `经营损益`
- `产品分类损益`
- `损益解释`

### 3. `/pnl-bridge`

Purpose:
- Answer: "Why did profit change into the current number?"

Data nature:
- Formal bridge explanation view.
- Focuses on explained PnL, actual PnL, residual, and decomposition effects.
- This is not the detailed ledger-like page.

Page title:
- `正式损益解释`

Subtitle:
- `查看 actual PnL 与 explained PnL 的差异，以及 carry、roll-down、利率、利差等桥接效应。`

Badge:
- `Formal Explain`

Forbidden wording:
- `正式损益明细`
- `经营损益`
- `产品分类损益`

## Basis rules

### `/product-category-pnl`

- Default page meaning: business-category system-layer profit.
- If a scenario rate is applied, the page must visibly state that the view is scenario preview.
- Formal baseline and scenario preview must never look identical in wording.

Required labels:
- Baseline: `正式基线`
- Scenario: `情景预览`

### `/pnl`

- Default page meaning: formal detailed PnL.
- If basis is switched to analytical, the page must visibly state that it is no longer the formal mainline view.

Required labels:
- `Formal`
- `Analytical (只读分析)`

### `/pnl-bridge`

- Always label as formal-only.
- Do not expose analytical wording on this page unless a real analytical bridge surface is later added.

Required label:
- `Formal Only`

## Copy rules

### Shared rule

Every PnL page must answer one question in the first screen.
Do not let the user infer the page purpose from tabs or charts.

### Required first-screen sentence pattern

Each page should contain one sentence in this shape:

- `/product-category-pnl`: `本页回答：哪类业务赚钱，哪类业务亏钱。`
- `/pnl`: `本页回答：正式口径下，哪些明细构成了当前损益。`
- `/pnl-bridge`: `本页回答：当前损益为什么会变成这样。`

## Navigation rule

The three pages should sit next to each other in navigation only if each label is explicit.

Recommended navigation labels:

- `产品分类损益`
- `正式损益明细`
- `正式损益解释`

Avoid:

- `损益分析`
- `PnL`
- `Bridge`

These labels are too short and force users to guess the page boundary.

## What this design does not change

- No backend calculation changes
- No route changes
- No schema changes
- No bridge formula changes
- No FTP policy changes

## Acceptance criteria

1. A user can tell the difference between the three pages from title, subtitle, and badge alone.
2. `/product-category-pnl` is no longer likely to be mistaken for `/pnl`.
3. `/pnl-bridge` is no longer likely to be mistaken for the detailed formal PnL page.
4. Analytical and scenario states are visibly labeled rather than implied.

## Suggested next step

If accepted, update the three frontend pages so the title, subtitle, badge, and first-screen summary sentence follow this document.
