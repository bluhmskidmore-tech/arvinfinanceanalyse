# Strategy Closed Loop Runbook

This workflow keeps the stock strategy evidence-first and observation-only.

## What The Loop Does

The closed loop combines:

- Livermore A-share market gate, sector rank, stock candidates, theme breakout, and risk exit.
- Macro bond linkage context.
- Macro adversarial anti-crowding overlay from macro toolkit outputs.
- Candidate-history replay evidence when a matching snapshot exists.

The output is for review and observation. It must not be treated as an order, trade instruction, investment advice, or automatic portfolio action.

## Data Prerequisites

Required for the stock side:

- Choice stock daily observation data.
- Choice stock factor snapshot when factor evidence is needed.
- Livermore position snapshot when risk-exit watch rows are needed.
- Candidate history table when replay evidence should be `available` and replay window status should be structured.

Required for the macro adversarial side:

- Temporary `data/macro_toolkit/output/final_signal.csv`, preferred for the current closed-loop validation path.
- `data/macro_toolkit/output/crowding_latest.csv`, fallback/degraded.

When neither file exists, the adversarial overlay must show `missing`; that is not neutral evidence.

## Current Validation Shape

The current closed-loop verification is intentionally narrow:

- Macro adversarial validation reads the temporary `final_signal.csv` first, then falls back to `crowding_latest.csv`.
- Candidate-history validation has two layers: structured replay-window status from `backtest_window_summary`, plus smoke evidence with snapshot date, row count, current-candidate match count, and sample rows when a matching snapshot exists.
- Frontend validation relies on the closed-loop summary surface to show entry gate, adversarial gate, replay evidence, risk exit, and lineage together.

This is enough to prove the observation loop is wired end to end, but it is not yet a full replay-consistency framework.

## Refresh Order

1. Refresh or materialize Choice stock observations.
2. Refresh macro toolkit source data, including CFFEX member-rank data.
3. Run macro toolkit scripts that generate `crowding_latest.csv` and then the temporary `final_signal.csv`.
4. Load `/ui/macro/toolkit/adversarial-signal` to verify the overlay state.
5. Load `/ui/market-data/livermore/signal-confluence` to verify Livermore + macro + adversarial confluence.
6. Open `/stock-analysis` and review the closed-loop summary.

## Gate Meanings

- `entry_gate=open`: market and macro context allow entry observation.
- `entry_gate=observe_only`: candidates remain visible, but are not cleared for entry observation.
- `entry_gate=blocked`: anti-crowding or another gate blocks entry observation.
- `adversarial_gate=pass` or `allow`: anti-crowding overlay does not block.
- `adversarial_gate=block`: anti-crowding overlay blocks entry observation.
- `adversarial_gate=degraded`: only partial anti-crowding evidence exists.
- `adversarial_gate=missing`: no anti-crowding output file exists.
- `closed_loop_state.replay_status.window_status=valid`: replay window has decision-usable completed stats.
- `closed_loop_state.replay_status.window_status=partial`: replay window has completed stats plus pending, unsupported, or proxy-only dates.
- `closed_loop_state.replay_status.window_status=unsupported`: replay window has no decision-usable completed stats.
- `replay_evidence.status=available`: matching candidate-history snapshot exists, with snapshot date, row count, matched current-candidate count, and sample rows.
- `replay_evidence.status=missing`: no matching candidate-history snapshot exists.
- `lineage_status=complete`: overlay evidence is present and usable.
- `lineage_status=degraded` or `missing`: show as a boundary to fill.

## Verification Commands

Backend:

```bash
python -m pytest -q tests/test_macro_adversarial_signal_service.py tests/test_livermore_signal_confluence.py tests/test_market_data_livermore_api.py tests/test_result_meta_on_all_ui_endpoints.py
python -m py_compile backend/app/services/macro_adversarial_signal_service.py backend/app/services/livermore_signal_confluence_service.py backend/app/api/routes/macro_toolkit.py backend/app/api/routes/market_data_livermore.py
```

Frontend:

```bash
cd frontend
npm run test -- src/test/StockAnalysisPageModel.test.ts src/test/StockAnalysisPage.test.tsx --pool=forks --poolOptions.forks.singleFork=true --reporter=dot
npm run typecheck
npm run debt:audit
```

## Operating Notes

- CFFEX anti-crowding is a macro risk coverage layer, not an A-share alpha selector, trade recommendation, or auto-order trigger.
- Missing anti-crowding evidence should never be displayed as a positive or neutral proof.
- Optional overlay absence should not overwrite the core Livermore result metadata as `error`.
- Candidate-history replay remains a bounded validation layer. It exposes structured replay-window status and snapshot evidence, but it does not attempt finer-grained replay consistency against current gates or decisions.
- Persisted closed-loop gate snapshots and any candidate-history schema migration are deferred to a later dedicated follow-up.
