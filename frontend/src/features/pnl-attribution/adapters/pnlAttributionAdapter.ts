/**
 * PnL Attribution workbench adapter skeleton.
 *
 * This file provides the shared state-derivation helper
 * ``derivePnlDataSectionState`` used by all tab-level adapters (W3.4 will
 * add the tab-specific sub-adapter functions that map ApiEnvelope to typed
 * view-models). Components MUST NOT read ResultMeta directly; they consume
 * the ``DataSectionState`` produced here.
 *
 * Design reference: ``docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md`` § 5.2.
 */
import type { ResultMeta } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";

export type PnlStateDerivationInput = {
  meta: ResultMeta | null;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
  isEmpty: boolean;
};

/**
 * Map raw query flags + ResultMeta into a single DataSectionState.
 *
 * Priority order:
 *   loading -> error -> (no meta yet? → loading) -> vendor_unavailable ->
 *   explicit_miss -> fallback -> stale -> empty -> ok
 */
export function derivePnlDataSectionState(
  input: PnlStateDerivationInput,
): DataSectionState {
  if (input.isLoading) return { kind: "loading" };
  if (input.isError) {
    return input.errorMessage
      ? { kind: "error", message: input.errorMessage }
      : { kind: "error" };
  }

  if (!input.meta) return { kind: "loading" };

  const meta = input.meta;
  const requestedDate = resolveRequestedDate(meta);
  const effectiveDate = resolveEffectiveDate(meta);
  const details = describeMetaDetails(meta);

  if (meta.vendor_status === "vendor_unavailable") {
    return { kind: "vendor_unavailable", details };
  }

  if (typeof meta.source_version === "string" && meta.source_version.includes("explicit_miss")) {
    return { kind: "explicit_miss", requested_date: requestedDate, details };
  }

  if (meta.fallback_mode === "latest_snapshot") {
    return { kind: "fallback", effective_date: effectiveDate, details };
  }

  if (meta.vendor_status === "vendor_stale" || meta.quality_flag === "stale") {
    return { kind: "stale", effective_date: effectiveDate, details };
  }

  if (input.isEmpty) return { kind: "empty" };

  return { kind: "ok" };
}

function resolveEffectiveDate(meta: ResultMeta): string | undefined {
  const reportDate = meta.filters_applied?.report_date;
  if (typeof reportDate === "string" && reportDate.trim()) {
    return reportDate.trim();
  }

  const effective = meta.filters_applied?.effective_report_dates;
  if (effective && typeof effective === "object" && !Array.isArray(effective)) {
    const values = Object.values(effective)
      .filter((v): v is string => typeof v === "string" && v.trim().length > 0)
      .map((v) => v.trim());
    const unique = Array.from(new Set(values));
    if (unique.length === 0) return undefined;
    if (unique.length === 1) return unique[0];
    return "mixed";
  }

  return undefined;
}

function resolveRequestedDate(meta: ResultMeta): string | undefined {
  const requested = meta.filters_applied?.requested_report_date ?? meta.filters_applied?.report_date;
  return typeof requested === "string" && requested.trim() ? requested.trim() : undefined;
}

function describeMetaDetails(meta: ResultMeta): string {
  const parts: string[] = [];
  if (meta.quality_flag && meta.quality_flag !== "ok") parts.push(`quality=${meta.quality_flag}`);
  if (meta.vendor_status && meta.vendor_status !== "ok") parts.push(`vendor=${meta.vendor_status}`);
  if (meta.fallback_mode && meta.fallback_mode !== "none") parts.push(`fallback=${meta.fallback_mode}`);
  if (meta.generated_at) parts.push(`generated_at=${meta.generated_at}`);
  return parts.join(" · ");
}
