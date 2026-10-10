---
name: moss-lineage-break-trace
description: "【MOSS血缘断点追踪】用于API结果、页面值、黄金样本、来源行、报告日期或页面契约无法核对时追根因。"
---

# MOSS Lineage Break Trace

Use this skill to root-cause mismatches instead of patching symptoms. It adapts GL break tracing patterns to MOSS source lineage and page verification.

## Break Buckets

Classify the mismatch before fixing it:

| Bucket | Typical Signal |
|---|---|
| Source-date break | requested date, resolved date, trade date, natural date, or fallback date differs |
| Unit break | yuan / ten-thousand yuan / hundred-million yuan / percent / bp mismatch |
| Grain break | row-level value compared to aggregated value, wrong grouping, duplicate rows |
| Rule break | wrong formula, rule version, cache version, or formal/scenario mix |
| Mapping break | product/category/security/account maps to a different canonical key |
| Null-state break | null, 0, undefined, NaN, or missing row semantics differ |
| Presentation break | backend value correct, adapter/formatter/component changes meaning |

## Trace Path

1. Capture the failing assertion or visible mismatch with exact value, date, metric ID, route, and endpoint.
2. Use authoritative contract and lineage evidence for the mismatch, reusing current evidence already gathered in this task.
3. Inspect the concrete data source and report dates with read-only catalog queries or existing tests when needed to locate the divergence.
4. Walk the implementation path from repository/service/core calculation through API schema to frontend adapter and component.
5. Identify the first layer where expected and actual diverge.
6. Fix that layer only; do not compensate downstream unless the downstream layer caused the break.
7. Add a regression test at the layer where the divergence first appeared.

## Root Cause Statement

A useful form is:

`<layer> produced/displayed <wrong value/state> because <specific evidence-backed cause>.`

Include the evidence-backed cause and any residual risk in the repository's completion report; do not add a second report for this skill.
