/**
 * P&L and Attribution domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 * Mock factory lives in pnlMockClient.ts so mock payloads stay out of the
 * real-mode bundle.
 */
import { readHttpJsonDetail } from "./httpResponseError";
import {
  assertApiEnvelopeShape,
  requestJson as transportRequestJson,
  type ShapeFieldSpec,
  type TransportRequestOptions,
} from "./transport";
import type {
  ApiEnvelope,
  CampisiDecisionGradePayload,
  PnlByBusinessAnalysisDimension,
  PnlByBusinessAnalysisPayload,
  PnlByBusinessCandidateInsightsPayload,
  PnlByBusinessInsightsPayload,
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

export type PnlByBusinessInsightsRequestOptions = Pick<TransportRequestOptions, "signal"> & {
  generation?: string;
};

export type PnlByBusinessPrecomputeStatusRequestOptions = Pick<TransportRequestOptions, "signal">;

export type PnlByBusinessPrecomputeRebuildOptions = {
  includePageDependencies?: boolean;
  scope?: "selected" | "all_available";
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

export type PnlBusinessClientMethods = {
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
  getPnlByBusinessInsights: (
    year: number,
    asOfDate: string,
    options?: PnlByBusinessInsightsRequestOptions,
  ) => Promise<ApiEnvelope<PnlByBusinessInsightsPayload>>;
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
  getPnlByBusinessPrecomputeStatus: (
    year: number,
    asOfDate?: string,
    options?: PnlByBusinessPrecomputeStatusRequestOptions,
  ) => Promise<PnlByBusinessPrecomputeStatus>;
  rebuildPnlByBusinessPrecompute: (
    year: number,
    asOfDate?: string,
    options?: PnlByBusinessPrecomputeRebuildOptions,
  ) => Promise<PnlByBusinessPrecomputeStatus>;
  getPnlYearlyBusinessSummary: (year: number) => Promise<ApiEnvelope<PnlYearlyBusinessSummaryPayload>>;
  getPnlCampisiDecisionGrade: (options?: {
    startDate?: string;
    endDate?: string;
    lookbackDays?: number;
  }) => Promise<ApiEnvelope<CampisiDecisionGradePayload>>;
};

/**
 * Business-critical field sample for `/api/pnl/by-business` — the PnL-by-business
 * page's primary payload (`PnlByBusinessPayload`). Wired as the Wave1/F06 sample
 * lane; other `pnlClient.ts` endpoints keep the shell-only envelope check until a
 * later batch extends this pattern.
 */
const PNL_BY_BUSINESS_RESULT_FIELDS: ShapeFieldSpec[] = [
  { path: "report_date", type: "string" },
  { path: "rows", type: "array" },
  { path: "summary", type: "object" },
  { path: "summary.total_pnl", type: "string" },
  { path: "summary.interest_income_514", type: "string" },
  { path: "summary.fair_value_change_516", type: "string" },
  { path: "summary.capital_gain_517", type: "string" },
  { path: "summary.pnl_row_count", type: "number" },
];

/**
 * `/api/pnl/by-business-insights` has no cache and recomputes the whole year per
 * call: measured 2026-07-31 at ~52s warm and >60s cold, so the shared transport
 * default (`DEFAULT_REQUEST_JSON_TIMEOUT_MS`, 60s) must not apply to this endpoint.
 */
export const PNL_BY_BUSINESS_INSIGHTS_TIMEOUT_MS = 180_000;

export type PnlClientMethods =
  PnlBusinessClientMethods
  & PnlAttributionClientMethods
  & PnlCoreClientMethods
  & QdbGlMonthlyAnalysisClientMethods;

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
        PNL_BY_BUSINESS_RESULT_FIELDS,
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
    getPnlByBusinessPrecomputeStatus: (
      year: number,
      asOfDate?: string,
      options?: PnlByBusinessPrecomputeStatusRequestOptions,
    ) => {
      const query = new URLSearchParams({ year: String(year) });
      if (asOfDate) {
        query.set("as_of_date", asOfDate);
      }
      return requestActionJson<PnlByBusinessPrecomputeStatus>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business/precompute-status?${query.toString()}`,
        { signal: options?.signal },
      );
    },
    rebuildPnlByBusinessPrecompute: (
      year: number,
      asOfDate?: string,
      options?: PnlByBusinessPrecomputeRebuildOptions,
    ) => {
      const query = new URLSearchParams({ year: String(year) });
      if (options?.scope) {
        query.set("scope", options.scope);
      }
      if (asOfDate) {
        query.set("as_of_date", asOfDate);
      }
      if (options?.includePageDependencies) {
        query.set("include_page_dependencies", "true");
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
    getPnlByBusinessInsights: (
      year: number,
      asOfDate: string,
      options?: PnlByBusinessInsightsRequestOptions,
    ) => {
      const query = new URLSearchParams({ year: String(year), as_of_date: asOfDate });
      if (options?.generation) {
        query.set("generation", options.generation);
      }
      return transportRequestJson<PnlByBusinessInsightsPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business-insights?${query.toString()}`,
        {
          timeoutMs: PNL_BY_BUSINESS_INSIGHTS_TIMEOUT_MS,
          errorDetail: "json-detail",
          signal: options?.signal,
        },
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
  /**
   * Optional business-critical field sample checked against `result`
   * (see `ShapeFieldSpec` in `./transport`). Omitted for endpoints not yet
   * wired to field-level validation (shell-only envelope check stays as-is
   * for those, matching historical behavior).
   */
  resultFields?: ShapeFieldSpec[],
): Promise<ApiEnvelope<TData>> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const detail = await readHttpJsonDetail(response);
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }
  const payload: unknown = await response.json();
  if (resultFields?.length) {
    assertApiEnvelopeShape(payload, `${baseUrl}${path}`, resultFields);
  }
  return payload as ApiEnvelope<TData>;
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
