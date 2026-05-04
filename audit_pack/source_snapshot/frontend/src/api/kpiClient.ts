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

const delay = async () => new Promise((resolve) => setTimeout(resolve, 40));

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

export function createMockKpiClient(): KpiClientMethods {
  return {
    async getKpiOwners(params) {
      await delay();
      return {
        owners: [
          {
            owner_id: 1,
            owner_name: "固定收益部",
            org_unit: "金融市场部",
            year: params?.year ?? new Date().getFullYear(),
            scope_type: "department",
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          {
            owner_id: 2,
            owner_name: "同业业务部",
            org_unit: "金融市场部",
            year: params?.year ?? new Date().getFullYear(),
            scope_type: "department",
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
        ],
        total: 2,
      };
    },
    async getKpiMetrics() {
      await delay();
      return { metrics: [], total: 0 };
    },
    async getKpiMetricById() {
      await delay();
      return {
        metric_id: 1,
        metric_code: "MOCK_001",
        owner_id: 1,
        year: new Date().getFullYear(),
        major_category: "收益类",
        metric_name: "债券投资收益率",
        target_value: "4.50",
        score_weight: "15.00",
        scoring_rule_type: "LINEAR_RATIO",
        data_source_type: "AUTO",
        is_active: true,
      };
    },
    async createKpiMetric(data) {
      await delay();
      return {
        metric_id: Date.now(),
        metric_code: data.metric_code,
        owner_id: data.owner_id,
        year: data.year,
        major_category: data.major_category,
        metric_name: data.metric_name,
        target_value: data.target_value ?? null,
        score_weight: data.score_weight,
        scoring_rule_type: data.scoring_rule_type,
        data_source_type: data.data_source_type,
        is_active: true,
      };
    },
    async updateKpiMetric(metricId, data) {
      await delay();
      return {
        metric_id: metricId,
        metric_code: data.metric_code,
        owner_id: data.owner_id,
        year: data.year,
        major_category: data.major_category,
        metric_name: data.metric_name,
        target_value: data.target_value ?? null,
        score_weight: data.score_weight,
        scoring_rule_type: data.scoring_rule_type,
        data_source_type: data.data_source_type,
        is_active: true,
      };
    },
    async deleteKpiMetric() {
      await delay();
    },
    async getKpiValues(params) {
      await delay();
      return {
        owner_id: params.owner_id,
        owner_name: "固定收益部",
        as_of_date: params.as_of_date,
        metrics: [],
        total: 0,
      };
    },
    async getKpiValuesSummary(params) {
      await delay();
      return {
        owner_id: params.owner_id,
        owner_name: "固定收益部",
        year: params.year,
        period_type: params.period_type,
        period_value: params.period_value,
        period_label: `${params.year}年${params.period_value ?? ""}${params.period_type === "MONTH" ? "月" : params.period_type === "QUARTER" ? "季度" : "年度"}`,
        period_start_date: `${params.year}-01-01`,
        period_end_date: `${params.year}-12-31`,
        metrics: [],
        total: 0,
        total_weight: "100.00",
        total_score: "0.00",
      };
    },
    async createKpiValue(data) {
      await delay();
      return {
        value_id: Date.now(),
        metric_id: data.metric_id,
        as_of_date: data.as_of_date,
        actual_value: data.actual_value ?? null,
        completion_ratio: null,
        progress_pct: data.progress_pct ?? null,
        score_value: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
    },
    async updateKpiValue(valueId, metricId, asOfDate, data) {
      await delay();
      return {
        value_id: valueId || Date.now(),
        metric_id: metricId,
        as_of_date: asOfDate,
        actual_value: data.actual_value ?? null,
        completion_ratio: null,
        progress_pct: data.progress_pct ?? null,
        score_value: data.score_value ?? null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
    },
    async batchUpdateKpiValues() {
      await delay();
      return { success_count: 0, failed_count: 0, errors: [] };
    },
    async fetchAndRecalcKpi(ownerId, asOfDate) {
      await delay();
      return {
        owner_id: ownerId,
        owner_name: "固定收益部",
        as_of_date: asOfDate,
        total_metrics: 0,
        fetched_count: 0,
        scored_count: 0,
        failed_count: 0,
        skipped_count: 0,
        results: [],
      };
    },
    async getKpiReport(params) {
      await delay();
      return {
        year: params.year,
        generated_at: new Date().toISOString(),
        rows: [],
        total: 0,
      };
    },
    async downloadKpiReportCSV() {
      await delay();
    },
  };
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
