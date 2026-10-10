import type { KpiClientMethods } from "../api/kpiClient";

const delay = async () => new Promise((resolve) => setTimeout(resolve, 40));

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
            person_name: null,
            year: params?.year ?? new Date().getFullYear(),
            scope_type: "department",
            scope_key: null,
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          {
            owner_id: 2,
            owner_name: "同业业务部",
            org_unit: "金融市场部",
            person_name: null,
            year: params?.year ?? new Date().getFullYear(),
            scope_type: "department",
            scope_key: null,
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
