# Liability V1 Compatibility Gates

## Scope

This document defines the gate model for the 4 current liability V1 compatibility-seam interfaces:

1. `/api/risk/buckets`
2. `/api/analysis/yield_metrics`
3. `/api/analysis/liabilities/counterparty`
4. `/api/liabilities/monthly`

These endpoints are currently treated as `V1 compatibility seam` surfaces.
They are not governed `result_meta` surfaces and must not be used as formal truth sources.

## Gate split

Two gates apply to every compatibility-diff and replay task:

1. `compatibility seam gate`
2. `governed surface gate`

Both gates must be satisfied before a replay-driven change is accepted.

## Compatibility seam gate

### Purpose

This gate validates compatibility behavior against frozen V1 samples.
It is allowed to bind payload-level outward behavior only.

### Allowed binding scope

V1 samples may bind:

- payload shape
- field presence and absence
- list ordering when ordering is part of the outward contract
- null behavior
- display labels
- display-oriented units
- top-N truncation behavior

### Not allowed

V1 samples may not independently decide:

- formal-sensitive rate semantics
- basis selection
- formal/scenario/analytical meaning
- governed cache semantics
- whether a snapshot-derived field is semantically correct

### Fail conditions

The compatibility seam gate fails when any of the following is true:

- a frozen compatibility field is missing
- an unexpected field appears where the seam contract says it must not
- list ordering differs from a frozen compatibility sample where order is contractual
- display-unit conversion differs from the frozen compatibility rule
- a known implementation-defect remains unresolved after replay

## Governed surface gate

### Purpose

This gate prevents compatibility work from leaking into formal or governed semantics.

### Protected boundaries

The governed surface gate protects:

- `AGENTS.md` architecture direction
- `docs/data_contracts.md` snapshot versus formal fact boundary
- `docs/CACHE_SPEC.md` outward `basis / formal_use_allowed / scenario_flag / result_meta` ownership
- `docs/calc_rules.md` formal-sensitive rule ownership

### Fail conditions

The governed surface gate fails when any of the following is true:

- compatibility work treats a snapshot-derived seam field as formal truth
- a replay fix adds or implies governed `result_meta` semantics without explicit contract work
- formal-sensitive behavior is changed only to match V1, without authority-matrix support
- formal finance logic is added to `api/`, `services/`, or frontend consumers to satisfy replay
- documentation or tests imply these seam endpoints are governed surfaces
- `/api/liabilities/monthly` semantic comparison proceeds before the monthly basis gate is resolved

## Monthly basis gate

`/api/liabilities/monthly` has an extra prerequisite gate.

Current seam decision:

- `basis = observed`

Other known basis families retained for authority-matrix review:

- `locf`
- `calendar_zero`

Interpretation:

- monthly averages are compared against the count of actually observed days
- missing calendar days are not automatically LOCF-filled
- missing calendar days are not treated as zero-filled

Implications:

- compatibility replay is allowed
- semantic review may proceed under the observed-basis assumption
- amount and rate mismatches must still respect the authority matrix and may not be labeled `implementation-defect` from V1 alone

## Diff classification output

Every replay difference must be routed into one of these classes:

- `implementation-defect`
- `data-issue`
- `historical-compatibility`
- `pending-confirmation`
- `architecture-invalid`
- `transitional-seam`

## Review order

When a compatibility replay finds a difference, review order is:

1. Check the field in the authority matrix.
2. Decide whether the field is formal-sensitive.
3. Run the compatibility seam gate.
4. Run the governed surface gate.
5. If the field is monthly-semantic, check the monthly basis gate.
6. Only then classify the difference.

## Required companion artifacts

This gate document is intended to be used together with:

- [liability_v1_field_authority_matrix.md](F:/MOSS-V3/docs/liability_v1_field_authority_matrix.md)
- [liability_v1_harness.py](F:/MOSS-V3/tests/liability_v1_harness.py)
- [test_liability_v1_field_mapping.py](F:/MOSS-V3/tests/test_liability_v1_field_mapping.py)
- [test_liability_v1_sample_replay.py](F:/MOSS-V3/tests/test_liability_v1_sample_replay.py)
