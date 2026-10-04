---
name: moss-metric-audit
description: "【MOSS指标审计】用于修改、审查或调试MOSS业务指标、指标字典、适配器、选择器和正式金融计算。"
---

# MOSS Metric Audit

Use this skill to keep MOSS metric work tied to authoritative definitions, source evidence, and verification. It adapts financial-model audit discipline to MOSS.

## Workflow

1. State the page or workflow being fixed and the first files to inspect.
2. Verify the metric authority before editing, selecting the evidence needed for the affected definition, source, or code path:
   - Prefer `moss-metric-contracts` for page contracts, metric definitions, units, rules, and golden samples.
   - Use `moss-lineage-evidence` for source version, rule/cache lineage, fallback/stale status, and governance evidence.
   - Use `moss-data-catalog` for DuckDB tables, columns, dates, and available source facts.
   - Use `gitnexus` for symbol/call-path impact as required by the repository rules.
   Reuse current evidence already gathered for this task; the tools above are not a mandatory bundle.
3. Trace the full display path:
   `API response -> adapter/transformer -> state/selector/computed model -> component -> chart/table`.
4. Check the metric hazards relevant to the affected path:
   units, precision, rounding, Decimal/string/float conversion, null vs 0, currency, trade date vs report date, fallback date, stale mock data, duplicate frontend calculations, and inconsistent filters.
5. Make the smallest code change at the correct layer:
   - formal finance math belongs in `backend/app/core_finance/`
   - API routes stay thin
   - frontend consumes and formats; it does not invent formal metrics
6. Add or update the smallest useful test around the changed formatter, adapter, selector, service, or core calculation.
7. Run narrow verification first, then widen only when the change crosses shared boundaries.

## Output Discipline

Use the repository's completion report once and include any remaining metric uncertainty. If metric meaning, unit, date, or lineage is ambiguous, stop the dependent implementation path and report the ambiguity with evidence instead of guessing.
