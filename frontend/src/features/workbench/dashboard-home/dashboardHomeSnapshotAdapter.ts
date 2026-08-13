import type {
  ApiEnvelope,
  HomeSnapshotPayload,
  Numeric,
  OverviewPayload,
  PnlAttributionPayload,
  ResultMeta,
  VerdictPayload,
  VerdictReason,
  VerdictSuggestion,
} from "../../../api/contracts";
import { isReservedBoundaryHttpMessage } from "../../../api/httpResponseError";
import type { DataSectionState } from "../../../components/DataSection.types";
import type { Tone } from "../../../utils/tone";
import {
  sanitizeMetricDetail,
  sanitizeMetricLabel,
} from "./lib/sanitizeMetricCopy";
import type { HomeProductCategoryHeadline } from "./dashboardHomeFirstScreenTypes";

import { EM_DASH } from "../../../utils/format";
type HomeSnapshotMetricTone = "positive" | "neutral" | "warning" | "negative";

export type HomeSnapshotOverviewMetricVM = {
  id: string;
  label: string;
  caliberLabel: string | null;
  value: Numeric;
  delta: Numeric;
  tone: HomeSnapshotMetricTone;
  detail: string;
  history: number[] | null;
};

export type HomeSnapshotOverviewVM = {
  title: string;
  metrics: HomeSnapshotOverviewMetricVM[];
};

export type HomeSnapshotPnlSegmentVM = {
  id: string;
  label: string;
  amount: Numeric;
  tone: Tone;
};

export type HomeSnapshotPnlAttributionVM = {
  title: string;
  total: Numeric;
  segments: HomeSnapshotPnlSegmentVM[];
};

export type HomeSnapshotAdapterOutput = {
  overview: {
    vm: HomeSnapshotOverviewVM | null;
    state: DataSectionState;
    meta: ResultMeta | null;
  };
  attribution: {
    vm: HomeSnapshotPnlAttributionVM | null;
    state: DataSectionState;
    meta: ResultMeta | null;
  };
  verdict: VerdictPayload | null;
  domainsEffectiveDate: Record<string, string>;
  domainsMissing: readonly string[];
  productCategoryHeadline: HomeProductCategoryHeadline;
  datesDiverged: boolean;
};

export type HomeSnapshotAdapterInput = {
  snapshot: ApiEnvelope<HomeSnapshotPayload> | null;
  isLoading: boolean;
  isError: boolean;
  snapshotFetchErrorDetail?: string;
};

function coerceTone(raw: string): Tone {
  if (raw === "positive" || raw === "negative" || raw === "neutral" || raw === "warning") {
    return raw;
  }
  return "neutral";
}

function coerceMetricTone(raw: string): HomeSnapshotMetricTone {
  if (raw === "positive" || raw === "negative" || raw === "neutral" || raw === "warning") {
    return raw;
  }
  return "neutral";
}

function coerceVerdictText(value: unknown, fallback: string): string {
  if (value == null) {
    return fallback;
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (typeof value === "bigint") {
    return value.toString();
  }
  if (typeof value === "symbol") {
    return fallback;
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return fallback;
    }
  }
  try {
    return String(value);
  } catch {
    return fallback;
  }
}

function coerceVerdictLink(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function coerceVerdictTone(value: unknown): VerdictPayload["tone"] {
  if (value === "positive" || value === "neutral" || value === "warning" || value === "negative") {
    return value;
  }
  return "neutral";
}

function sanitizeVerdict(verdict: VerdictPayload | null | undefined): VerdictPayload | null {
  if (!verdict || typeof verdict !== "object") {
    return null;
  }

  const reasonsRaw = Array.isArray(verdict.reasons) ? verdict.reasons : [];
  const suggestionsRaw = Array.isArray(verdict.suggestions) ? verdict.suggestions : [];

  return {
    conclusion: coerceVerdictText(verdict.conclusion, ""),
    tone: coerceVerdictTone(verdict.tone),
    reasons: reasonsRaw.map((raw) => {
      const reason = raw && typeof raw === "object" ? (raw as Partial<VerdictReason>) : {};
      return {
        label: sanitizeMetricLabel(coerceVerdictText(reason.label, "")),
        value: coerceVerdictText(reason.value, "-"),
        detail: sanitizeMetricDetail(coerceVerdictText(reason.detail, "")),
        tone: coerceVerdictTone(reason.tone),
      };
    }),
    suggestions: suggestionsRaw.map((raw) => {
      const suggestion =
        raw && typeof raw === "object" ? (raw as Partial<VerdictSuggestion>) : {};
      return {
        text: coerceVerdictText(suggestion.text, ""),
        link: coerceVerdictLink(suggestion.link),
      };
    }),
  };
}

function buildOverviewVM(result: OverviewPayload | undefined): HomeSnapshotOverviewVM | null {
  if (!result) {
    return null;
  }
  return {
    title: result.title,
    metrics: result.metrics.map((metric) => ({
      id: metric.id,
      label: metric.label,
      caliberLabel: metric.caliber_label ?? null,
      value: metric.value,
      delta: metric.delta,
      tone: coerceMetricTone(metric.tone),
      detail: metric.detail,
      history: metric.history ?? null,
    })),
  };
}

function buildAttributionVM(
  result: PnlAttributionPayload | undefined,
): HomeSnapshotPnlAttributionVM | null {
  if (!result) {
    return null;
  }
  return {
    title: result.title,
    total: result.total,
    segments: result.segments.map((segment) => ({
      id: segment.id,
      label: segment.label,
      amount: segment.amount,
      tone: coerceTone(segment.tone),
    })),
  };
}

function reservedFetchSecondaryMessage(raw?: string): string | undefined {
  if (!raw?.trim() || !isReservedBoundaryHttpMessage(raw)) {
    return undefined;
  }
  return "该接口在当前发布边界中为保留面，本轮不可用；并非通用网络错误。";
}

function resolveEffectiveDate(meta: ResultMeta): string | undefined {
  const reportDate = meta.filters_applied?.report_date;
  if (typeof reportDate === "string" && reportDate.trim()) {
    return reportDate.trim();
  }

  const effective = meta.filters_applied?.effective_report_dates;
  if (effective && typeof effective === "object" && !Array.isArray(effective)) {
    const values = Object.values(effective)
      .filter((value): value is string => typeof value === "string" && value.trim().length > 0)
      .map((value) => value.trim());
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
  if (meta.quality_flag && meta.quality_flag !== "ok") {
    parts.push(`质量=${meta.quality_flag}`);
  }
  if (meta.vendor_status && meta.vendor_status !== "ok") {
    parts.push(`供应商=${meta.vendor_status}`);
  }
  if (meta.fallback_mode && meta.fallback_mode !== "none") {
    parts.push(`降级=${meta.fallback_mode}`);
  }
  if (meta.generated_at) {
    parts.push(`生成时间=${meta.generated_at}`);
  }
  return parts.join(" · ");
}

function deriveStateFromSnapshot<T>(opts: {
  result: T | undefined;
  meta: ResultMeta | null;
  isLoading: boolean;
  isError: boolean;
  fetchErrorDetail?: string;
  emptyIf: (result: T | undefined) => boolean;
}): DataSectionState {
  if (opts.isLoading) return { kind: "loading" };
  if (opts.isError) {
    const secondary = reservedFetchSecondaryMessage(opts.fetchErrorDetail);
    return secondary ? { kind: "error", message: secondary } : { kind: "error" };
  }
  if (!opts.meta) return { kind: "loading" };

  const effectiveDate = resolveEffectiveDate(opts.meta);
  const requestedDate = resolveRequestedDate(opts.meta);

  if (
    typeof opts.meta.source_version === "string" &&
    opts.meta.source_version.includes("explicit_miss")
  ) {
    return {
      kind: "explicit_miss",
      requested_date: requestedDate,
      details: describeMetaDetails(opts.meta),
    };
  }
  if (opts.meta.vendor_status === "vendor_unavailable") {
    return { kind: "vendor_unavailable", details: describeMetaDetails(opts.meta) };
  }
  if (opts.meta.fallback_mode === "latest_snapshot") {
    return {
      kind: "fallback",
      effective_date: effectiveDate,
      details: describeMetaDetails(opts.meta),
    };
  }
  if (opts.meta.vendor_status === "vendor_stale" || opts.meta.quality_flag === "stale") {
    return {
      kind: "stale",
      effective_date: effectiveDate,
      details: describeMetaDetails(opts.meta),
    };
  }
  if (opts.emptyIf(opts.result)) {
    return { kind: "empty" };
  }
  return { kind: "ok" };
}

function datesDiverged(domains: Record<string, string>): boolean {
  const uniqueDates = new Set(
    Object.values(domains).filter((value) => typeof value === "string" && value.trim()),
  );
  return uniqueDates.size > 1;
}

const PRODUCT_CATEGORY_GAP = EM_DASH;

function isGovernedNumeric(value: Numeric | null | undefined): boolean {
  return value?.raw != null && Number.isFinite(value.raw);
}

function governedDisplay(value: Numeric | null | undefined): string {
  if (!isGovernedNumeric(value)) {
    return PRODUCT_CATEGORY_GAP;
  }
  const display = value?.display?.trim();
  return display && display !== "--" && display !== PRODUCT_CATEGORY_GAP
    ? display
    : PRODUCT_CATEGORY_GAP;
}

function governedDetail(value: string | null | undefined): string {
  return value?.trim() || "对应快照字段未下发";
}

function productCategoryState(args: {
  hasAnyPayload: boolean;
  isComplete: boolean;
  meta: ResultMeta | null;
  isLoading: boolean;
  isError: boolean;
}): HomeProductCategoryHeadline["state"] {
  if (args.isLoading) return "loading";
  if (args.isError) return "error";
  if (!args.hasAnyPayload) return "empty";
  if (!args.isComplete) return "partial";
  if (
    args.meta?.quality_flag === "stale" ||
    args.meta?.vendor_status === "vendor_stale"
  ) {
    return "stale";
  }
  return "ready";
}

function buildProductCategoryHeadline(
  result: HomeSnapshotPayload | undefined,
  input: HomeSnapshotAdapterInput,
  meta: ResultMeta | null,
): HomeProductCategoryHeadline {
  const ytd = result?.product_category_ytd ?? null;
  const monthly = result?.product_category_monthly ?? null;
  const hasAnyPayload = Boolean(ytd || monthly);
  const governedValues = [
    ytd?.summary_pnl,
    ytd?.operating_income,
    ytd?.intermediate_business_income,
    monthly?.monthly_income,
  ];
  const isComplete = Boolean(
    ytd && monthly && governedValues.every((value) => isGovernedNumeric(value)),
  );
  const metrics: HomeProductCategoryHeadline["metrics"] = hasAnyPayload
    ? [
        { id: "ytd-summary-pnl", label: "年度汇总损益", value: governedDisplay(ytd?.summary_pnl), detail: governedDetail(ytd?.summary_pnl_detail) },
        { id: "ytd-operating-income", label: "年度营业收入", value: governedDisplay(ytd?.operating_income), detail: governedDetail(ytd?.operating_income_detail) },
        { id: "ytd-intermediate-business-income", label: "年度中间业务收入", value: governedDisplay(ytd?.intermediate_business_income), detail: governedDetail(ytd?.intermediate_business_income_detail) },
        { id: "monthly-income", label: "本月收入", value: governedDisplay(monthly?.monthly_income), detail: governedDetail(monthly?.monthly_income_detail) },
      ]
    : [];

  return {
    state: productCategoryState({
      hasAnyPayload,
      isComplete,
      meta,
      isLoading: input.isLoading,
      isError: input.isError,
    }),
    metrics,
  };
}

export function adaptHomeSnapshotForFirstScreen(
  input: HomeSnapshotAdapterInput,
): HomeSnapshotAdapterOutput {
  const result = input.snapshot?.result;
  const meta = input.snapshot?.result_meta ?? null;
  const overview = result?.overview;
  const attribution = result?.attribution;
  const domainsEffectiveDate = result?.domains_effective_date ?? {};
  const domainsMissing = Array.isArray(result?.domains_missing) ? result.domains_missing : [];
  const productCategoryHeadline = buildProductCategoryHeadline(result, input, meta);

  return {
    overview: {
      vm: buildOverviewVM(overview),
      state: deriveStateFromSnapshot({
        result: overview,
        meta,
        isLoading: input.isLoading,
        isError: input.isError,
        fetchErrorDetail: input.snapshotFetchErrorDetail,
        emptyIf: (payload) =>
          !payload || !Array.isArray(payload.metrics) || payload.metrics.length === 0,
      }),
      meta,
    },
    attribution: {
      vm: buildAttributionVM(attribution),
      state: deriveStateFromSnapshot({
        result: attribution,
        meta,
        isLoading: input.isLoading,
        isError: input.isError,
        fetchErrorDetail: input.snapshotFetchErrorDetail,
        emptyIf: (payload) =>
          !payload || !Array.isArray(payload.segments) || payload.segments.length === 0,
      }),
      meta,
    },
    verdict: sanitizeVerdict(result?.verdict),
    domainsEffectiveDate,
    domainsMissing,
    productCategoryHeadline,
    datesDiverged: datesDiverged(domainsEffectiveDate),
  };
}
