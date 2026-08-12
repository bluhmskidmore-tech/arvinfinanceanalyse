# MOSS Agent Evaluation

A MOSS-Agent-Bench scaffold for scoring scoped development tasks. It does not change the MOSS frontend or backend runtime.

The scorecard weights mirror `AGENTS.md`: business correctness 40, page closure 20, verification 20, diff discipline 20, with a pass threshold of 90.

## Measure, Do Not Ask

`reward.py` scores a result mapping. That mapping must be produced by `collect.py` from observed
repository state, not supplied by the agent being evaluated:

| Field | Measured from |
| --- | --- |
| `changed_files` | `git diff --name-only <base or HEAD>` plus `git ls-files --others --exclude-standard`; diffing against HEAD by default keeps staged-but-uncommitted edits visible, and any git failure aborts the collection instead of reading as "nothing changed" |
| `checks` | real exit code of each command in `task.checks` |
| `business_gates` / `page_gates` | real exit code of the command in `task.gate_probes` |
| `evidence` | the artifact in `task.evidence_probes` parses as a JSON object with a non-empty string `source` |

**A gate with no declared probe is scored as failed.** An unmeasurable gate must not be assumed to
pass, otherwise the score only reflects whether the reporter was cooperative. Record why a probe is
missing in `gate_probe_gaps`; the collector echoes those reasons in the measurement block so the
coverage gap stays visible instead of silently reading as a low score.

**Evidence must satisfy a minimal schema, not merely exist.** An artifact counts only when it is a
non-empty file parsing to a JSON object whose `source` is a non-empty string naming the MCP server
or query tool it came from — the anchor for a future call-receipt check. Anything weaker is recorded
in `measurement.evidence_artifacts` as `missing` / `empty` / `invalid_json` / `missing_source` and
does not satisfy the probe, so a placeholder file cannot buy the verification score.

## Run A Task

```bash
python scripts/agent_eval/validate_task.py \
  --task scripts/agent_eval/tasks/ledger_pnl_unit_mismatch_001.json \
  --measure \
  --base-ref origin/main \
  --result-out .codex-tmp/agent-eval/result.json \
  --out .codex-tmp/agent-eval/scorecard.json
```

Exit code `0` means the task passes, `1` means the scorecard failed, `2` means the input or the
measurement itself was invalid.

To score a result produced by a separate runner, pass `--result` instead of `--measure`, and add
`--require-measured` so a hand-written result is rejected.

For a one-command evaluation with archived artifacts (task snapshot, result, scorecard, summary),
use `python scripts/agent_eval/replay.py --task <task> --worktree <path> --base-ref <ref>` — see its
docstring for the recommended `git worktree` isolation. On Windows, `scripts/agent_eval/run.ps1`
wraps the CLI with interpreter discovery (uv, then `py -3.11`, then `MOSS_PYTHON`).

## PR Consumer

The `Agent Eval Replay` CI job (pull requests only) is the scorecard's first consumer:
`pr_replay.py` selects every task whose `allowed_scope` overlaps the PR diff, runs a replay
evaluation per task, and publishes one Markdown report to the step summary and a marker-updated PR
comment. The report is informational and never blocks a merge; hard failures are split into *real
failures* (a probe ran red) and *probe gaps* (fail-closed gates with no probe yet), and a *void*
verdict means the PR touches the scoring harness or a protected probe, which by design cannot be
scored by itself. The job goes red only when the orchestration itself breaks.

## Integrity

The scorecard is void, not merely low, when the run tampered with its own scoring rules. The
measurement carries an `integrity` block, and `validate_measured_result` raises when it is not
trusted:

- the task definition changed during the run — detected by `--task-digest` when the runner captures
  `compute_task_digest()` before the agent starts, otherwise by tracked-file diff
- a protected probe file changed during the run (tracked-file diff), which would let an agent neuter
  the very test a gate depends on
- any file under `scripts/agent_eval/` changed during the run — the harness always protects its own
  scoring code (`HARNESS_SELF_PATHS`), no task declaration needed

The protected probe list is auto-derived plus manual, deduplicated:

- **auto-derived** — `derive_probe_paths()` extracts explicit repo test-file paths from every
  `gate_probes` and `checks` command: tokens shaped like `tests/**.py`, `backend/tests/**.py`, or
  `frontend/src/test/**` (backslashes normalized to `/`, lowercased). A filter word such as the
  vitest name `LedgerPnlUnitContract` is not a path and derives nothing.
- **manual** — `probe_protected_paths` covers every dependency a command does not spell out as a
  path. Entries ending in `/` protect the whole directory prefix.

The effective union is recorded in `measurement.integrity.protected_paths`. Commands from which no
path could be derived are recorded in `measurement.integrity.underivable_probe_commands`, so the
coverage gap stays visible. A command that mixes an explicit path with a filter word counts as
derived; its non-path dependencies still need a manual declaration.

## Security boundary

Three hard rules; a run that breaks any of them produces a score that cannot be trusted:

1. The task JSON must be a reviewed, in-repo file. The collector executes `checks` and
   `gate_probes` commands with a shell, so an agent must never generate or modify the task
   definition it is evaluated against.
2. In rollout/automation scenarios the runner must pass `--task-digest`, captured with
   `compute_task_digest()` before the agent starts. Tracked-file diff only covers committed task
   files; an untracked task definition is invisible to it.
3. A probe whose command carries no derivable file path (listed in `underivable_probe_commands`)
   must have every file it depends on declared manually in `probe_protected_paths`; otherwise those
   files are unprotected against tampering.

## Task Fields

Required: `id`, `required_evidence`, `checks`, `business_gates`, `page_gates`, `allowed_scope`, `forbidden`.

Optional: `page`, `goal`, `gate_probes`, `evidence_probes`, `probe_protected_paths`, `gate_probe_gaps`, `metric_ids`.

Validation is strict where laxity would weaken scoring:

- `gate_probes` / `evidence_probes` keys must match declared gates and evidence, so a typo fails
  loudly instead of silently leaving a gate unmeasured.
- `allowed_scope` must be non-empty — an empty scope would disable out-of-scope detection.
- every `gate_probes` command must start with `python -m pytest ` or `npm --prefix frontend run `,
  so a probe cannot be an arbitrary script that fabricates a green gate.
- `metric_ids` binds the task to governed metric ids in `docs/metric_dictionary.md`;
  `tests/test_agent_eval_spec.py` asserts every shipped task's ids resolve against the dictionary.

## Current Coverage

`ledger_pnl_unit_mismatch_001` declares 8 gates and has probes for 4: unit consistency, precision
and rounding, and null/zero/undefined handling (three dedicated `frontend/src/test/LedgerPnl*Contract`
suites, each validated red-then-green), plus `no_frontend_official_metric_recalculation`
(`tests/test_no_finance_logic_in_frontend.py`). The remaining 4 are recorded in `gate_probe_gaps`
with the probe each one needs. That backlog is the point: the task honestly reports what is
verifiable today rather than accepting a self-declared pass.
