# Polar MOSS Agent Bench Design

## Goal

Adapt Polar to MOSS-V3 as an external development-agent training and evaluation layer. Polar should not be introduced into the production frontend or backend runtime.

The first useful target is a MOSS-Agent-Bench harness: define scoped development tasks, run an agent in an isolated workspace, collect evidence and validation output, then score the result for Polar-style rollout training.

## Placement

Polar sits outside the repository runtime:

```text
Polar rollout server
  -> isolated MOSS-V3 workspace
  -> coding agent harness
  -> MOSS validation commands and MCP evidence
  -> scorecard JSON
  -> trainer reward
```

This keeps MOSS architecture unchanged while making the existing development protocol trainable.

## Initial Task Family

Start with page-level business display fixes:

- Ledger PnL unit mismatch
- PnL attribution null or precision handling
- Risk overview stale or fallback date display
- Average balance date semantics

Each task should specify page, goal, allowed scope, forbidden paths, required evidence, required checks, business gates, and page gates.

## Reward Priorities

The reward should mirror the project contract:

1. Business metric correctness
2. Page-level closure
3. Traceability and validation
4. Minimal, reviewable changes

Hard failures include missing required metric evidence, failed required checks, failed business gates, and forbidden-path changes. Out-of-scope diffs are penalized so agents learn to keep changes local.

## MVP Files

The initial scaffold lives under `scripts/agent_eval/`:

- `reward.py`: pure scorecard logic
- `validate_task.py`: JSON CLI for local or Polar runners
- `tasks/ledger_pnl_unit_mismatch_001.json`: first sample task
- `README.md`: expected result JSON and CLI usage

Focused pytest coverage lives in `tests/test_agent_eval_reward.py`.

