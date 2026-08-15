/**
 * Liability and ADB client slice.
 * Imported by client.ts for ApiClient composition.
 */
import type {
  AdbAccountingBasisDailyAvgTrendItem,
  AdbComparisonResponse,
  AdbConcentrationBlock,
  AdbConcentrationSide,
  AdbCoveragePayload,
  AdbInsightDimension,
  AdbInsightItem,
  AdbInsightSeverity,
  AdbInsightsResponse,
  AdbInsightsWindow,
  AdbInsightsWindowReason,
  AdbMonthEndEffect,
  AdbMonthlyResponse,
  AdbNimAttribution,
  AdbNimSideAttribution,
  AdbNimUnavailableReason,
  AdbPayload,
  AdbScaleAttribution,
  AdbScaleContributionRow,
  AdbScaleSideTotals,
  AdbVolatilityBlock,
  AdbVolatilitySeries,
  ApiEnvelope,
  BalancePageCalibration,
  CockpitWarningsPayload,
  ContributionSplitPayload,
  ResultMeta,
  YieldByPeriodPayload,
} from "./contracts";
import type {
  LiabilitiesMonthlyPayload,
  LiabilityCounterpartyPayload,
  LiabilityKnowledgeBriefPayload,
  LiabilityRiskBucketsPayload,
  LiabilityYieldMetricsPayload,
} from "./liabilityAdbContracts";
import { formatRawAsNumeric } from "../utils/format";

export type LiabilityRiskBucketsResponse = LiabilityRiskBucketsPayload & {
  result_meta?: ResultMeta;
};

export type LiabilityYieldMetricsResponse = LiabilityYieldMetricsPayload & {
  result_meta?: ResultMeta;
};

export type LiabilityCounterpartyResponse = LiabilityCounterpartyPayload & {
  result_meta?: ResultMeta;
};

export type LiabilitiesMonthlyResponse = LiabilitiesMonthlyPayload & {
  result_meta?: ResultMeta;
};

export type LiabilityAdbClientMethods = {
  getLiabilityRiskBuckets: (reportDate?: string | null) => Promise<LiabilityRiskBucketsResponse>;
  getLiabilityYieldMetrics: (reportDate?: string | null) => Promise<LiabilityYieldMetricsResponse>;
  getYieldByPeriod: (options: {
    year: number;
    periodType?: "monthly" | "quarterly" | "yearly";
  }) => Promise<YieldByPeriodPayload>;
  getLiabilityCounterparty: (options: {
    reportDate?: string | null;
    topN?: number;
  }) => Promise<LiabilityCounterpartyResponse>;
  getLiabilityKnowledgeBrief: () => Promise<ApiEnvelope<LiabilityKnowledgeBriefPayload>>;
  getCockpitWarnings: (reportDate?: string | null) => Promise<ApiEnvelope<CockpitWarningsPayload>>;
  getContributionSplit: (reportDate?: string | null) => Promise<ApiEnvelope<ContributionSplitPayload>>;
  getLiabilitiesMonthly: (year: number) => Promise<LiabilitiesMonthlyResponse>;
  getLiabilityAdbMonthly: (year: number) => Promise<AdbMonthlyResponse>;
  getAdb: (params: { startDate: string; endDate: string }) => Promise<AdbPayload>;
  getAdbComparison: (
    startDate: string,
    endDate: string,
    options?: {
      topN?: number;
    },
  ) => Promise<AdbComparisonResponse>;
  getAdbMonthly: (year: number) => Promise<AdbMonthlyResponse>;
  getAdbCoverage: (startDate: string, endDate: string) => Promise<AdbCoveragePayload>;
  getAdbInsights: (startDate: string, endDate: string) => Promise<AdbInsightsResponse>;
};

type FetchLike = typeof fetch;
type Delay = () => Promise<void>;

type LiabilityAdbMockBundle = Pick<
  typeof import("../mocks/mockApiEnvelope"),
  "buildMockApiEnvelope"
>;

type EnsureLiabilityAdbMockBundle = () => Promise<LiabilityAdbMockBundle>;

type RequestJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
) => Promise<ApiEnvelope<T>>;

export type LiabilityAdbClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
};

const requestPlainJson = async <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<T> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as T;
};

const requestEnvelopeOrPlainJson = async <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<T> => {
  const payload = await requestPlainJson<Record<string, unknown>>(fetchImpl, baseUrl, path);
  if (
    payload &&
    typeof payload === "object" &&
    "result_meta" in payload &&
    "result" in payload
  ) {
    return payload.result as T;
  }
  return payload as T;
};

const requestEnvelopeOrPlainJsonWithMeta = async <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<{ result: T; result_meta?: ResultMeta; calibration?: BalancePageCalibration | null }> => {
  const payload = await requestPlainJson<Record<string, unknown>>(fetchImpl, baseUrl, path);
  if (
    payload &&
    typeof payload === "object" &&
    "result_meta" in payload &&
    "result" in payload
  ) {
    return {
      result: payload.result as T,
      result_meta: payload.result_meta as ResultMeta,
      // ADB 系列端点把校准说明放在信封顶层（与 result 同层），需要一并透传。
      calibration: payload.calibration as BalancePageCalibration | null | undefined,
    };
  }
  return { result: payload as T };
};

const normalizeNullableNumber = (value: unknown): number | null =>
  value === null || value === undefined ? null : Number(value);

const normalizeMonthlyNimStress = (
  value: unknown,
): { nim_stressed: number | null; delta_bp: number | null } | null => {
  if (!value || typeof value !== "object") {
    return null;
  }
  const raw = value as Record<string, unknown>;
  return {
    nim_stressed: normalizeNullableNumber(raw.nim_stressed),
    delta_bp: normalizeNullableNumber(raw.delta_bp),
  };
};

function normalizeAccountingBasisTrendItem(item: unknown): AdbAccountingBasisDailyAvgTrendItem {
  const basis = item as Record<string, unknown>;
  const rows = Array.isArray(basis.rows) ? basis.rows : [];
  return {
    report_date: String(basis.report_date ?? ""),
    report_month: String(basis.report_month ?? String(basis.report_date ?? "").slice(0, 7)),
    currency_basis: String(basis.currency_basis ?? ""),
    daily_avg_total: normalizeNullableNumber(basis.daily_avg_total),
    rows: rows.map((entry) => {
      const row = entry as Record<string, unknown>;
      return {
        basis_bucket: String(row.basis_bucket ?? ""),
        daily_avg_balance: normalizeNullableNumber(row.daily_avg_balance),
        daily_avg_pct: normalizeNullableNumber(row.daily_avg_pct),
        source_account_patterns: Array.isArray(row.source_account_patterns)
          ? row.source_account_patterns.map(String)
          : [],
      };
    }),
    accounting_controls: Array.isArray(basis.accounting_controls)
      ? basis.accounting_controls.map(String)
      : [],
    excluded_controls: Array.isArray(basis.excluded_controls)
      ? basis.excluded_controls.map(String)
      : [],
  };
}

function normalizeAdbComparisonResponse(
  raw: Record<string, unknown>,
  resultMeta?: ResultMeta,
  calibration?: BalancePageCalibration | null,
): AdbComparisonResponse {
  const mapBreakdown = (items: unknown[]) =>
    items.map((item) => {
      const row = item as Record<string, unknown>;
      return {
        category: String(row.category ?? ""),
        spot_balance: normalizeNullableNumber(row.spot_balance),
        avg_balance: normalizeNullableNumber(row.avg_balance),
        proportion: normalizeNullableNumber(row.proportion),
        weighted_rate:
          row.weighted_rate === null || row.weighted_rate === undefined
            ? null
            : Number(row.weighted_rate),
        rate_coverage_ratio: normalizeNullableNumber(row.rate_coverage_ratio),
      };
    });

  const assetsBreakdown = mapBreakdown(
    Array.isArray(raw.assets_breakdown) ? raw.assets_breakdown : [],
  );
  const liabilitiesBreakdown = mapBreakdown(
    Array.isArray(raw.liabilities_breakdown) ? raw.liabilities_breakdown : [],
  );
  const accountingBasisRaw =
    raw.accounting_basis_daily_avg && typeof raw.accounting_basis_daily_avg === "object"
      ? (raw.accounting_basis_daily_avg as Record<string, unknown>)
      : null;
  const accountingBasisRows = accountingBasisRaw?.rows;

  return {
    result_meta: resultMeta,
    report_date: String(raw.report_date ?? raw.end_date ?? ""),
    start_date: String(raw.start_date ?? ""),
    end_date: String(raw.end_date ?? ""),
    calendar_days_inclusive: Number(raw.calendar_days_inclusive ?? raw.num_days ?? 0),
    adb_denominator_basis: String(raw.adb_denominator_basis ?? "snapshot_calendar") as
      | "formal_calendar"
      | "snapshot_distinct_days"
      | "snapshot_calendar"
      | "ledger_weighted",
    num_days: Number(raw.num_days ?? 0),
    coverage_days:
      raw.coverage_days === null || raw.coverage_days === undefined
        ? undefined
        : Number(raw.coverage_days),
    sample_filled: raw.sample_filled === true || raw.sample_filled === "true" ? true : undefined,
    sample_fill_method: raw.sample_fill_method ? String(raw.sample_fill_method) : undefined,
    simulated: Boolean(raw.simulated),
    total_spot_assets: normalizeNullableNumber(raw.total_spot_assets),
    total_avg_assets: normalizeNullableNumber(raw.total_avg_assets),
    total_spot_liabilities: normalizeNullableNumber(raw.total_spot_liabilities),
    total_avg_liabilities: normalizeNullableNumber(raw.total_avg_liabilities),
    avg_unavailable_reason:
      raw.avg_unavailable_reason === "insufficient_window" || raw.avg_unavailable_reason === "no_data"
        ? raw.avg_unavailable_reason
        : null,
    spot_unavailable_reason: raw.spot_unavailable_reason === "no_data" ? raw.spot_unavailable_reason : null,
    total_avg_interbank_assets: Number(raw.total_avg_interbank_assets ?? 0),
    total_avg_interbank_liabilities: Number(raw.total_avg_interbank_liabilities ?? 0),
    asset_yield:
      raw.asset_yield === null || raw.asset_yield === undefined ? null : Number(raw.asset_yield),
    liability_cost:
      raw.liability_cost === null || raw.liability_cost === undefined
        ? null
        : Number(raw.liability_cost),
    net_interest_margin:
      raw.net_interest_margin === null || raw.net_interest_margin === undefined
        ? null
        : Number(raw.net_interest_margin),
    asset_rate_coverage_ratio: normalizeNullableNumber(raw.asset_rate_coverage_ratio),
    liability_rate_coverage_ratio: normalizeNullableNumber(raw.liability_rate_coverage_ratio),
    assets_breakdown: assetsBreakdown,
    liabilities_breakdown: liabilitiesBreakdown,
    accounting_basis_daily_avg: accountingBasisRaw
      ? {
          report_date: String(accountingBasisRaw.report_date ?? ""),
          currency_basis: String(accountingBasisRaw.currency_basis ?? ""),
          daily_avg_total: normalizeNullableNumber(accountingBasisRaw.daily_avg_total),
          rows: (Array.isArray(accountingBasisRows) ? accountingBasisRows : []).map((item) => {
            const row = item as Record<string, unknown>;
            return {
              basis_bucket: String(row.basis_bucket ?? ""),
              daily_avg_balance: normalizeNullableNumber(row.daily_avg_balance),
              daily_avg_pct: normalizeNullableNumber(row.daily_avg_pct),
              source_account_patterns: Array.isArray(row.source_account_patterns)
                ? row.source_account_patterns.map(String)
                : [],
            };
          }),
          accounting_controls: Array.isArray(accountingBasisRaw.accounting_controls)
            ? accountingBasisRaw.accounting_controls.map(String)
            : [],
          excluded_controls: Array.isArray(accountingBasisRaw.excluded_controls)
            ? accountingBasisRaw.excluded_controls.map(String)
            : [],
        }
      : undefined,
    accounting_basis_daily_avg_trend: Array.isArray(raw.accounting_basis_daily_avg_trend)
      ? raw.accounting_basis_daily_avg_trend.map(normalizeAccountingBasisTrendItem)
      : undefined,
    detail: raw.detail ? String(raw.detail) : undefined,
    calibration,
  };
}

function normalizeAdbMonthlyResponse(
  raw: Record<string, unknown>,
  resultMeta?: ResultMeta,
): AdbMonthlyResponse {
  const months = Array.isArray(raw.months) ? raw.months : [];
  const accountingBasisTrend = Array.isArray(raw.accounting_basis_daily_avg_trend)
    ? raw.accounting_basis_daily_avg_trend
    : [];
  return {
    result_meta: resultMeta,
    year: Number(raw.year ?? 0),
    months: months.map((item) => {
      const row = item as Record<string, unknown>;
      const breakdownAssets = Array.isArray(row.breakdown_assets) ? row.breakdown_assets : [];
      const breakdownLiabilities = Array.isArray(row.breakdown_liabilities)
        ? row.breakdown_liabilities
        : [];
      const mapBreakdown = (entries: unknown[]) =>
        entries.map((entry) => {
          const breakdown = entry as Record<string, unknown>;
          return {
            category: String(breakdown.category ?? ""),
            avg_balance:
              breakdown.avg_balance === null || breakdown.avg_balance === undefined
                ? null
                : Number(breakdown.avg_balance),
            proportion:
              breakdown.proportion === null || breakdown.proportion === undefined
                ? null
                : Number(breakdown.proportion),
            weighted_rate:
              breakdown.weighted_rate === null || breakdown.weighted_rate === undefined
                ? null
                : Number(breakdown.weighted_rate),
            rate_coverage_ratio: normalizeNullableNumber(breakdown.rate_coverage_ratio),
          };
        });

      return {
        month: String(row.month ?? ""),
        month_label: String(row.month_label ?? row.month ?? ""),
        num_days: Number(row.num_days ?? 0),
        avg_assets: normalizeNullableNumber(row.avg_assets),
        avg_liabilities: normalizeNullableNumber(row.avg_liabilities),
        asset_yield:
          row.asset_yield === null || row.asset_yield === undefined
            ? null
            : Number(row.asset_yield),
        liability_cost:
          row.liability_cost === null || row.liability_cost === undefined
            ? null
            : Number(row.liability_cost),
        net_interest_margin:
          row.net_interest_margin === null || row.net_interest_margin === undefined
            ? null
            : Number(row.net_interest_margin),
        nim_stress: normalizeMonthlyNimStress(row.nim_stress),
        asset_rate_coverage_ratio: normalizeNullableNumber(row.asset_rate_coverage_ratio),
        liability_rate_coverage_ratio: normalizeNullableNumber(row.liability_rate_coverage_ratio),
        mom_change_assets:
          row.mom_change_assets === null || row.mom_change_assets === undefined
            ? null
            : Number(row.mom_change_assets),
        mom_change_pct_assets:
          row.mom_change_pct_assets === null || row.mom_change_pct_assets === undefined
            ? null
            : Number(row.mom_change_pct_assets),
        mom_change_liabilities:
          row.mom_change_liabilities === null || row.mom_change_liabilities === undefined
            ? null
            : Number(row.mom_change_liabilities),
        mom_change_pct_liabilities:
          row.mom_change_pct_liabilities === null || row.mom_change_pct_liabilities === undefined
            ? null
            : Number(row.mom_change_pct_liabilities),
        breakdown_assets: mapBreakdown(breakdownAssets),
        breakdown_liabilities: mapBreakdown(breakdownLiabilities),
      };
    }),
    accounting_basis_daily_avg_trend: accountingBasisTrend.map(normalizeAccountingBasisTrendItem),
    ytd_avg_assets: normalizeNullableNumber(raw.ytd_avg_assets),
    ytd_avg_liabilities: normalizeNullableNumber(raw.ytd_avg_liabilities),
    ytd_asset_yield:
      raw.ytd_asset_yield === null || raw.ytd_asset_yield === undefined
        ? null
        : Number(raw.ytd_asset_yield),
    ytd_liability_cost:
      raw.ytd_liability_cost === null || raw.ytd_liability_cost === undefined
        ? null
        : Number(raw.ytd_liability_cost),
    ytd_nim:
      raw.ytd_nim === null || raw.ytd_nim === undefined ? null : Number(raw.ytd_nim),
    ytd_asset_rate_coverage_ratio: normalizeNullableNumber(raw.ytd_asset_rate_coverage_ratio),
    ytd_liability_rate_coverage_ratio: normalizeNullableNumber(
      raw.ytd_liability_rate_coverage_ratio,
    ),
    unit: raw.unit ? String(raw.unit) : undefined,
  };
}

// --- `GET /api/analysis/adb/insights` 归一化 ---
// 契约冻结于 docs/plans/2026-08-13-average-balance-deep-analysis-prd.md §5。
// 规则：契约里带 `| null` 的字段一律保留 null（不得 0 顶替），枚举取值未知时安全归一，
// 数组缺失归一为空数组，`insights` 永不为 null。

const ADB_INSIGHTS_WINDOW_REASONS = new Set(["ok", "no_data"]);
const ADB_NIM_UNAVAILABLE_REASONS = new Set([
  "rate_unavailable",
  "comparison_unavailable",
  "current_unavailable",
  "insufficient_window",
]);
const ADB_INSIGHT_SEVERITIES = new Set(["info", "notice", "warning"]);
const ADB_INSIGHT_DIMENSIONS = new Set([
  "scale",
  "nim",
  "volatility",
  "concentration",
  "quality",
]);

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : {};

const asOptionalRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : null;

const asArray = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

function normalizeAdbInsightsWindow(value: unknown): AdbInsightsWindow {
  const raw = asRecord(value);
  const reason = String(raw.reason ?? "");
  return {
    start_date: String(raw.start_date ?? ""),
    end_date: String(raw.end_date ?? ""),
    calendar_days_inclusive: Number(raw.calendar_days_inclusive ?? 0),
    coverage_days: Number(raw.coverage_days ?? 0),
    available: raw.available === true,
    reason: ADB_INSIGHTS_WINDOW_REASONS.has(reason) ? (reason as AdbInsightsWindowReason) : null,
  };
}

function normalizeAdbScaleSideTotals(value: unknown): AdbScaleSideTotals {
  const raw = asRecord(value);
  return {
    current_avg: Number(raw.current_avg ?? 0),
    prior_avg: Number(raw.prior_avg ?? 0),
    delta: Number(raw.delta ?? 0),
    delta_pct: normalizeNullableNumber(raw.delta_pct),
  };
}

function normalizeAdbScaleContributions(value: unknown): AdbScaleContributionRow[] {
  return asArray(value).map((entry) => {
    const row = asRecord(entry);
    return {
      category: String(row.category ?? ""),
      side: row.side === "liability" ? "liability" : "asset",
      current_avg: normalizeNullableNumber(row.current_avg),
      prior_avg: normalizeNullableNumber(row.prior_avg),
      delta: Number(row.delta ?? 0),
      contribution_pct: normalizeNullableNumber(row.contribution_pct),
    };
  });
}

function normalizeAdbScaleAttribution(value: unknown): AdbScaleAttribution | null {
  const raw = asOptionalRecord(value);
  if (!raw) return null;
  const totals = asRecord(raw.side_totals);
  return {
    side_totals: {
      assets: normalizeAdbScaleSideTotals(totals.assets),
      liabilities: normalizeAdbScaleSideTotals(totals.liabilities),
    },
    asset_contributions: normalizeAdbScaleContributions(raw.asset_contributions),
    liability_contributions: normalizeAdbScaleContributions(raw.liability_contributions),
  };
}

function normalizeAdbNimSide(value: unknown): AdbNimSideAttribution {
  const raw = asRecord(value);
  return {
    total_effect_bp: Number(raw.total_effect_bp ?? 0),
    rate_effect_bp: Number(raw.rate_effect_bp ?? 0),
    mix_effect_bp: Number(raw.mix_effect_bp ?? 0),
    residual_bp: Number(raw.residual_bp ?? 0),
    by_category: asArray(raw.by_category).map((entry) => {
      const row = asRecord(entry);
      return {
        category: String(row.category ?? ""),
        share_current: normalizeNullableNumber(row.share_current),
        share_prior: normalizeNullableNumber(row.share_prior),
        rate_current: normalizeNullableNumber(row.rate_current),
        rate_prior: normalizeNullableNumber(row.rate_prior),
        rate_effect_bp: Number(row.rate_effect_bp ?? 0),
        mix_effect_bp: Number(row.mix_effect_bp ?? 0),
      };
    }),
  };
}

function normalizeAdbNimAttribution(value: unknown): AdbNimAttribution | null {
  const raw = asOptionalRecord(value);
  if (!raw) return null;
  return {
    basis: "qoq",
    nim_current: normalizeNullableNumber(raw.nim_current),
    nim_prior: normalizeNullableNumber(raw.nim_prior),
    nim_delta_bp: normalizeNullableNumber(raw.nim_delta_bp),
    asset_side: normalizeAdbNimSide(raw.asset_side),
    liability_side: normalizeAdbNimSide(raw.liability_side),
  };
}

function normalizeAdbVolatilitySeries(value: unknown): AdbVolatilitySeries | null {
  const raw = asOptionalRecord(value);
  if (!raw) return null;
  const minimum = asRecord(raw.min);
  const maximum = asRecord(raw.max);
  const change = asOptionalRecord(raw.max_daily_change);
  return {
    mean: Number(raw.mean ?? 0),
    std: Number(raw.std ?? 0),
    cv: normalizeNullableNumber(raw.cv),
    min: { date: String(minimum.date ?? ""), value: Number(minimum.value ?? 0) },
    max: { date: String(maximum.date ?? ""), value: Number(maximum.value ?? 0) },
    max_daily_change: change
      ? {
          date: String(change.date ?? ""),
          delta: Number(change.delta ?? 0),
          pct: normalizeNullableNumber(change.pct),
        }
      : null,
  };
}

function normalizeAdbMonthEndEffect(value: unknown): AdbMonthEndEffect {
  const raw = asRecord(value);
  return {
    uplift_pct: normalizeNullableNumber(raw.uplift_pct),
    months_observed: Number(raw.months_observed ?? 0),
    flagged: raw.flagged === true,
  };
}

function normalizeAdbVolatilityBlock(value: unknown): AdbVolatilityBlock | null {
  const raw = asOptionalRecord(value);
  if (!raw) return null;
  const monthEnd = asOptionalRecord(raw.month_end_effect);
  return {
    assets: normalizeAdbVolatilitySeries(raw.assets),
    liabilities: normalizeAdbVolatilitySeries(raw.liabilities),
    anomaly_detection_available: raw.anomaly_detection_available === true,
    anomalies: asArray(raw.anomalies).map((entry) => {
      const row = asRecord(entry);
      return {
        date: String(row.date ?? ""),
        side: row.side === "liability" ? "liability" : "asset",
        value: Number(row.value ?? 0),
        delta: Number(row.delta ?? 0),
        zscore: Number(row.zscore ?? 0),
        direction: row.direction === "down" ? "down" : "up",
      };
    }),
    month_end_effect: monthEnd
      ? {
          assets: normalizeAdbMonthEndEffect(monthEnd.assets),
          liabilities: normalizeAdbMonthEndEffect(monthEnd.liabilities),
        }
      : null,
  };
}

function normalizeAdbConcentrationSide(value: unknown): AdbConcentrationSide | null {
  const raw = asOptionalRecord(value);
  if (!raw) return null;
  return {
    start_observation_date: String(raw.start_observation_date ?? ""),
    end_observation_date: String(raw.end_observation_date ?? ""),
    hhi_start: Number(raw.hhi_start ?? 0),
    hhi_end: Number(raw.hhi_end ?? 0),
    top3_share_start: Number(raw.top3_share_start ?? 0),
    top3_share_end: Number(raw.top3_share_end ?? 0),
    top5_share_start: Number(raw.top5_share_start ?? 0),
    top5_share_end: Number(raw.top5_share_end ?? 0),
    movers: asArray(raw.movers).map((entry) => {
      const row = asRecord(entry);
      return {
        category: String(row.category ?? ""),
        share_start_pct: Number(row.share_start_pct ?? 0),
        share_end_pct: Number(row.share_end_pct ?? 0),
        delta_pp: Number(row.delta_pp ?? 0),
      };
    }),
  };
}

function normalizeAdbConcentrationBlock(value: unknown): AdbConcentrationBlock | null {
  const raw = asOptionalRecord(value);
  if (!raw) return null;
  return {
    assets: normalizeAdbConcentrationSide(raw.assets),
    liabilities: normalizeAdbConcentrationSide(raw.liabilities),
    reason: raw.reason === null || raw.reason === undefined ? null : String(raw.reason),
  };
}

function normalizeAdbInsightItems(value: unknown): AdbInsightItem[] {
  return asArray(value).map((entry) => {
    const row = asRecord(entry);
    const severity = String(row.severity ?? "");
    const dimension = String(row.dimension ?? "");
    return {
      id: String(row.id ?? ""),
      severity: ADB_INSIGHT_SEVERITIES.has(severity) ? (severity as AdbInsightSeverity) : "info",
      dimension: ADB_INSIGHT_DIMENSIONS.has(dimension)
        ? (dimension as AdbInsightDimension)
        : "quality",
      title: String(row.title ?? ""),
      detail: String(row.detail ?? ""),
      evidence: asRecord(row.evidence),
    };
  });
}

function normalizeAdbInsightsResponse(
  raw: Record<string, unknown>,
  resultMeta?: ResultMeta,
): AdbInsightsResponse {
  const windows = asRecord(raw.windows);
  const scaleAttribution = asRecord(raw.scale_attribution);
  const nimReason = String(raw.nim_attribution_unavailable_reason ?? "");
  return {
    result_meta: resultMeta,
    start_date: String(raw.start_date ?? ""),
    end_date: String(raw.end_date ?? ""),
    calendar_days_inclusive: Number(raw.calendar_days_inclusive ?? 0),
    insufficient_window: raw.insufficient_window === true,
    windows: {
      current: normalizeAdbInsightsWindow(windows.current),
      qoq: normalizeAdbInsightsWindow(windows.qoq),
      yoy: normalizeAdbInsightsWindow(windows.yoy),
    },
    scale_attribution: {
      qoq: normalizeAdbScaleAttribution(scaleAttribution.qoq),
      yoy: normalizeAdbScaleAttribution(scaleAttribution.yoy),
    },
    nim_attribution: normalizeAdbNimAttribution(raw.nim_attribution),
    nim_attribution_unavailable_reason: ADB_NIM_UNAVAILABLE_REASONS.has(nimReason)
      ? (nimReason as AdbNimUnavailableReason)
      : null,
    volatility: normalizeAdbVolatilityBlock(raw.volatility),
    concentration: normalizeAdbConcentrationBlock(raw.concentration),
    insights: normalizeAdbInsightItems(raw.insights),
  };
}

function buildLiabilityAnalyticalMockMeta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}_mock`,
    basis: "analytical",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_liability_mock",
    vendor_version: "vv_none",
    rule_version: "rv_liability_mock",
    cache_version: "cv_liability_mock",
    quality_flag: "warning",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: new Date().toISOString(),
  };
}

export function createDemoLiabilityAdbClient(
  delay: Delay,
  ensureMockClientBundle: EnsureLiabilityAdbMockBundle,
): LiabilityAdbClientMethods {
  return {
    async getLiabilityRiskBuckets(reportDate?: string | null) {
      await delay();
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("liability_analytics.risk_buckets"),
        report_date: reportDate?.trim() || "",
        liabilities_structure: [],
        liabilities_term_buckets: [],
        interbank_liabilities_structure: [],
        interbank_liabilities_term_buckets: [],
        issued_liabilities_structure: [],
        issued_liabilities_term_buckets: [],
      };
    },
    async getLiabilityYieldMetrics(reportDate?: string | null) {
      await delay();
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("liability_analytics.yield_metrics"),
        report_date: reportDate?.trim() || "",
        kpi: {
          asset_yield: null,
          liability_cost: null,
          market_liability_cost: null,
          nim: null,
        },
        history: [],
        scatter: [],
      };
    },
    async getYieldByPeriod(options: { year: number; periodType?: "monthly" | "quarterly" | "yearly" }) {
      await delay();
      const y = options.year;
      const pt = options.periodType ?? "monthly";
      return {
        year: y,
        period_type: pt,
        periods: [
          {
            period: `${y}-12`,
            period_type: pt,
            start_date: `${y}-12-01`,
            end_date: `${y}-12-31`,
            num_days: 31,
            total_avg_balance: 1_000_000_000,
            total_pnl: 1_300_000,
            overall_yield: 0.13,
            overall_annualized_yield: 1.53,
            weighted_portfolio_yield: 0.13,
            weighted_portfolio_annualized_yield: 1.53,
            items: [
              {
                business_type_primary: "政策性金融债",
                total_pnl: 1_300_000,
                scale_amount: 1_000_000_000,
                yield_pct: 0.13,
              },
            ],
          },
        ],
      };
    },
    async getLiabilityCounterparty(options: { reportDate?: string | null; topN?: number }) {
      await delay();
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("liability_analytics.counterparty"),
        report_date: options.reportDate?.trim() || "",
        total_value: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
        top10_share: null,
        hhi: null,
        population_count: 0,
        is_truncated: false,
        top_10: [],
        by_type: [],
      };
    },
    async getLiabilityKnowledgeBrief() {
      await delay();
      return {
        result_meta: {
          trace_id: "tr_liability_knowledge_mock",
          basis: "analytical",
          result_kind: "liability.page_knowledge",
          formal_use_allowed: false,
          source_version: "sv_liability_knowledge_mock",
          vendor_version: "vv_none",
          rule_version: "rv_liability_knowledge_v1",
          cache_version: "cv_liability_knowledge_v1",
          quality_flag: "warning",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: new Date().toISOString(),
        },
        result: {
          page_id: "liability-analytics",
          available: false,
          vault_path: null,
          status_note: "mock-no-obsidian",
          notes: [],
        },
      };
    },
    async getCockpitWarnings(reportDate?: string | null) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "liability.cockpit_warnings",
        {
          report_date: reportDate?.trim() || "",
          watch_items: [],
          alert_events: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getContributionSplit(reportDate?: string | null) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "liability.contribution_split",
        {
          report_date: reportDate?.trim() || "",
          contributions: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getLiabilitiesMonthly(year: number) {
      await delay();
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("liability_analytics.monthly"),
        year,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      };
    },
    async getLiabilityAdbMonthly(year: number) {
      await delay();
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("adb.monthly"),
        year,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      };
    },
    async getAdb(_params: { startDate: string; endDate: string }) {
      await delay();
      return {
        summary: {
          total_avg_assets: 0,
          total_avg_liabilities: 0,
          end_spot_assets: 0,
          end_spot_liabilities: 0,
        },
        trend: [],
        breakdown: [],
      };
    },
    async getAdbComparison(_startDate: string, _endDate: string, _options?: { topN?: number }) {
      await delay();
      return {
        report_date: "",
        start_date: "",
        end_date: "",
        calendar_days_inclusive: 0,
        adb_denominator_basis: "snapshot_calendar" as const,
        num_days: 0,
        coverage_days: 0,
        simulated: false,
        total_spot_assets: 0,
        total_avg_assets: 0,
        total_spot_liabilities: 0,
        total_avg_liabilities: 0,
        total_avg_interbank_assets: 0,
        total_avg_interbank_liabilities: 0,
        asset_yield: null,
        liability_cost: null,
        net_interest_margin: null,
        assets_breakdown: [],
        liabilities_breakdown: [],
      };
    },
    async getAdbMonthly(year: number) {
      await delay();
      return {
        year,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      };
    },
    async getAdbCoverage(_startDate: string, _endDate: string) {
      await delay();
      return {
        start_date: _startDate,
        end_date: _endDate,
        calendar_days: 0,
        snapshot_tables: {},
        formal_tables: {},
        snapshot_date_count: 0,
        formal_date_count: 0,
        missing_dates: [],
        missing_count: 0,
        coverage_pct: 0,
      };
    },
    async getAdbInsights(startDate: string, endDate: string) {
      await delay();
      // 演示数据集与 getAdbComparison 一样没有余额行，这里返回后端在「本期无有效余额」
      // 分支下的同形响应：三个窗口全部 no_data、分析块全 null，页面显式披露不可用而不是渲染 0。
      const unavailableWindow = (start: string, end: string): AdbInsightsWindow => ({
        start_date: start,
        end_date: end,
        calendar_days_inclusive: 0,
        coverage_days: 0,
        available: false,
        reason: "no_data",
      });
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("adb.insights"),
        start_date: startDate,
        end_date: endDate,
        calendar_days_inclusive: 0,
        insufficient_window: false,
        windows: {
          current: unavailableWindow(startDate, endDate),
          qoq: unavailableWindow("", ""),
          yoy: unavailableWindow("", ""),
        },
        scale_attribution: { qoq: null, yoy: null },
        nim_attribution: null,
        nim_attribution_unavailable_reason: "current_unavailable",
        volatility: null,
        concentration: null,
        insights: [],
      };
    },
  };
}

export function createRealLiabilityAdbClient(
  options: LiabilityAdbClientFactoryOptions,
): LiabilityAdbClientMethods {
  const { fetchImpl, baseUrl, requestJson } = options;

  return {
    getLiabilityRiskBuckets: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestEnvelopeOrPlainJsonWithMeta<LiabilityRiskBucketsPayload>(
        fetchImpl,
        baseUrl,
        `/api/risk/buckets${q ? `?${q}` : ""}`,
      ).then(({ result, result_meta }) => ({
        ...result,
        result_meta,
      }));
    },
    getLiabilityYieldMetrics: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestEnvelopeOrPlainJsonWithMeta<LiabilityYieldMetricsPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/yield_metrics${q ? `?${q}` : ""}`,
      ).then(({ result, result_meta }) => ({
        ...result,
        result_meta,
      }));
    },
    getYieldByPeriod: ({ year, periodType }) => {
      const params = new URLSearchParams();
      params.set("year", String(year));
      if (periodType) {
        params.set("period_type", periodType);
      }
      return requestEnvelopeOrPlainJson<YieldByPeriodPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/yield-by-period?${params.toString()}`,
      );
    },
    getLiabilityCounterparty: async ({ reportDate, topN }) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      const q = params.toString();
      const { result, result_meta } = await requestEnvelopeOrPlainJsonWithMeta<LiabilityCounterpartyPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/liabilities/counterparty${q ? `?${q}` : ""}`,
      );
      return {
        ...result,
        result_meta,
      };
    },
    getLiabilityKnowledgeBrief: () =>
      requestJson<LiabilityKnowledgeBriefPayload>(
        fetchImpl,
        baseUrl,
        "/ui/liability/business-context",
      ),
    getCockpitWarnings: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<CockpitWarningsPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/liabilities/cockpit-warnings${q ? `?${q}` : ""}`,
      );
    },
    getContributionSplit: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestJson<ContributionSplitPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/liabilities/contribution-split${q ? `?${q}` : ""}`,
      );
    },
    getLiabilitiesMonthly: async (year) => {
      const { result, result_meta } = await requestEnvelopeOrPlainJsonWithMeta<LiabilitiesMonthlyPayload>(
        fetchImpl,
        baseUrl,
        `/api/liabilities/monthly?year=${encodeURIComponent(String(year))}`,
      );
      return {
        ...result,
        result_meta,
      };
    },
    getLiabilityAdbMonthly: async (year) => {
      const { result, result_meta } = await requestEnvelopeOrPlainJsonWithMeta<
        Record<string, unknown>
      >(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb/monthly?year=${encodeURIComponent(String(year))}`,
      );
      return normalizeAdbMonthlyResponse(result, result_meta);
    },
    getAdb: ({ startDate, endDate }) => {
      const params = new URLSearchParams();
      params.set("start_date", startDate.trim());
      params.set("end_date", endDate.trim());
      return requestEnvelopeOrPlainJson<AdbPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb?${params.toString()}`,
      );
    },
    getAdbComparison: async (startDate, endDate, options) => {
      const params = new URLSearchParams();
      params.set("start_date", startDate.trim());
      params.set("end_date", endDate.trim());
      const topN = options?.topN;
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      const { result, result_meta, calibration } = await requestEnvelopeOrPlainJsonWithMeta<
        Record<string, unknown>
      >(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb/comparison?${params.toString()}`,
      );
      return normalizeAdbComparisonResponse(result, result_meta, calibration);
    },
    getAdbMonthly: async (year) => {
      const { result, result_meta } = await requestEnvelopeOrPlainJsonWithMeta<
        Record<string, unknown>
      >(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb/monthly?year=${encodeURIComponent(String(year))}`,
      );
      return normalizeAdbMonthlyResponse(result, result_meta);
    },
    getAdbCoverage: (startDate, endDate) => {
      const params = new URLSearchParams();
      params.set("start_date", startDate.trim());
      params.set("end_date", endDate.trim());
      return requestPlainJson<AdbCoveragePayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb/coverage?${params.toString()}`,
      );
    },
    getAdbInsights: async (startDate, endDate) => {
      const params = new URLSearchParams();
      params.set("start_date", startDate.trim());
      params.set("end_date", endDate.trim());
      const { result, result_meta } = await requestEnvelopeOrPlainJsonWithMeta<
        Record<string, unknown>
      >(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb/insights?${params.toString()}`,
      );
      return normalizeAdbInsightsResponse(result, result_meta);
    },
  };
}
