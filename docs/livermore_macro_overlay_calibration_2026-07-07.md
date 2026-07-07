# Livermore Macro Overlay Calibration Check

Date: 2026-07-07

Scope: calibration evidence for `backend/app/core_finance/gate_macro_overlay.py` (`rv_market_gate_macro_overlay_v1`). This report is read-only analysis against `data/moss.duckdb`; it does not change production constants.

## Conclusion

Recommendation: keep the current v1 parameters for production.

Current parameters:

| Item | Current value | Recommendation |
| --- | ---: | ---: |
| recession threshold | `macro_score < 0.25` | unchanged |
| contraction threshold | `0.25 <= macro_score < 0.40` | unchanged |
| recession cap | `0.25` | unchanged |
| contraction cap | `0.50` | unchanged |

Reason: the current historical window is too thin for a production calibration upgrade. The full three-component macro-score period starts only on 2025-12-30 and contains no recession/contraction triggers. The only current trigger is one partial-component contraction interval in 2025-10, before PE/10Y price-spread history exists. There are zero recession observations, so neither the recession threshold nor recession cap can be calibrated from this sample.

No constants were changed and `formula_version` remains `rv_market_gate_macro_overlay_v1`.

## Evidence Limits

MCP limitation: the current Codex App tool surface did not expose `gitnexus_*` or `moss-*` MCP calls. `tool_search` found no GitNexus tools. `codex mcp list` also failed before listing servers because the local global Codex config rejects `service_tier = "default"` (`expected fast or flex`). The repo-local `.mcp.json` and `.codex/config.toml` do declare `gitnexus`, `moss-metric-contracts`, `moss-lineage-evidence`, and `moss-data-catalog`.

Fallback evidence used:

- Production code paths: `cycle_macro_score.py`, `gate_macro_overlay.py`, `market_data_livermore_service.py`, `livermore_strategy.py`.
- Tests: `tests/test_cycle_macro_score.py`, `tests/test_cycle_macro_score_golden.py`, `tests/test_gate_macro_overlay.py`.
- DuckDB read-only connection to `data/moss.duckdb`.

## Method

Daily series:

- Use CSI300 trading days from the same broad-index union logic as production: `fact_choice_macro_daily` first, `choice_market_snapshot` fallback.
- For each trading day T, use only macro rows with `trade_date <= T`.
- PMI uses latest `M0017126`.
- Credit impulse uses social-financing YoY `M5525763` when at least two observations exist; M2 `M0001385` is only a fallback.
- Price spread uses PE `CA.CSI300_PE` and China 10Y `EMM00166466` only when both have the same latest landed trade date.
- Macro score is computed through `build_cycle_macro_snapshot`, preserving the no-lookahead and component reweighting behavior.
- Raw Livermore exposure is replayed with `evaluate_market_gate` using the latest 260 CSI300 observations and same-day `fact_livermore_gate_supplement_daily` when available.

Xun series:

- For the ten-day view, use the last available CSI300 trading day in each calendar xun: day 1-10, 11-20, and 21-month-end.

Cap-effect definitions:

- `delta = exposure_raw - exposure_capped`.
- Endpoint loss avoided over horizon H: `delta * max(0, -CSI300_return_H)`.
- Endpoint upside missed over horizon H: `delta * max(0, CSI300_return_H)`.
- Endpoint net: loss avoided minus upside missed. Positive means the cap helped at that horizon.
- Path drawdown saved uses the worst close inside the forward H-trading-day window.
- These horizon sums use overlapping daily observations, so they are calibration diagnostics, not standalone portfolio PnL.

## Data Coverage

| Series | Rows | Date range | Unit | Source note |
| --- | ---: | --- | --- | --- |
| `CA.CSI300` | 422 | 2024-09-25 to 2026-06-26 | index | `sv_tushare_index_daily_61bfe54e9e84` |
| `CA.CSI300_PE` | 116 | 2025-12-30 to 2026-06-26 | x | `sv_tushare_index_dailybasic_6245002ef322` |
| `EMM00166466` | 120 | 2025-12-30 to 2026-06-26 | % | `sv_public_bond_zh_us_rate_20260628` |
| `M0017126` PMI | 29 | 2024-01-01 to 2026-05-01 | index | `sv_cycle_rotation_macro_fixture_v1` |
| `M5525763` social-financing YoY | 29 | 2024-01-01 to 2026-05-01 | % | `sv_cycle_rotation_macro_fixture_v1` |
| `M0001385` M2 YoY fallback | 28 | 2024-01-01 to 2026-04-01 | % | fallback only |

Macro-score coverage on CSI300 trading days:

| Slice | Rows | Date range | Score min | Score max | Score mean |
| --- | ---: | --- | ---: | ---: | ---: |
| Any computable component set | 422 | 2024-09-25 to 2026-06-26 | 0.389732 | 0.752917 | 0.508382 |
| Full PMI + credit + price-spread | 116 | 2025-12-30 to 2026-06-26 | 0.4904 | 0.7529 | n/a |

State counts:

| Slice | Recession | Contraction | Neutral | Expansion |
| --- | ---: | ---: | ---: | ---: |
| Daily, any computable set | 0 | 17 | 360 | 45 |
| Daily, full three-component set | 0 | 0 | 71 | 45 |
| Xun, any computable set | 0 | 3 | 54 | 7 |

## Current Trigger Intervals

Current thresholds produce one trigger interval.

| State | Start | End | Trading days | Start score | Component set | Start raw exposure | Start capped exposure | 20D return | 60D return | 20D worst path | 20D best path |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| contraction | 2025-10-09 | 2025-10-31 | 17 | 0.3897 | PMI + credit, price-spread missing/reweighted | 0.75 | 0.50 | -0.34% | +0.18% | -4.15% | +0.81% |

There were no recession intervals.

## Forward Return Distribution

Event-level distribution, using only the start date of each trigger interval:

| State | Horizon | Events | Mean | Median | Min | Max | Positive rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| recession | 20D | 0 | n/a | n/a | n/a | n/a | n/a |
| recession | 60D | 0 | n/a | n/a | n/a | n/a | n/a |
| contraction | 20D | 1 | -0.34% | -0.34% | -0.34% | -0.34% | 0.00% |
| contraction | 60D | 1 | +0.18% | +0.18% | +0.18% | +0.18% | 100.00% |

Daily-trigger distribution, using every triggered trading day:

| State | Horizon | Days | Mean | Median | P25 | P75 | Min | Max | Positive rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| contraction | 20D | 17 | -0.91% | -0.34% | -4.13% | +1.34% | -5.68% | +2.52% | 41.18% |
| contraction | 60D | 17 | +2.39% | +3.03% | +0.68% | +3.77% | -0.95% | +5.47% | 88.24% |

Interpretation: the current contraction trigger did reduce short-horizon downside in this single episode, but the same episode mostly recovered over 60 trading days.

## Current Cap Effect

Current caps applied on 16 of the 17 triggered days. One contraction day had raw exposure already at or below the 0.50 cap.

| Horizon | Eligible days | Trigger days | Cap-applied days | Avg exposure reduction | Avg forward return on cap days | Endpoint loss avoided | Endpoint upside missed | Endpoint net | Path drawdown saved | Path upside missed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20D | 402 | 17 | 16 | 0.4062 | -1.12% | 12.88 pp | 3.61 pp | +9.27 pp | 19.88 pp | 14.41 pp |
| 60D | 362 | 17 | 16 | 0.4062 | +2.27% | 0.49 pp | 14.43 pp | -13.94 pp | 26.89 pp | 20.88 pp |

At the single interval start:

| Horizon | Cap event starts | Endpoint loss avoided | Endpoint upside missed | Path drawdown saved | Path upside missed |
| --- | ---: | ---: | ---: | ---: | ---: |
| 20D | 1 | 0.09 pp | 0.00 pp | 1.04 pp | 0.20 pp |
| 60D | 1 | 0.00 pp | 0.04 pp | 1.39 pp | 0.20 pp |

Sequential one-day exposure replay:

| Raw total return | Overlay total return | Overlay excess | Raw max drawdown | Overlay max drawdown | Max-drawdown reduction | 1D loss avoided | 1D upside missed |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| +14.81% | +15.38% | +0.57 pp | -7.46% | -7.46% | 0.00 pp | 3.09 pp | 2.64 pp |

## Sensitivity: Thresholds

Threshold grid changes recession boundary and contraction/neutral boundary by +/-0.05. Expansion boundary is not cap-bearing and is held at 0.60 for the overlay analysis.

Current caps are used here: recession 0.25, contraction 0.50.

| Recession threshold | Contraction upper threshold | 20D trigger days | 20D cap days | 20D endpoint net | 60D trigger days | 60D cap days | 60D endpoint net | 1D replay excess |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.20 | 0.35 | 0 | 0 | 0.00 pp | 0 | 0 | 0.00 pp | 0.00 pp |
| 0.20 | 0.40 | 17 | 16 | +9.27 pp | 17 | 16 | -13.94 pp | +0.57 pp |
| 0.20 | 0.45 | 99 | 74 | -81.06 pp | 99 | 74 | -244.71 pp | -4.15 pp |
| 0.25 | 0.35 | 0 | 0 | 0.00 pp | 0 | 0 | 0.00 pp | 0.00 pp |
| 0.25 | 0.40 | 17 | 16 | +9.27 pp | 17 | 16 | -13.94 pp | +0.57 pp |
| 0.25 | 0.45 | 99 | 74 | -81.06 pp | 99 | 74 | -244.71 pp | -4.15 pp |
| 0.30 | 0.35 | 0 | 0 | 0.00 pp | 0 | 0 | 0.00 pp | 0.00 pp |
| 0.30 | 0.40 | 17 | 16 | +9.27 pp | 17 | 16 | -13.94 pp | +0.57 pp |
| 0.30 | 0.45 | 99 | 74 | -81.06 pp | 99 | 74 | -244.71 pp | -4.15 pp |

Readout:

- Moving the recession threshold has no observed effect because the sample has no scores below 0.3897.
- Lowering the contraction upper threshold to 0.35 eliminates all triggers in-sample; this is not evidence that it is better, only that the sample does not cover stress.
- Raising the contraction upper threshold to 0.45 captures 99 days and materially worsens both 20D and 60D endpoint diagnostics.

## Sensitivity: Caps

Current thresholds are used here: recession 0.25, contraction 0.40. Since there are no recession observations, recession cap choices are invariant in this sample.

| Recession cap | Contraction cap | 20D cap days | 20D loss avoided | 20D upside missed | 20D endpoint net | 60D cap days | 60D loss avoided | 60D upside missed | 60D endpoint net | 1D replay excess |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.20 | 0.40 | 17 | 15.69 pp | 4.87 pp | +10.82 pp | 17 | 0.59 pp | 18.60 pp | -18.01 pp | +0.71 pp |
| 0.20 | 0.50 | 16 | 12.88 pp | 3.61 pp | +9.27 pp | 16 | 0.49 pp | 14.43 pp | -13.94 pp | +0.57 pp |
| 0.20 | 0.60 | 16 | 10.08 pp | 2.61 pp | +7.47 pp | 16 | 0.39 pp | 10.70 pp | -10.31 pp | +0.26 pp |
| 0.25 | 0.40 | 17 | 15.69 pp | 4.87 pp | +10.82 pp | 17 | 0.59 pp | 18.60 pp | -18.01 pp | +0.71 pp |
| 0.25 | 0.50 | 16 | 12.88 pp | 3.61 pp | +9.27 pp | 16 | 0.49 pp | 14.43 pp | -13.94 pp | +0.57 pp |
| 0.25 | 0.60 | 16 | 10.08 pp | 2.61 pp | +7.47 pp | 16 | 0.39 pp | 10.70 pp | -10.31 pp | +0.26 pp |
| 0.30 | 0.40 | 17 | 15.69 pp | 4.87 pp | +10.82 pp | 17 | 0.59 pp | 18.60 pp | -18.01 pp | +0.71 pp |
| 0.30 | 0.50 | 16 | 12.88 pp | 3.61 pp | +9.27 pp | 16 | 0.49 pp | 14.43 pp | -13.94 pp | +0.57 pp |
| 0.30 | 0.60 | 16 | 10.08 pp | 2.61 pp | +7.47 pp | 16 | 0.39 pp | 10.70 pp | -10.31 pp | +0.26 pp |

Readout:

- A 0.40 contraction cap is more defensive over 20D and in one-day replay, but misses more of the 60D rebound.
- A 0.60 contraction cap misses less 60D upside, but gives up short-horizon protection.
- The current 0.50 cap is a middle point; the sample is too small to prove that 0.40 or 0.60 dominates.

## Combined Grid Summary

The requested 3 x 3 threshold grid and 3 x 3 cap grid has 81 combinations. In this sample it collapses because no recession states occur; recession threshold and recession cap do not change any metric. Unique outcomes are driven by the contraction upper threshold and contraction cap.

| Contraction upper threshold | Contraction cap | Cap days, 20D | 20D endpoint net | Cap days, 60D | 60D endpoint net | 1D replay excess | 1D max-drawdown reduction |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 0.40 | 0 | 0.00 pp | 0 | 0.00 pp | 0.00 pp | 0.00 pp |
| 0.35 | 0.50 | 0 | 0.00 pp | 0 | 0.00 pp | 0.00 pp | 0.00 pp |
| 0.35 | 0.60 | 0 | 0.00 pp | 0 | 0.00 pp | 0.00 pp | 0.00 pp |
| 0.40 | 0.40 | 17 | +10.82 pp | 17 | -18.01 pp | +0.71 pp | 0.00 pp |
| 0.40 | 0.50 | 16 | +9.27 pp | 16 | -13.94 pp | +0.57 pp | 0.00 pp |
| 0.40 | 0.60 | 16 | +7.47 pp | 16 | -10.31 pp | +0.26 pp | 0.00 pp |
| 0.45 | 0.40 | 88 | -104.35 pp | 88 | -301.85 pp | -5.38 pp | +0.21 pp |
| 0.45 | 0.50 | 74 | -81.06 pp | 74 | -244.71 pp | -4.15 pp | 0.00 pp |
| 0.45 | 0.60 | 74 | -62.07 pp | 74 | -189.21 pp | -3.18 pp | 0.00 pp |

## Recommendation And Impact Versus Current

Production recommendation: no parameter upgrade.

Why not lower the contraction threshold to 0.35:

- It removes all observed triggers, but that is an absence-of-signal result from one short, non-stress sample.
- It would discard the only observed 20D defensive benefit from the current threshold.

Why not raise the contraction threshold to 0.45:

- It expands trigger days from 17 to 99.
- It is materially worse in the sample: 20D endpoint net changes from +9.27 pp at current settings to -81.06 pp with the current 0.50 contraction cap; 60D endpoint net changes from -13.94 pp to -244.71 pp.

Why not change caps:

- There are no recession observations, so recession cap cannot be learned.
- Contraction cap 0.40, 0.50, and 0.60 express a clear defense/rebound tradeoff but do not provide stable evidence for a new production value.
- Current 0.50 remains the least speculative middle point.

Impact versus current: none, because no constants changed.

## Verification

Read-only analysis command used:

```powershell
@'
# Python script run from repo root.
# It opened duckdb.connect('data/moss.duckdb', read_only=True),
# replayed production macro-score and market-gate logic,
# and printed the tables summarized above.
'@ | python -
```

No production code was changed, no tests were updated, and no commit/stash was made.
