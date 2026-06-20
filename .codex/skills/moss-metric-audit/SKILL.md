---
name: moss-metric-audit
description: Use when changing, reviewing, or debugging MOSS business metrics, metric dictionaries, adapters, selectors, formal finance calculations, golden samples, or displayed metric values.
---

# MOSS Metric Audit

Use this skill to keep MOSS metric work tied to authoritative definitions, source evidence, and verification. It adapts financial-model audit discipline to MOSS.

## Workflow

1. State the page or workflow being fixed and the first files to inspect.
2. Verify the metric authority before editing:
   - Prefer `moss-metric-contracts` for page contracts, metric definitions, units, rules, and golden samples.
   - Use `moss-lineage-evidence` for source version, rule/cache lineage, fallback/stale status, and governance evidence.
   - Use `moss-data-catalog` for DuckDB tables, columns, dates, and available source facts.
   - Use `gitnexus` for symbol/call-path impact when touching shared code.
3. Trace the full display path:
   `API response -> adapter/transformer -> state/selector/computed model -> component -> chart/table`.
4. Check metric hazards explicitly:
   units, precision, rounding, Decimal/string/float conversion, null vs 0, currency, trade date vs report date, fallback date, stale mock data, duplicate frontend calculations, and inconsistent filters.
5. Make the smallest code change at the correct layer:
   - formal finance math belongs in `backend/app/core_finance/`
   - API routes stay thin
   - frontend consumes and formats; it does not invent formal metrics
6. Add or update the smallest useful test around the changed formatter, adapter, selector, service, or core calculation.
7. Run narrow verification first, then widen only when the change crosses shared boundaries.

## Output Discipline

Report root cause, changed files, verification results, and remaining risk. If metric meaning, unit, date, or lineage is ambiguous, stop the implementation path and report the ambiguity with evidence instead of guessing.
