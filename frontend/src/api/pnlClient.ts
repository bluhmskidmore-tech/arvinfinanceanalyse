/**
 * P&L and Attribution domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 */
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { mockCampisiDecisionGrade } from "../mocks/campisiMocks";
import { readHttpJsonDetail } from "./httpResponseError";
import type {
  ApiEnvelope,
  CampisiDecisionGradePayload,
  PnlByBusinessAnalysisDimension,
  PnlByBusinessAnalysisPayload,
  PnlByBusinessCandidateInsightsPayload,
  PnlByBusinessManualAdjustmentListPayload,
  PnlByBusinessManualAdjustmentPayload,
  PnlByBusinessManualAdjustmentRequest,
  PnlByBusinessMonthlyPayload,
  PnlByBusinessPayload,
  PnlByBusinessPrecomputeStatus,
  PnlByBusinessYtdPayload,
  PnlV1DataPayload,
  PnlYearlyBusinessSummaryPayload,
} from "./contracts";
import type { PnlAttributionClientMethods } from "./pnlAttributionClient";
import type { PnlCoreClientMethods } from "./pnlCoreClient";
import type { QdbGlMonthlyAnalysisClientMethods } from "./qdbGlMonthlyAnalysisClient";

type FetchLike = typeof fetch;

type PnlClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

function buildCampisiQuery(options?: {
  startDate?: string;
  endDate?: string;
  lookbackDays?: number;
}) {
  const params = new URLSearchParams();
  if (options?.startDate?.trim()) {
    params.set("start_date", options.startDate.trim());
  }
  if (options?.endDate?.trim()) {
    params.set("end_date", options.endDate.trim());
  }
  if (options?.lookbackDays !== undefined) {
    params.set("lookback_days", String(options.lookbackDays));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

type PnlBusinessClientMethods = {
  getPnlV1Data: (date: string) => Promise<ApiEnvelope<PnlV1DataPayload>>;
  getPnlByBusiness: (reportDate: string) => Promise<ApiEnvelope<PnlByBusinessPayload>>;
  getPnlByBusinessYtd: (year: number, asOfDate?: string) => Promise<ApiEnvelope<PnlByBusinessYtdPayload>>;
  getPnlByBusinessMonthly: (year: number, asOfDate?: string) => Promise<ApiEnvelope<PnlByBusinessMonthlyPayload>>;
  getPnlByBusinessAnalysis: (options: {
    year: number;
    asOfDate?: string;
    businessKey?: string;
    dimension: PnlByBusinessAnalysisDimension;
  }) => Promise<ApiEnvelope<PnlByBusinessAnalysisPayload>>;
  getPnlByBusinessCandidateInsights: (
    year: number,
    asOfDate: string,
  ) => Promise<ApiEnvelope<PnlByBusinessCandidateInsightsPayload>>;
  createPnlByBusinessManualAdjustment: (
    payload: PnlByBusinessManualAdjustmentRequest,
  ) => Promise<PnlByBusinessManualAdjustmentPayload>;
  updatePnlByBusinessManualAdjustment: (
    adjustmentId: string,
    payload: PnlByBusinessManualAdjustmentRequest,
  ) => Promise<PnlByBusinessManualAdjustmentPayload>;
  revokePnlByBusinessManualAdjustment: (
    adjustmentId: string,
  ) => Promise<PnlByBusinessManualAdjustmentPayload>;
  restorePnlByBusinessManualAdjustment: (
    adjustmentId: string,
  ) => Promise<PnlByBusinessManualAdjustmentPayload>;
  getPnlByBusinessManualAdjustments: (
    reportDate: string,
  ) => Promise<PnlByBusinessManualAdjustmentListPayload>;
  getPnlByBusinessPrecomputeStatus: (year: number, asOfDate?: string) => Promise<PnlByBusinessPrecomputeStatus>;
  rebuildPnlByBusinessPrecompute: (year: number, asOfDate?: string) => Promise<PnlByBusinessPrecomputeStatus>;
  getPnlYearlyBusinessSummary: (year: number) => Promise<ApiEnvelope<PnlYearlyBusinessSummaryPayload>>;
  getPnlCampisiDecisionGrade: (options?: {
    startDate?: string;
    endDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<CampisiDecisionGradePayload>>;
};

export type PnlClientMethods =
  PnlBusinessClientMethods
  & PnlAttributionClientMethods
  & PnlCoreClientMethods
  & QdbGlMonthlyAnalysisClientMethods;

const delay = async () => new Promise((resolve) => setTimeout(resolve, 40));

export function createMockPnlBusinessClient(): PnlBusinessClientMethods {
  return {
    async getPnlV1Data(date: string) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.v1_data",
        {
          report_date: date,
          source_tables: ["data_input/pnl", "data_input/pnl_514", "data_input/pnl_516", "data_input/pnl_517"],
          rows: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPnlByBusiness(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.by_business",
        {
          report_date: reportDate,
          source_tables: ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"],
          summary: {
            business_count: 0,
            total_pnl: "0.00",
            total_scale_amount: "0.00",
            traced_pnl_row_count: 0,
            untraced_pnl_row_count: 0,
            untraced_breakdown: [],
          },
          rows: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPnlByBusinessYtd(year: number, _asOfDate?: string) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.by_business_ytd",
        {
          year,
          period_type: "yearly",
          period_label: `${year}年累计`,
          period_start_date: `${year}-01-01`,
          period_end_date: _asOfDate ?? `${year}-12-31`,
          total_pnl: "0.00",
          source_tables: ["data_input/pnl", "fact_formal_zqtz_balance_daily", "ZQTZ_ASSET_BOND_ROWS"],
          items: [],
        },
        { basis: "analytical", formal_use_allowed: false },
      );
    },
    async getPnlByBusinessPrecomputeStatus(year: number, asOfDate?: string) {
      await delay();
      return {
        year,
        status: "completed",
        serving_mode: "precomputed",
        is_current: true,
        run_id: null,
        report_date: asOfDate ?? `${year}-12-31`,
        latest_available_as_of_date: `${year}-12-31`,
        source_version: "sv_mock_pnl_by_business_precompute",
        rule_version: "rv_pnl_by_business_precompute_v6",
        queued_at: null,
        started_at: null,
        finished_at: null,
        generated_at: new Date().toISOString(),
        record_count: 1,
        error_message: null,
        failure_category: null,
        trigger_reason: null,
        retry_attempt: 0,
        retry_policy: { max_retries: 3, min_backoff_seconds: 15 },
      };
    },
    async rebuildPnlByBusinessPrecompute(year: number, asOfDate?: string) {
      await delay();
      return {
        year,
        status: "queued",
        serving_mode: "live_fallback",
        is_current: false,
        run_id: `pnl_by_business_precompute:mock-${year}`,
        report_date: asOfDate ?? null,
        latest_available_as_of_date: `${year}-12-31`,
        source_version: "sv_pnl_by_business_precompute_pending",
        rule_version: "rv_pnl_by_business_precompute_v6",
        queued_at: new Date().toISOString(),
        started_at: null,
        finished_at: null,
        generated_at: null,
        record_count: null,
        error_message: null,
        failure_category: null,
        trigger_reason: "manual_retry",
        retry_attempt: 0,
        retry_policy: { max_retries: 3, min_backoff_seconds: 15 },
      };
    },
    async createPnlByBusinessManualAdjustment(payload) {
      await delay();
      return {
        adjustment_id: "pba-mock-1",
        event_type: "created",
        created_at: new Date().toISOString(),
        stream: "pnl_by_business_adjustments",
        business_type: payload.business_type ?? "",
        reason: payload.reason ?? "",
        ...payload,
      };
    },
    async updatePnlByBusinessManualAdjustment(adjustmentId, payload) {
      await delay();
      return {
        adjustment_id: adjustmentId,
        event_type: "edited",
        created_at: new Date().toISOString(),
        stream: "pnl_by_business_adjustments",
        business_type: payload.business_type ?? "",
        reason: payload.reason ?? "",
        ...payload,
      };
    },
    async revokePnlByBusinessManualAdjustment(adjustmentId) {
      await delay();
      return {
        adjustment_id: adjustmentId,
        event_type: "revoked",
        created_at: new Date().toISOString(),
        stream: "pnl_by_business_adjustments",
        report_date: "",
        row_key: "",
        business_type: "",
        operator: "DELTA",
        approval_status: "rejected",
        manual_adjustment: "0",
        reason: "",
      };
    },
    async restorePnlByBusinessManualAdjustment(adjustmentId) {
      await delay();
      return {
        adjustment_id: adjustmentId,
        event_type: "restored",
        created_at: new Date().toISOString(),
        stream: "pnl_by_business_adjustments",
        report_date: "",
        row_key: "",
        business_type: "",
        operator: "DELTA",
        approval_status: "approved",
        manual_adjustment: "0",
        reason: "",
      };
    },
    async getPnlByBusinessManualAdjustments(reportDate) {
      await delay();
      return {
        report_date: reportDate,
        adjustment_count: 0,
        event_total: 0,
        adjustments: [],
        events: [],
      };
    },
    async getPnlByBusinessMonthly(year: number, _asOfDate?: string) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.by_business_monthly",
        {
          year,
          as_of_date: _asOfDate ?? `${year}-12-31`,
          source_tables: [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
            "ZQTZ_ASSET_BOND_ROWS",
          ],
          months: [],
          management_change: null,
        },
        { basis: "analytical", formal_use_allowed: false },
      );
    },
    async getPnlByBusinessAnalysis(options) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.by_business_analysis",
        {
          year: options.year,
          as_of_date: options.asOfDate ?? `${options.year}-12-31`,
          business_key: options.businessKey ?? null,
          dimension: options.dimension,
          period_start_date: `${options.year}-01-01`,
          period_end_date: options.asOfDate ?? `${options.year}-12-31`,
          source_tables: [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
            "ZQTZ_ASSET_BOND_ROWS",
          ],
          rows: [],
        },
        { basis: "analytical", formal_use_allowed: false },
      );
    },
    async getPnlByBusinessCandidateInsights(year: number, asOfDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.by_business_candidate_insights",
        {
          year,
          as_of_date: asOfDate,
          concentration: {
            year,
            as_of_date: asOfDate,
            total_avg_balance: "0.00",
            hhi_pct: "0.00",
            top_n: 3,
            top_n_share_pct: "0.00",
            rows: [],
          },
          negative_ftp_persistence: {
            as_of_date: asOfDate,
            lookback_months: 12,
            window_start_month: null,
            window_end_month: null,
            months_observed: 0,
            negative_ftp_month_share_pct: null,
            negative_ftp_longest_streak_months: 0,
            rows: [],
          },
          share_drift: {
            year,
            as_of_date: asOfDate,
            baseline_year: year - 1,
            baseline_as_of_date: null,
            baseline_available: false,
            rows: [],
          },
          reconciliation_diagnostics: {
            as_of_date: asOfDate,
            lookback_months: 12,
            rows: [],
          },
        },
        { basis: "analytical", formal_use_allowed: false, tables_used: ["pnl.by_business_ytd", "pnl.by_business_monthly"] },
      );
    },
    async getPnlCampisiDecisionGrade(_options?: {
      startDate?: string;
      endDate?: string;
      lookbackDays?: number;
    }) {
      await delay();
      return buildMockApiEnvelope("campisi.decision_grade", mockCampisiDecisionGrade, {
        basis: "formal",
        formal_use_allowed: true,
      });
    },
    async getPnlYearlyBusinessSummary(year: number) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.yearly_summary",
        {
          year,
          source_tables: ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"],
          rows: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
  };
}

export function createRealPnlBusinessClient({
  fetchImpl,
  baseUrl,
}: PnlClientFactoryOptions): PnlBusinessClientMethods {
  return {
    getPnlV1Data: (date: string) =>
      requestJson<PnlV1DataPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/v1-data?date=${encodeURIComponent(date)}`,
      ),
    getPnlByBusiness: (reportDate: string) =>
      requestJson<PnlByBusinessPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getPnlByBusinessYtd: (year: number, asOfDate?: string) => {
      const query = new URLSearchParams({ year: String(year) });
      if (asOfDate) {
        query.set("as_of_date", asOfDate);
      }
      return requestJson<PnlByBusinessYtdPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business-ytd?${query.toString()}`,
      );
    },
    getPnlByBusinessPrecomputeStatus: (year: number, asOfDate?: string) => {
      const query = new URLSearchParams({ year: String(year) });
      if (asOfDate) {
        query.set("as_of_date", asOfDate);
      }
      return requestActionJson<PnlByBusinessPrecomputeStatus>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business/precompute-status?${query.toString()}`,
      );
    },
    rebuildPnlByBusinessPrecompute: (year: number, asOfDate?: string) => {
      const query = new URLSearchParams({ year: String(year) });
      if (asOfDate) {
        query.set("as_of_date", asOfDate);
      }
      return requestActionJson<PnlByBusinessPrecomputeStatus>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business/precompute-rebuild?${query.toString()}`,
        { method: "POST" },
      );
    },
    createPnlByBusinessManualAdjustment: (payload) =>
      requestActionWithBody<PnlByBusinessManualAdjustmentPayload, PnlByBusinessManualAdjustmentRequest>(
        fetchImpl,
        baseUrl,
        "/api/pnl/by-business/manual-adjustments",
        payload,
      ),
    updatePnlByBusinessManualAdjustment: (adjustmentId, payload) =>
      requestActionWithBody<PnlByBusinessManualAdjustmentPayload, PnlByBusinessManualAdjustmentRequest>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business/manual-adjustments/${encodeURIComponent(adjustmentId)}/edit`,
        payload,
      ),
    revokePnlByBusinessManualAdjustment: (adjustmentId) =>
      requestActionJson<PnlByBusinessManualAdjustmentPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business/manual-adjustments/${encodeURIComponent(adjustmentId)}/revoke`,
        { method: "POST" },
      ),
    restorePnlByBusinessManualAdjustment: (adjustmentId) =>
      requestActionJson<PnlByBusinessManualAdjustmentPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business/manual-adjustments/${encodeURIComponent(adjustmentId)}/restore`,
        { method: "POST" },
      ),
    getPnlByBusinessManualAdjustments: (reportDate) =>
      requestActionJson<PnlByBusinessManualAdjustmentListPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business/manual-adjustments?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getPnlByBusinessMonthly: (year: number, asOfDate?: string) => {
      const query = new URLSearchParams({ year: String(year) });
      if (asOfDate) {
        query.set("as_of_date", asOfDate);
      }
      return requestJson<PnlByBusinessMonthlyPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business-monthly?${query.toString()}`,
      );
    },
    getPnlByBusinessAnalysis: (options) => {
      const query = new URLSearchParams({
        year: String(options.year),
        dimension: options.dimension,
      });
      if (options.asOfDate) {
        query.set("as_of_date", options.asOfDate);
      }
      if (options.businessKey) {
        query.set("business_key", options.businessKey);
      }
      return requestJson<PnlByBusinessAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business-analysis?${query.toString()}`,
      );
    },
    getPnlByBusinessCandidateInsights: (year: number, asOfDate: string) => {
      const query = new URLSearchParams({ year: String(year), as_of_date: asOfDate });
      return requestJson<PnlByBusinessCandidateInsightsPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business-candidate-insights?${query.toString()}`,
      );
    },
    getPnlCampisiDecisionGrade: (options) =>
      requestJson<CampisiDecisionGradePayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl-attribution/campisi/decision-grade${buildCampisiQuery(options)}`,
      ),
    getPnlYearlyBusinessSummary: (year: number) =>
      requestJson<PnlYearlyBusinessSummaryPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/yearly-summary?year=${encodeURIComponent(String(year))}`,
      ),
  };
}

async function requestJson<TData>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<TData>> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<TData>;
}

async function requestActionJson<T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as T;
}

async function requestActionWithBody<TResponse, TBody>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  body: TBody,
): Promise<TResponse> {
  return requestActionJson<TResponse>(fetchImpl, baseUrl, path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
