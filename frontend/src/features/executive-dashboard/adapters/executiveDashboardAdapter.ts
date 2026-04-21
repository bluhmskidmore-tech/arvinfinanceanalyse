/**
 * Executive Dashboard adapter.
 *
 * Consumes raw ``ApiEnvelope`` payloads from ``getOverview`` / ``getPnlAttribution``
 * and produces typed view-models plus a single ``DataSectionState`` per card.
 *
 * Components downstream MUST NOT read raw envelopes; they read this adapter's
 * view-models only. Selectors (W2.4) carve view-models into per-component
 * sub-models for cross-component raw-number consistency tests.
 *
 * Design reference: ``docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md`` § 5.2 / § 5.3.
 */
import type {
  ApiEnvelope,
  Numeric,
  OverviewPayload,
  PnlAttributionPayload,
  ResultMeta,
  VerdictPayload,
} from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import type { Tone } from "../../../utils/tone";
import { sanitizeMetricDetail, sanitizeMetricLabel } from "../lib/sanitizeMetricCopy";

type MetricTone = "positive" | "neutral" | "warning" | "negative";

export type DashboardOverviewMetricVM = {
  id: string;
  label: string;
  value: Numeric;
  delta: Numeric;
  tone: MetricTone;
  detail: string;
  history: number[] | null;
};

export type DashboardOverviewVM = {
  title: string;
  metrics: DashboardOverviewMetricVM[];
};

export type DashboardPnlSegmentVM = {
  id: string;
  label: string;
  amount: Numeric;
  tone: Tone;
};

export type DashboardPnlAttributionVM = {
  title: string;
  total: Numeric;
  segments: DashboardPnlSegmentVM[];
};

export type DashboardAdapterInput = {
  overviewEnv: ApiEnvelope<OverviewPayload> | undefined;
  attributionEnv: ApiEnvelope<PnlAttributionPayload> | undefined;
  overviewLoading: boolean;
  overviewError: boolean;
  attributionLoading: boolean;
  attributionError: boolean;
  verdictPayload?: VerdictPayload | null;
};

export type DashboardAdapterOutput = {
  overview: {
    vm: DashboardOverviewVM | null;
    state: DataSectionState;
    meta: ResultMeta | null;
  };
  attribution: {
    vm: DashboardPnlAttributionVM | null;
    state: DataSectionState;
    meta: ResultMeta | null;
  };
  verdict: VerdictPayload | null;
};

export function adaptDashboard(input: DashboardAdapterInput): DashboardAdapterOutput {
  const overviewState = deriveStateFromEnvelope({
    env: input.overviewEnv,
    isLoading: input.overviewLoading,
    isError: input.overviewError,
    emptyIf: (result) => !result || !Array.isArray(result.metrics) || result.metrics.length === 0,
  });

  const attributionState = deriveStateFromEnvelope({
    env: input.attributionEnv,
    isLoading: input.attributionLoading,
    isError: input.attributionError,
    emptyIf: (result) => !result || !Array.isArray(result.segments) || result.segments.length === 0,
  });

  const overviewVM = buildOverviewVM(input.overviewEnv?.result);
  const attributionVM = buildAttributionVM(input.attributionEnv?.result);

  return {
    overview: {
      vm: overviewVM,
      state: overviewState,
      meta: input.overviewEnv?.result_meta ?? null,
    },
    attribution: {
      vm: attributionVM,
      state: attributionState,
      meta: input.attributionEnv?.result_meta ?? null,
    },
    verdict: sanitizeVerdict(input.verdictPayload ?? null),
  };
}

/**
 * 把后端 verdict 中的 reasons 也过一遍显示净化器，
 * 避免 hero strip 已经净化、但 verdict 仍然漏出表名/字段名/英文术语。
 */
function sanitizeVerdict(verdict: VerdictPayload | null): VerdictPayload | null {
  if (!verdict) return null;
  return {
    ...verdict,
    reasons: verdict.reasons.map((r) => ({
      ...r,
      label: sanitizeMetricLabel(r.label),
      detail: sanitizeMetricDetail(r.detail),
    })),
  };
}

function buildOverviewVM(result: OverviewPayload | undefined): DashboardOverviewVM | null {
  if (!result) return null;
  return {
    title: result.title,
    metrics: result.metrics.map((m) => ({
      id: m.id,
      label: m.label,
      value: m.value,
      delta: m.delta,
      tone: (m.tone as MetricTone) ?? "neutral",
      detail: m.detail,
      history: m.history ?? null,
    })),
  };
}

function buildAttributionVM(result: PnlAttributionPayload | undefined): DashboardPnlAttributionVM | null {
  if (!result) return null;
  return {
    title: result.title,
    total: result.total,
    segments: result.segments.map((s) => ({
      id: s.id,
      label: s.label,
      amount: s.amount,
      tone: coerceTone(s.tone),
    })),
  };
}

function coerceTone(raw: string): Tone {
  if (raw === "positive" || raw === "negative" || raw === "neutral" || raw === "warning") {
    return raw;
  }
  return "neutral";
}

function deriveStateFromEnvelope<T extends { metrics?: unknown; segments?: unknown }>(opts: {
  env: { result_meta: ResultMeta; result: T } | undefined;
  isLoading: boolean;
  isError: boolean;
  emptyIf: (result: T | undefined) => boolean;
}): DataSectionState {
  if (opts.isLoading) return { kind: "loading" };
  if (opts.isError) return { kind: "error" };
  if (!opts.env) return { kind: "loading" };

  const meta = opts.env.result_meta;
  const effectiveDate = resolveEffectiveDate(meta);
  const requestedDate = resolveRequestedDate(meta);

  if (typeof meta.source_version === "string" && meta.source_version.includes("explicit_miss")) {
    return { kind: "explicit_miss", requested_date: requestedDate, details: describeMetaDetails(meta) };
  }

  if (meta.vendor_status === "vendor_unavailable") {
    return { kind: "vendor_unavailable", details: describeMetaDetails(meta) };
  }

  if (meta.fallback_mode === "latest_snapshot") {
    return { kind: "fallback", effective_date: effectiveDate, details: describeMetaDetails(meta) };
  }

  if (meta.vendor_status === "vendor_stale" || meta.quality_flag === "stale") {
    return { kind: "stale", effective_date: effectiveDate, details: describeMetaDetails(meta) };
  }

  if (opts.emptyIf(opts.env.result)) {
    return { kind: "empty" };
  }

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
