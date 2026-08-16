/**
 * P&L and Attribution domain — type slice of ApiClient.
 * Imported and re-exported by client.ts for backward compatibility.
 * Mock factory lives in pnlMockClient.ts so mock payloads stay out of the
 * real-mode bundle.
 */
import { readHttpJsonDetail } from "./httpResponseError";
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
    getPnlByBusinessInsights: (year: number, asOfDate: string) => {
      const query = new URLSearchParams({ year: String(year), as_of_date: asOfDate });
      return requestJson<PnlByBusinessInsightsPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/by-business-insights?${query.toString()}`,
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
