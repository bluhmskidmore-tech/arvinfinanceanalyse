# MOSS Agent Evaluation

This directory is a small MOSS-Agent-Bench scaffold for Polar-style rollout scoring.

It does not change the MOSS frontend or backend runtime. A rollout runner can let a coding agent modify an isolated worktree, collect a result JSON, and call this evaluator to produce a pass/fail scorecard.

## Result JSON Shape

```json
{
  "evidence": ["moss-metric-contracts", "moss-lineage-evidence"],
  "checks": {
    "npm run test -- LedgerPnl": "passed",
    "npm run debt:audit": "passed",
    "npm run typecheck": "passed"
  },
  "business_gates": {
    "unit_consistency": true,
    "precision_and_rounding": true,
    "date_semantics": true,
    "null_zero_undefined_handling": true,
    "no_frontend_official_metric_recalculation": true
  },
  "page_gates": {
    "page_loads": true,
    "no_console_errors": true,
    "fallback_or_stale_state_visible_when_applicable": true
  },
  "changed_files": [
    "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx",
    "frontend/src/test/LedgerPnlPage.test.tsx"
  ]
}
```

## Score A Result

```bash
python scripts/agent_eval/validate_task.py \
  --task scripts/agent_eval/tasks/ledger_pnl_unit_mismatch_001.json \
  --result .codex-tmp/agent-result.json
```

Exit code `0` means the task passes. Exit code `1` means the scorecard failed and can be sent back to Polar as a low-reward rollout.

