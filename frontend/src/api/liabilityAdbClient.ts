/**
 * Liability and ADB client slice.
 * Imported by client.ts for ApiClient composition.
 */
import type {
  AdbAccountingBasisDailyAvgTrendItem,
  AdbComparisonResponse,
  AdbCoveragePayload,
  AdbMonthlyResponse,
  AdbPayload,
  ApiEnvelope,
  CockpitWarningsPayload,
  ContributionSplitPayload,
  LiabilitiesMonthlyPayload,
  LiabilityCounterpartyPayload,
  LiabilityKnowledgeBriefPayload,
  LiabilityRiskBucketsPayload,
  LiabilityYieldMetricsPayload,
  ResultMeta,
  YieldByPeriodPayload,
} from "./contracts";
import { formatRawAsNumeric } from "../utils/format";

export type LiabilityAdbClientMethods = {
  getLiabilityRiskBuckets: (reportDate?: string | null) => Promise<LiabilityRiskBucketsPayload>;
  getLiabilityYieldMetrics: (reportDate?: string | null) => Promise<LiabilityYieldMetricsPayload>;
  getYieldByPeriod: (options: {
    year: number;
    periodType?: "monthly" | "quarterly" | "yearly";
  }) => Promise<YieldByPeriodPayload>;
  getLiabilityCounterparty: (options: {
    reportDate?: string | null;
    topN?: number;
  }) => Promise<LiabilityCounterpartyPayload>;
  getLiabilityKnowledgeBrief: () => Promise<ApiEnvelope<LiabilityKnowledgeBriefPayload>>;
  getCockpitWarnings: (reportDate?: string | null) => Promise<ApiEnvelope<CockpitWarningsPayload>>;
  getContributionSplit: (reportDate?: string | null) => Promise<ApiEnvelope<ContributionSplitPayload>>;
  getLiabilitiesMonthly: (year: number) => Promise<LiabilitiesMonthlyPayload>;
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
): Promise<{ result: T; result_meta?: ResultMeta }> => {
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
    };
  }
  return { result: payload as T };
};

function normalizeAccountingBasisTrendItem(item: unknown): AdbAccountingBasisDailyAvgTrendItem {
  const basis = item as Record<string, unknown>;
  const rows = Array.isArray(basis.rows) ? basis.rows : [];
  return {
    report_date: String(basis.report_date ?? ""),
    report_month: String(basis.report_month ?? String(basis.report_date ?? "").slice(0, 7)),
    currency_basis: String(basis.currency_basis ?? ""),
    daily_avg_total: Number(basis.daily_avg_total ?? 0),
    rows: rows.map((entry) => {
      const row = entry as Record<string, unknown>;
      return {
        basis_bucket: String(row.basis_bucket ?? ""),
        daily_avg_balance: Number(row.daily_avg_balance ?? 0),
        daily_avg_pct:
          row.daily_avg_pct === null || row.daily_avg_pct === undefined
            ? null
            : Number(row.daily_avg_pct),
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
): AdbComparisonResponse {
  const mapBreakdown = (items: unknown[]) =>
    items.map((item) => {
      const row = item as Record<string, unknown>;
      return {
        category: String(row.category ?? ""),
        spot_balance: Number(row.spot_balance ?? 0),
        avg_balance: Number(row.avg_balance ?? 0),
        proportion: Number(row.proportion ?? 0),
        weighted_rate:
          row.weighted_rate === null || row.weighted_rate === undefined
            ? null
            : Number(row.weighted_rate),
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
    total_spot_assets: Number(raw.total_spot_assets ?? 0),
    total_avg_assets: Number(raw.total_avg_assets ?? 0),
    total_spot_liabilities: Number(raw.total_spot_liabilities ?? 0),
    total_avg_liabilities: Number(raw.total_avg_liabilities ?? 0),
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
    assets_breakdown: assetsBreakdown,
    liabilities_breakdown: liabilitiesBreakdown,
    accounting_basis_daily_avg: accountingBasisRaw
      ? {
          report_date: String(accountingBasisRaw.report_date ?? ""),
          currency_basis: String(accountingBasisRaw.currency_basis ?? ""),
          daily_avg_total: Number(accountingBasisRaw.daily_avg_total ?? 0),
          rows: (Array.isArray(accountingBasisRows) ? accountingBasisRows : []).map((item) => {
            const row = item as Record<string, unknown>;
            return {
              basis_bucket: String(row.basis_bucket ?? ""),
              daily_avg_balance: Number(row.daily_avg_balance ?? 0),
              daily_avg_pct:
                row.daily_avg_pct === null || row.daily_avg_pct === undefined
                  ? null
                  : Number(row.daily_avg_pct),
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
            avg_balance: Number(breakdown.avg_balance ?? 0),
            proportion:
              breakdown.proportion === null || breakdown.proportion === undefined
                ? null
                : Number(breakdown.proportion),
            weighted_rate:
              breakdown.weighted_rate === null || breakdown.weighted_rate === undefined
                ? null
                : Number(breakdown.weighted_rate),
          };
        });

      return {
        month: String(row.month ?? ""),
        month_label: String(row.month_label ?? row.month ?? ""),
        num_days: Number(row.num_days ?? 0),
        avg_assets: Number(row.avg_assets ?? 0),
        avg_liabilities: Number(row.avg_liabilities ?? 0),
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
    ytd_avg_assets: Number(raw.ytd_avg_assets ?? 0),
    ytd_avg_liabilities: Number(raw.ytd_avg_liabilities ?? 0),
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
    unit: raw.unit ? String(raw.unit) : undefined,
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
        report_date: options.reportDate?.trim() || "",
        total_value: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
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
        year,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      };
    },
    async getLiabilityAdbMonthly(year: number) {
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
      return requestEnvelopeOrPlainJson<LiabilityRiskBucketsPayload>(
        fetchImpl,
        baseUrl,
        `/api/risk/buckets${q ? `?${q}` : ""}`,
      );
    },
    getLiabilityYieldMetrics: (reportDate) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      const q = params.toString();
      return requestEnvelopeOrPlainJson<LiabilityYieldMetricsPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/yield_metrics${q ? `?${q}` : ""}`,
      );
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
    getLiabilityCounterparty: ({ reportDate, topN }) => {
      const params = new URLSearchParams();
      if (reportDate?.trim()) {
        params.set("report_date", reportDate.trim());
      }
      if (topN !== undefined) {
        params.set("top_n", String(topN));
      }
      const q = params.toString();
      return requestEnvelopeOrPlainJson<LiabilityCounterpartyPayload>(
        fetchImpl,
        baseUrl,
        `/api/analysis/liabilities/counterparty${q ? `?${q}` : ""}`,
      );
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
    getLiabilitiesMonthly: (year) =>
      requestEnvelopeOrPlainJson<LiabilitiesMonthlyPayload>(
        fetchImpl,
        baseUrl,
        `/api/liabilities/monthly?year=${encodeURIComponent(String(year))}`,
      ),
    getLiabilityAdbMonthly: (year) =>
      requestEnvelopeOrPlainJson<AdbMonthlyResponse>(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb/monthly?year=${encodeURIComponent(String(year))}`,
      ),
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
      const { result, result_meta } = await requestEnvelopeOrPlainJsonWithMeta<
        Record<string, unknown>
      >(
        fetchImpl,
        baseUrl,
        `/api/analysis/adb/comparison?${params.toString()}`,
      );
      return normalizeAdbComparisonResponse(result, result_meta);
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
  };
}
