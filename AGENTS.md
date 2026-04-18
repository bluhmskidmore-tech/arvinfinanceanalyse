# AGENTS.md

## Current mission
This repository is a business system.
Current priority:
1. business metric correctness
2. page-level closure
3. traceability and validation
4. minimal, reviewable changes

Not current priority:
- backend platform refactor
- generic infrastructure abstraction
- framework beautification
- base-layer rebuild
- unrelated performance tuning

## Scope discipline
- Fix one page or one workflow at a time.
- Prefer the smallest effective change.
- Do not refactor unrelated modules.
- Do not introduce new abstractions unless they are required by the current task and reused immediately.
- If a metric definition is ambiguous, do not guess. Report the ambiguity with evidence.
- Business correctness is more important than architectural elegance.

## Frontend data verification rules
For every displayed metric, always trace:
API response -> adapter/transformer -> store/state -> selector/computed -> component -> chart/table

Always check:
- unit consistency: 元 / 万元 / 亿元 / % / bp
- precision and rounding
- Decimal / float / string serialization
- null vs 0 vs undefined vs NaN
- currency conversion
- trade date vs natural date
- daily vs month-end vs YTD
- as_of_date / fallback date / cached date
- stale mock data or hard-coded fallback values
- duplicate calculations in frontend
- inconsistent filters across cards / charts / tables

## UI and page rules
- Each page must answer one primary business question first.
- The first screen must make the main conclusion obvious.
- Explicitly surface:
  - no data
  - stale data
  - fallback date
  - loading failure
  - metric definition pending confirmation
- Do not add visual complexity unless it improves decision-making.

## Forbidden without explicit instruction
Do NOT proactively modify:
- database schema
- auth / permission framework
- queue / scheduler / cache base
- global SDK wrappers
- shared infra layers
- app-wide state architecture
- unrelated backend services

Unless there is direct evidence that one of them is the root cause of the current task.

## Work protocol
Before editing:
- state the page or workflow being fixed
- state the files to inspect first
- state what will NOT be touched

After editing:
- report the root cause
- list changed files
- report validation steps and results
- report remaining risks

## Validation
When changing business display logic, also add or update the smallest necessary tests for:
- formatter
- selector / computed
- adapter / transform

Always run the narrowest relevant checks available in this repo:
- lint
- typecheck
- targeted tests
- build

If a command cannot run, explain why instead of skipping silently.
