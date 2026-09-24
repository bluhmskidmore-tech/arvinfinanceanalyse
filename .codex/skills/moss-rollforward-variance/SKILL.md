---
name: moss-rollforward-variance
description: "【MOSS滚动与方差分析】用于余额变动、PnL桥、运营分析、期间方差、roll-forward和管理层解读工作。"
---

# MOSS Roll-Forward And Variance

Use this skill for MOSS workflows that must explain movement, not just show two numbers. It adapts roll-forward and variance-commentary workflow patterns.

## Roll-Forward Pattern

Every movement schedule should foot:

```text
Beginning balance
  + additions / new activity
  + accruals or income
  - reversals / settlements / payments
  +/- reclasses, valuation, FX, or adjustments
= Ending balance
```

Each line must tie to a source query, API field, golden sample row, or documented rule. If the schedule does not foot, surface the unexplained delta; do not plug it.

## Variance Pattern

For current vs prior, current vs budget, or current vs benchmark:

1. Determine materiality threshold from contract, docs, or existing tests.
2. Flag lines over threshold and lines that must always be explained.
3. Produce driver commentary from underlying activity, not from the headline delta alone.
4. If the driver is not clear from evidence, say `driver unclear` and preserve the gap.
5. Keep basis explicit: formal, analytical, scenario, preview, or vendor.

## MOSS Implementation Checks

- Formal movement logic belongs in backend services/core finance, not page components.
- Frontend may sort, group, and format, but must not recalculate governed movement totals.
- Dates must distinguish requested report date, resolved report date, generated time, and source/as-of date where present.
- Tests should cover at least one foot check and one threshold/commentary edge case when behavior changes.

## Useful Outputs

Return a roll-forward table, foot-check status, variance table, top drivers, and unresolved breaks with exact source evidence.
