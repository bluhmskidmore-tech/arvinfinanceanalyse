import type {
  KpiBatchUpdateResponse,
  KpiFetchAndRecalcRequest,
  KpiFetchAndRecalcResponse,
  KpiMetric,
  KpiMetricListResponse,
  KpiMetricUpsertRequest,
  KpiMetricValue,
  KpiOwnerListResponse,
  KpiPeriodSummaryResponse,
  KpiReportResponse,
  KpiValuesResponse,
} from "./contracts";

export type KpiClientMethods = {
  getKpiOwners: (params?: {
    year?: number;
    is_active?: boolean;
  }) => Promise<KpiOwnerListResponse>;
  getKpiMetrics: (params?: {
    owner_id?: number;
    year?: number;
    is_active?: boolean;
  }) => Promise<KpiMetricListResponse>;
  getKpiMetricById: (metricId: number) => Promise<KpiMetric>;
  createKpiMetric: (data: KpiMetricUpsertRequest) => Promise<KpiMetric>;
  updateKpiMetric: (metricId: number, data: KpiMetricUpsertRequest) => Promise<KpiMetric>;
  deleteKpiMetric: (metricId: number) => Promise<void>;
  getKpiValues: (params: {
    owner_id: number;
    as_of_date: string;
    include_trace?: boolean;
  }) => Promise<KpiValuesResponse>;
  getKpiValuesSummary: (params: {
    owner_id: number;
    year: number;
    period_type: "MONTH" | "QUARTER" | "YEAR";
    period_value?: number;
  }) => Promise<KpiPeriodSummaryResponse>;
  createKpiValue: (data: {
    metric_id: number;
    as_of_date: string;
    actual_value?: string;
    actual_text?: string;
    progress_pct?: string;
    source?: string;
  }) => Promise<KpiMetricValue>;
  updateKpiValue: (
    valueId: number,
    metricId: number,
    asOfDate: string,
    data: {
      target_value?: string;
      actual_value?: string;
      actual_text?: string;
      progress_pct?: string;
      score_value?: string;
      source?: string;
    },
  ) => Promise<KpiMetricValue>;
  batchUpdateKpiValues: (
    asOfDate: string,
    items: Array<{
      metric_id: number;
      actual_value?: string;
      progress_pct?: string;
    }>,
  ) => Promise<KpiBatchUpdateResponse>;
  fetchAndRecalcKpi: (
    ownerId: number,
    asOfDate: string,
    request?: KpiFetchAndRecalcRequest,
  ) => Promise<KpiFetchAndRecalcResponse>;
  getKpiReport: (params: {
    year: number;
    owner_id?: number;
    as_of_date?: string;
    format?: "json" | "csv";
  }) => Promise<KpiReportResponse>;
  downloadKpiReportCSV: (params: {
    year: number;
    owner_id?: number;
    as_of_date?: string;
  }) => Promise<void>;
};

type KpiClientFactoryOptions = {
  fetchImpl: typeof fetch;
  baseUrl: string;
};

function kpiQueryString(params: Record<string, string | number | boolean | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === "") continue;
    q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

async function requestKpiJson<T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetchImpl(`${baseUrl}/api/kpi${path}`, {
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init?.headers as Record<string, string> | undefined),
    },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(text || `KPI API ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function createRealKpiClient({
  fetchImpl,
  baseUrl,
}: KpiClientFactoryOptions): KpiClientMethods {
  return {
    getKpiOwners: (params) =>
      requestKpiJson<KpiOwnerListResponse>(
        fetchImpl,
        baseUrl,
        `/owners${kpiQueryString(params ?? {})}`,
      ),
    getKpiMetrics: (params) =>
      requestKpiJson<KpiMetricListResponse>(
        fetchImpl,
        baseUrl,
        `/metrics${kpiQueryString(params ?? {})}`,
      ),
    getKpiMetricById: (metricId) =>
      requestKpiJson<KpiMetric>(fetchImpl, baseUrl, `/metrics/${metricId}`),
    createKpiMetric: (data) =>
      requestKpiJson<KpiMetric>(
        fetchImpl,
        baseUrl,
        "/metrics",
        { method: "POST", body: JSON.stringify(data) },
      ),
    updateKpiMetric: (metricId, data) =>
      requestKpiJson<KpiMetric>(
        fetchImpl,
        baseUrl,
        `/metrics/${metricId}`,
        { method: "PUT", body: JSON.stringify(data) },
      ),
    deleteKpiMetric: async (metricId) => {
      const response = await fetchImpl(`${baseUrl}/api/kpi/metrics/${metricId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `KPI API ${response.status}`);
      }
    },
    getKpiValues: (params) =>
      requestKpiJson<KpiValuesResponse>(
        fetchImpl,
        baseUrl,
        `/values${kpiQueryString(params)}`,
      ),
    getKpiValuesSummary: (params) =>
      requestKpiJson<KpiPeriodSummaryResponse>(
        fetchImpl,
        baseUrl,
        `/values/summary${kpiQueryString(params)}`,
      ),
    createKpiValue: (data) =>
      requestKpiJson<KpiMetricValue>(
        fetchImpl,
        baseUrl,
        "/values",
        { method: "POST", body: JSON.stringify(data) },
      ),
    updateKpiValue: async (valueId, metricId, asOfDate, data) => {
      if (valueId && valueId > 0) {
        return requestKpiJson<KpiMetricValue>(
          fetchImpl,
          baseUrl,
          `/values/${valueId}`,
          { method: "PUT", body: JSON.stringify(data) },
        );
      }
      return requestKpiJson<KpiMetricValue>(
        fetchImpl,
        baseUrl,
        "/values",
        {
          method: "POST",
          body: JSON.stringify({ metric_id: metricId, as_of_date: asOfDate, ...data }),
        },
      );
    },
    batchUpdateKpiValues: (asOfDate, items) =>
      requestKpiJson<KpiBatchUpdateResponse>(
        fetchImpl,
        baseUrl,
        "/values/batch",
        { method: "POST", body: JSON.stringify({ as_of_date: asOfDate, items }) },
      ),
    fetchAndRecalcKpi: (ownerId, asOfDate, request) =>
      requestKpiJson<KpiFetchAndRecalcResponse>(
        fetchImpl,
        baseUrl,
        `/fetch_and_recalc${kpiQueryString({ owner_id: ownerId, as_of_date: asOfDate })}`,
        { method: "POST", body: JSON.stringify(request ?? {}) },
      ),
    getKpiReport: (params) =>
      requestKpiJson<KpiReportResponse>(
        fetchImpl,
        baseUrl,
        `/report${kpiQueryString(params)}`,
      ),
    downloadKpiReportCSV: async (params) => {
      const response = await fetchImpl(
        `${baseUrl}/api/kpi/report${kpiQueryString({ ...params, format: "csv" })}`,
      );
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `KPI API ${response.status}`);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `kpi_report_${params.year}_${params.as_of_date || "latest"}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    },
  };
}
