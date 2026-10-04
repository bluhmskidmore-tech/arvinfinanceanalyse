---
name: moss-agent-loops
description: "Use when planning or running repeated agent work in MOSS with a cycle, schedule, budget, or stop condition. Covers goal-based, time-based, proactive, and verification loops; ordinary one-pass reviews and edits do not need this skill."
---

# MOSS Agent Loops

This skill turns looped agent work into a bounded MOSS operating pattern. It is for agent execution loops, not the stock strategy closed-loop business workflow.

## Required Setup

Reuse the task's established scope and acceptance criteria. Before entering a loop, state its trigger, stop criteria, and cycle or time budget only if they have not already been established.

`goal-based` describes the workflow; it does not authorize creating a host goal. Create a goal only when the user or host instructions explicitly request one. Existing goal lifecycle, pause, blocker, and budget rules come from the host and take precedence over the defaults below. Scheduling and external actions still require the authority supplied by the task.

## Loop Classes

| Class | Use For | Default Stop |
| --- | --- | --- |
| `turn-based` | One explicitly requested inspect/edit/verify cycle. | The cycle's acceptance criterion is met. |
| `goal-based` | Page/workflow closure, bug fix, refactor, or implementation with measurable acceptance. | Acceptance criteria pass; unresolved blockers and budget limits follow host lifecycle rules. |
| `time-based` | Scheduled checks, CI/watch tasks, readiness snapshots, data freshness monitors. | Time window expires, configured check passes, or alert/report is emitted. |
| `proactive` | Event-triggered triage such as stale evidence, failed debt audit, MCP contract change, or open review. | Report or bounded fix is produced; write actions require explicit authority. |

## MOSS Verification Gates

Follow the repository and affected path's verification rules. Select evidence for the actual risk: metric definitions need contract evidence; source/date discrepancies need lineage or catalog evidence; changed symbols need impact analysis. Touching an API or page does not require querying every evidence server.

Reuse current contract, lineage, impact, and verification evidence across cycles and applicable skills. Refresh it when the relevant source, code, scope, or assumptions change, or a failure makes it unreliable. If required evidence is unavailable, report the local substitute and remaining uncertainty; do not guess business meaning.

## Execution Loop

Each cycle is:

1. Inspect the minimum context needed for the current slice.
2. If editing, make the smallest change at the correct layer.
3. Run the proof command for that slice.
4. Read the output and decide:
   - pass: continue to the next acceptance item or stop;
   - fail with a clear local cause: fix and run one more cycle;
   - repeated failure: use the evidence to change approach, delegate a bounded investigation, or report the concrete blocker; do not repeat an unchanged attempt;
   - high/critical blast radius: warn, inspect the affected callers, and select proportionate verification; the risk label alone is not a stop condition;
   - missing authority or essential evidence, or an action outside the task's authorization: pause the dependent action and surface the specific requirement. Continue independent authorized work.

## Budget Defaults

- `turn-based`: 1 cycle, no child agents unless the answer depends on parallel inspection.
- `goal-based`: review the approach after 3 repair cycles per acceptance item; use bounded independent delegation when useful. User and host budgets govern continuation.
- `time-based`: explicit interval, end time, and alert/report destination; read-only unless the user explicitly authorized writes.
- `proactive`: read-only triage first; create a bounded follow-up or fix only when the repo rules and user request authorize it.

## Reporting

Use the repository's completion report once. Add the loop outcome or unresolved blocker only when it helps explain the result; do not repeat the same evidence for every skill used.
