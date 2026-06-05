# Strategy Closed Loop Implementation Plan

**Goal:** Combine the A-share Livermore observation strategy with the macro anti-crowding mode into a governed, evidence-first closed loop.

**Boundary:** Observation and review only. No order placement, no automatic portfolio action, and no wording that can be read as trading advice or execution instruction.

## Current State

- Livermore already produces market gate, sector rank, stock candidates, theme breakout, and risk exit.
- Macro toolkit has CFFEX crowding and `signal_aggregator` outputs, but those outputs were not a first-class input to stock confluence.
- Stock analysis page consumed Livermore and broad macro confluence, but did not show anti-crowding gate status.
- The current verification shape is intentionally lightweight: temporary `final_signal.csv`, structured candidate-history replay-window status, snapshot smoke evidence, and frontend closed-loop summary.

## First Execution Slice

1. Add `macro_adversarial_signal_service`.
   - Read the temporary `final_signal.csv` first.
   - Fall back to `crowding_latest.csv`.
   - Return explicit missing/degraded states when files are absent or partial.

2. Add governed API.
   - `GET /ui/macro/toolkit/adversarial-signal`
   - Result kind: `macro_toolkit.adversarial_signal`
   - Rule version: `rv_macro_adversarial_signal_v1`

3. Feed anti-crowding into Livermore confluence.
   - Add `adversarial_context`.
   - Add `closed_loop_state`.
   - Convert entries to observation-only when the anti-crowding gate blocks.
   - Keep missing anti-crowding visible without treating it as neutral proof.
   - Keep the anti-crowding layer governed as a risk coverage overlay, not a trading recommendation.

4. Add stock analysis closed-loop summary.
   - Show entry gate, adversarial gate, risk exit, replay, and lineage on the decision surface.
   - Keep missing/stale evidence visible.
   - Render structured `closed_loop_state.replay_status` for replay windows and `replay_evidence` for snapshot smoke evidence.

5. Verify.
   - Backend pytest for adversarial signal, confluence, API envelope.
   - Frontend stock-analysis model/page tests.
   - Frontend debt audit.

## Deferred Slice

- Candidate-history replay stays bounded for now: expose replay-window status from `backtest_window_summary` plus snapshot date, row count, current-candidate match count, and sample rows when a matching snapshot exists, but do not claim fine-grained replay consistency against current gates, statuses, or decisions.
- Persisted closed-loop gate snapshots in candidate history are deferred to a later dedicated slice.
- Any schema migration required to persist those gate snapshots is also deferred to a later dedicated slice.

## Success Criteria

- Stock analysis answers whether entries are open, observation-only, blocked, or missing evidence.
- Anti-crowding data is a formal risk coverage overlay, not a stock alpha selector, trade recommendation, or auto-order signal.
- Missing anti-crowding files are visible.
- Result meta stays governed and does not overwrite core Livermore lineage when optional overlay files are absent.
