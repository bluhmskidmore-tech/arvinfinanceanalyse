import {
  createContext,
  createElement,
  useContext,
  useMemo,
  type ReactNode,
} from "react";

import type {
  AlertsPayload,
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceNewsEventsPayload,
  ContributionPayload,
  FormalPnlDisabledResponse,
  FormalPnlRefreshPayload,
  HealthResponse,
  MacroVendorPayload,
  OverviewPayload,
  PlaceholderSnapshot,
  ProductCategoryDatesPayload,
  ProductCategoryManualAdjustmentListPayload,
  ProductCategoryManualAdjustmentExportPayload,
  ProductCategoryManualAdjustmentPayload,
  ProductCategoryManualAdjustmentQuery,
  ProductCategoryManualAdjustmentRequest,
  ProductCategoryRefreshPayload,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
  PnlAttributionPayload,
  ResultMeta,
  RiskOverviewPayload,
  SourcePreviewHistoryPayload,
  SourcePreviewRefreshPayload,
  SourcePreviewRowsPayload,
  SourcePreviewTracesPayload,
  SourcePreviewColumn,
  SourcePreviewSummary,
  SourcePreviewPayload,
  SummaryPayload,
} from "./contracts";
import {
  alertsPayload,
  contributionPayload,
  overviewPayload,
  placeholderSnapshots,
  pnlAttributionPayload,
  riskOverviewPayload,
  summaryPayload,
} from "../mocks/workbench";

export type DataSourceMode = "mock" | "real";

export type ApiClient = {
  mode: DataSourceMode;
  getHealth: () => Promise<HealthResponse>;
  getOverview: () => Promise<ApiEnvelope<OverviewPayload>>;
  getSummary: () => Promise<ApiEnvelope<SummaryPayload>>;
  getFormalPnlDates: () => Promise<FormalPnlDisabledResponse>;
  getFormalPnlData: (date: string) => Promise<FormalPnlDisabledResponse>;
  getFormalPnlOverview: (reportDate: string) => Promise<FormalPnlDisabledResponse>;
  refreshFormalPnl: () => Promise<FormalPnlRefreshPayload>;
  getFormalPnlImportStatus: (runId?: string) => Promise<FormalPnlRefreshPayload>;
  getPnlAttribution: () => Promise<ApiEnvelope<PnlAttributionPayload>>;
  getRiskOverview: () => Promise<ApiEnvelope<RiskOverviewPayload>>;
  getContribution: () => Promise<ApiEnvelope<ContributionPayload>>;
  getAlerts: () => Promise<ApiEnvelope<AlertsPayload>>;
  getPlaceholderSnapshot: (key: string) => Promise<ApiEnvelope<PlaceholderSnapshot>>;
  getSourceFoundation: () => Promise<ApiEnvelope<SourcePreviewPayload>>;
  refreshSourcePreview: () => Promise<SourcePreviewRefreshPayload>;
  getSourcePreviewRefreshStatus: (runId: string) => Promise<SourcePreviewRefreshPayload>;
  getSourceFoundationHistory: (options: {
    sourceFamily?: string;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<SourcePreviewHistoryPayload>>;
  getSourceFoundationRows: (options: {
    sourceFamily: string;
    ingestBatchId: string;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<SourcePreviewRowsPayload>>;
  getSourceFoundationTraces: (options: {
    sourceFamily: string;
    ingestBatchId: string;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<SourcePreviewTracesPayload>>;
  getMacroFoundation: () => Promise<ApiEnvelope<MacroVendorPayload>>;
  getChoiceMacroLatest: () => Promise<ApiEnvelope<ChoiceMacroLatestPayload>>;
  getChoiceNewsEvents: (options: {
    limit: number;
    offset: number;
    groupId?: string;
    topicCode?: string;
    errorOnly?: boolean;
    receivedFrom?: string;
    receivedTo?: string;
  }) => Promise<ApiEnvelope<ChoiceNewsEventsPayload>>;
  getProductCategoryDates: () => Promise<ApiEnvelope<ProductCategoryDatesPayload>>;
  refreshProductCategoryPnl: () => Promise<ProductCategoryRefreshPayload>;
  getProductCategoryRefreshStatus: (runId: string) => Promise<ProductCategoryRefreshPayload>;
  createProductCategoryManualAdjustment: (
    payload: ProductCategoryManualAdjustmentRequest,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  getProductCategoryManualAdjustments: (
    reportDate: string,
    options?: ProductCategoryManualAdjustmentQuery,
  ) => Promise<ProductCategoryManualAdjustmentListPayload>;
  exportProductCategoryManualAdjustmentsCsv: (
    reportDate: string,
    options?: ProductCategoryManualAdjustmentQuery,
  ) => Promise<ProductCategoryManualAdjustmentExportPayload>;
  updateProductCategoryManualAdjustment: (
    adjustmentId: string,
    payload: ProductCategoryManualAdjustmentRequest,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  revokeProductCategoryManualAdjustment: (
    adjustmentId: string,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  restoreProductCategoryManualAdjustment: (
    adjustmentId: string,
  ) => Promise<ProductCategoryManualAdjustmentPayload>;
  getProductCategoryPnl: (options: {
    reportDate: string;
    view: string;
    scenarioRatePct?: string;
  }) => Promise<ApiEnvelope<ProductCategoryPnlPayload>>;
};

type ApiClientOptions = {
  mode?: DataSourceMode;
  baseUrl?: string;
  fetchImpl?: typeof fetch;
};

type ApiClientProviderProps = {
  children: ReactNode;
  client?: ApiClient;
};

const defaultFetch = (...args: Parameters<typeof fetch>) => fetch(...args);

const delay = async () => new Promise((resolve) => setTimeout(resolve, 40));

const buildMockMeta = (resultKind: string): ResultMeta => ({
  trace_id: `mock_${resultKind}`,
  basis: "mock",
  result_kind: resultKind,
  formal_use_allowed: false,
  source_version: "sv_mock_dashboard_v2",
  vendor_version: "vv_none",
  rule_version: "rv_dashboard_mock_v2",
  cache_version: "cv_dashboard_mock_v2",
  quality_flag: "ok",
  scenario_flag: false,
  generated_at: "2026-04-09T10:30:00Z",
});

const buildMockApiEnvelope = <T>(
  resultKind: string,
  result: T,
  metaOverrides?: Partial<ResultMeta>,
): ApiEnvelope<T> => ({
  result_meta: { ...buildMockMeta(resultKind), ...metaOverrides },
  result,
});

/** Inline mock for `getSourceFoundation` in mock mode only (mirrors backend preview shape). */
const MOCK_SOURCE_FOUNDATION_SUMMARIES: SourcePreviewSummary[] = [
  {
    source_family: "tyw",
    report_date: "2025-12-31",
    source_file: "TYWLSHOW-20251231.xls",
    total_rows: 2395,
    manual_review_count: 18,
    source_version: "sv_mock_tyw_preview",
    rule_version: "rv_phase1_source_preview_v1",
    group_counts: {
      "回购类": 1060,
      "拆借类": 97,
      "存放类": 1238,
    },
  },
  {
    source_family: "zqtz",
    report_date: "2025-12-31",
    source_file: "ZQTZSHOW-20251231.xls",
    total_rows: 1724,
    manual_review_count: 0,
    source_version: "sv_mock_zqtz_preview",
    rule_version: "rv_phase1_source_preview_v1",
    group_counts: {
      "债券类": 1571,
      "基金类": 127,
      "特定目的载体及其他非标类": 26,
    },
  },
];

const MOCK_CHOICE_NEWS_EVENTS: ChoiceNewsEventsPayload["events"] = [
  {
    event_key: "ce_mock_001",
    received_at: "2026-04-10T09:01:00Z",
    group_id: "news_cmd1",
    content_type: "sectornews",
    serial_id: 1001,
    request_id: 501,
    error_code: 0,
    error_msg: "",
    topic_code: "S888010007API",
    item_index: 0,
    payload_text: "Macro data release calendar updated for CPI and industrial production.",
    payload_json: null,
  },
  {
    event_key: "ce_mock_002",
    received_at: "2026-04-10T08:58:00Z",
    group_id: "news_cmd1",
    content_type: "sectornews",
    serial_id: 1001,
    request_id: 501,
    error_code: 0,
    error_msg: "",
    topic_code: "C000003006",
    item_index: 0,
    payload_text: null,
    payload_json:
      "{\"headline\":\"Policy follow-up\",\"summary\":\"PBOC open-market operation commentary stream.\"}",
  },
  {
    event_key: "ce_mock_003",
    received_at: "2026-04-10T08:50:00Z",
    group_id: "news_cmd1",
    content_type: "sectornews",
    serial_id: 1002,
    request_id: 502,
    error_code: 101,
    error_msg: "vendor callback timeout",
    topic_code: "__callback__",
    item_index: -1,
    payload_text: null,
    payload_json: null,
  },
];

const MOCK_MACRO_FOUNDATION_PAYLOAD: MacroVendorPayload = {
  read_target: "duckdb",
  series: [
    {
      series_id: "M001",
      series_name: "公开市场7天逆回购利率",
      vendor_name: "choice",
      vendor_version: "vv_choice_catalog_v1",
      frequency: "daily",
      unit: "%",
    },
    {
      series_id: "M002",
      series_name: "DR007",
      vendor_name: "choice",
      vendor_version: "vv_choice_catalog_v1",
      frequency: "daily",
      unit: "%",
    },
    {
      series_id: "M003",
      series_name: "1年期国债到期收益率",
      vendor_name: "choice",
      vendor_version: "vv_choice_catalog_v1",
      frequency: "daily",
      unit: "%",
    },
  ],
};

const MOCK_CHOICE_MACRO_LATEST_PAYLOAD: ChoiceMacroLatestPayload = {
  read_target: "duckdb",
  series: [
    {
      series_id: "M001",
      series_name: "公开市场7天逆回购利率",
      trade_date: "2026-04-10",
      value_numeric: 1.75,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_20260410",
      vendor_series_code: "EDB_M001",
    },
    {
      series_id: "M002",
      series_name: "DR007",
      trade_date: "2026-04-10",
      value_numeric: 1.83,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_20260410",
    },
    {
      series_id: "M003",
      series_name: "1年期国债到期收益率",
      trade_date: "2026-04-10",
      value_numeric: 1.56,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_20260410",
    },
  ],
};

function buildMockSourcePreviewColumns(rows: Array<Record<string, unknown>>): SourcePreviewColumn[] {
  const firstRow = rows[0];
  if (!firstRow) {
    return [];
  }
  return Object.keys(firstRow).map((key) => ({
    key,
    label: buildMockSourcePreviewLabel(key),
    type: key === "row_locator" || key === "trace_step"
      ? "number"
      : key === "manual_review_needed"
        ? "boolean"
        : "string",
  }));
}

function buildMockSourcePreviewLabel(key: string) {
  const labels: Record<string, string> = {
    ingest_batch_id: "批次ID",
    row_locator: "行号",
    report_date: "报告日期",
    business_type_primary: "业务种类1",
    business_type_final: "业务种类2归类",
    asset_group: "资产分组",
    instrument_code: "债券代码",
    instrument_name: "债券名称",
    account_category: "账户类别",
    product_group: "产品分组",
    institution_category: "机构类型",
    special_nature: "特殊性质",
    counterparty_name: "对手方名称",
    investment_portfolio: "投资组合",
    manual_review_needed: "需人工复核",
    trace_step: "轨迹步骤",
    field_name: "字段名",
    field_value: "字段值",
    derived_label: "归类标签",
  };
  return labels[key] ?? key;
}

type ProductCategoryPnlMockOptions = {
  reportDate: string;
  view: string;
  scenarioRatePct?: string;
};

function reduceLatestManualAdjustments<
  T extends { adjustment_id: string; created_at: string }
>(records: T[]): T[] {
  const latestById = new Map<string, T>();
  for (const record of records) {
    const existing = latestById.get(record.adjustment_id);
    if (!existing || record.created_at >= existing.created_at) {
      latestById.set(record.adjustment_id, record);
    }
  }
  return Array.from(latestById.values());
}

function filterManualAdjustments<
  T extends {
    adjustment_id: string;
    created_at: string;
    account_code: string;
    approval_status: string;
    event_type: string;
  }
>(
  records: T[],
  options: ProductCategoryManualAdjustmentQuery = {},
  applyEventType = true,
): T[] {
  const adjustmentId = options.adjustmentId?.trim() ?? "";
  const adjustmentIdExact = options.adjustmentIdExact ?? false;
  const accountCode = options.accountCode?.trim() ?? "";
  const approvalStatus = options.approvalStatus?.trim() ?? "";
  const eventType = options.eventType?.trim() ?? "";
  const createdAtFrom = options.createdAtFrom?.trim() ?? "";
  const createdAtTo = options.createdAtTo?.trim() ?? "";

  return records.filter((record) => {
    if (adjustmentId) {
      if (adjustmentIdExact) {
        if (record.adjustment_id !== adjustmentId) {
          return false;
        }
      } else if (!record.adjustment_id.includes(adjustmentId)) {
        return false;
      }
    }
    if (accountCode && !record.account_code.includes(accountCode)) {
      return false;
    }
    if (approvalStatus && record.approval_status !== approvalStatus) {
      return false;
    }
    if (applyEventType && eventType && record.event_type !== eventType) {
      return false;
    }
    if (createdAtFrom && record.created_at < createdAtFrom) {
      return false;
    }
    if (createdAtTo && record.created_at > createdAtTo) {
      return false;
    }
    return true;
  });
}

function sortManualAdjustments<
  T extends {
    adjustment_id: string;
    created_at: string;
    account_code: string;
    approval_status: string;
    event_type: string;
  }
>(
  records: T[],
  field:
    | "created_at"
    | "adjustment_id"
    | "event_type"
    | "approval_status"
    | "account_code",
  direction: "asc" | "desc",
) {
  const sorted = [...records].sort((left, right) => {
    const leftValue = String(left[field] ?? "").toLowerCase();
    const rightValue = String(right[field] ?? "").toLowerCase();
    return leftValue.localeCompare(rightValue);
  });
  return direction === "desc" ? sorted.reverse() : sorted;
}

function buildManualAdjustmentSearchParams(
  reportDate: string,
  options: ProductCategoryManualAdjustmentQuery = {},
) {
  const params = new URLSearchParams({
    report_date: reportDate,
  });
  if (options.adjustmentId?.trim()) {
    params.set("adjustment_id", options.adjustmentId.trim());
  }
  if (options.adjustmentIdExact) {
    params.set("adjustment_id_exact", "true");
  }
  if (options.accountCode?.trim()) {
    params.set("account_code", options.accountCode.trim());
  }
  if (options.approvalStatus?.trim()) {
    params.set("approval_status", options.approvalStatus.trim());
  }
  if (options.eventType?.trim()) {
    params.set("event_type", options.eventType.trim());
  }
  if (options.currentSortField) {
    params.set("current_sort_field", options.currentSortField);
  }
  if (options.currentSortDir) {
    params.set("current_sort_dir", options.currentSortDir);
  }
  if (options.eventSortField) {
    params.set("event_sort_field", options.eventSortField);
  }
  if (options.eventSortDir) {
    params.set("event_sort_dir", options.eventSortDir);
  }
  if (options.createdAtFrom?.trim()) {
    params.set("created_at_from", options.createdAtFrom.trim());
  }
  if (options.createdAtTo?.trim()) {
    params.set("created_at_to", options.createdAtTo.trim());
  }
  if (options.adjustmentLimit !== undefined) {
    params.set("adjustment_limit", String(options.adjustmentLimit));
  }
  if (options.adjustmentOffset !== undefined) {
    params.set("adjustment_offset", String(options.adjustmentOffset));
  }
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  if (options.offset !== undefined) {
    params.set("offset", String(options.offset));
  }
  return params;
}

function buildMockProductCategoryPnlEnvelope(
  options: ProductCategoryPnlMockOptions,
): ApiEnvelope<ProductCategoryPnlPayload> {
  const scenarioRate = options.scenarioRatePct ?? null;
  const rows: ProductCategoryPnlRow[] = [
    {
      category_id: "interbank_lending_assets",
      category_name: "拆放同业",
      side: "asset",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "171.60",
      cny_scale: "156.91",
      foreign_scale: "14.69",
      cnx_cash: "0.33",
      cny_cash: "0.27",
      foreign_cash: "0.06",
      cny_ftp: scenarioRate ? "0.27" : "0.21",
      foreign_ftp: scenarioRate ? "0.03" : "0.02",
      cny_net: scenarioRate ? "0.00" : "0.05",
      foreign_net: scenarioRate ? "0.03" : "0.05",
      business_net_income: scenarioRate ? "0.03" : "0.10",
      weighted_yield: "2.50",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "repo_assets",
      category_name: "买入返售",
      side: "asset",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "230.11",
      cny_scale: "230.11",
      foreign_scale: "0.00",
      cnx_cash: "0.26",
      cny_cash: "0.26",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "0.39" : "0.31",
      foreign_ftp: "0.00",
      cny_net: scenarioRate ? "-0.13" : "-0.05",
      foreign_net: "0.00",
      business_net_income: scenarioRate ? "-0.13" : "-0.05",
      weighted_yield: "1.47",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "bond_investment",
      category_name: "债券投资",
      side: "asset",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "3361.78",
      cny_scale: "3305.70",
      foreign_scale: "56.08",
      cnx_cash: "6.79",
      cny_cash: "6.62",
      foreign_cash: "0.17",
      cny_ftp: scenarioRate ? "5.66" : "4.44",
      foreign_ftp: scenarioRate ? "0.10" : "0.08",
      cny_net: scenarioRate ? "0.96" : "2.18",
      foreign_net: scenarioRate ? "0.07" : "0.10",
      business_net_income: scenarioRate ? "1.03" : "2.27",
      weighted_yield: "2.63",
      is_total: false,
      children: ["bond_tpl", "bond_ac", "bond_ac_other", "bond_fvoci", "bond_valuation_spread"],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "bond_tpl",
      category_name: "TPL",
      side: "asset",
      level: 1,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "864.98",
      cny_scale: "865.79",
      foreign_scale: "-0.80",
      cnx_cash: "1.53",
      cny_cash: "1.51",
      foreign_cash: "0.02",
      cny_ftp: scenarioRate ? "1.48" : "1.16",
      foreign_ftp: scenarioRate ? "0.01" : "0.00",
      cny_net: scenarioRate ? "0.03" : "0.35",
      foreign_net: scenarioRate ? "0.01" : "0.02",
      business_net_income: scenarioRate ? "0.04" : "0.37",
      weighted_yield: "2.31",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "bond_ac",
      category_name: "AC债券投资",
      side: "asset",
      level: 1,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "1373.13",
      cny_scale: "1371.70",
      foreign_scale: "1.43",
      cnx_cash: "2.61",
      cny_cash: "2.60",
      foreign_cash: "0.01",
      cny_ftp: scenarioRate ? "2.35" : "1.84",
      foreign_ftp: scenarioRate ? "0.01" : "0.00",
      cny_net: scenarioRate ? "0.25" : "0.76",
      foreign_net: scenarioRate ? "0.00" : "0.01",
      business_net_income: scenarioRate ? "0.25" : "0.76",
      weighted_yield: "2.47",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "bond_ac_other",
      category_name: "AC其他投资",
      side: "asset",
      level: 1,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "58.04",
      cny_scale: "29.64",
      foreign_scale: "28.40",
      cnx_cash: "0.05",
      cny_cash: "0.05",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "0.05" : "0.04",
      foreign_ftp: scenarioRate ? "0.05" : "0.04",
      cny_net: scenarioRate ? "0.00" : "0.01",
      foreign_net: scenarioRate ? "-0.05" : "-0.04",
      business_net_income: scenarioRate ? "-0.05" : "-0.03",
      weighted_yield: "1.09",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "bond_fvoci",
      category_name: "FVOCI",
      side: "asset",
      level: 1,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "1065.63",
      cny_scale: "1038.57",
      foreign_scale: "27.05",
      cnx_cash: "2.10",
      cny_cash: "1.96",
      foreign_cash: "0.14",
      cny_ftp: scenarioRate ? "1.77" : "1.39",
      foreign_ftp: scenarioRate ? "0.05" : "0.04",
      cny_net: scenarioRate ? "0.19" : "0.56",
      foreign_net: scenarioRate ? "0.09" : "0.11",
      business_net_income: scenarioRate ? "0.28" : "0.67",
      weighted_yield: "2.57",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "bond_valuation_spread",
      category_name: "估值及买卖价差等",
      side: "asset",
      level: 1,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "0",
      cny_scale: "0",
      foreign_scale: "0",
      cnx_cash: "0.50",
      cny_cash: "0.50",
      foreign_cash: "0.00",
      cny_ftp: "0",
      foreign_ftp: "0",
      cny_net: "0.50",
      foreign_net: "0.00",
      business_net_income: "0.50",
      weighted_yield: null,
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "interest_earning_assets",
      category_name: "生息资产",
      side: "asset",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "2898.50",
      cny_scale: "2826.94",
      foreign_scale: "71.57",
      cnx_cash: "5.34",
      cny_cash: "5.13",
      foreign_cash: "0.22",
      cny_ftp: scenarioRate ? "4.85" : "3.80",
      foreign_ftp: scenarioRate ? "0.13" : "0.10",
      cny_net: scenarioRate ? "0.28" : "1.33",
      foreign_net: scenarioRate ? "0.09" : "0.12",
      business_net_income: scenarioRate ? "0.37" : "1.45",
      weighted_yield: "2.40",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "derivatives",
      category_name: "衍生品",
      side: "asset",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "0",
      cny_scale: "0",
      foreign_scale: "0",
      cnx_cash: "-0.01",
      cny_cash: "-0.01",
      foreign_cash: "0.00",
      cny_ftp: "0",
      foreign_ftp: "0",
      cny_net: "-0.01",
      foreign_net: "0.00",
      business_net_income: "-0.01",
      weighted_yield: null,
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "intermediate_business_income",
      category_name: "中间业务收入",
      side: "asset",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "0",
      cny_scale: "0",
      foreign_scale: "0",
      cnx_cash: "0.38",
      cny_cash: "0.38",
      foreign_cash: "0.00",
      cny_ftp: "0",
      foreign_ftp: "0",
      cny_net: "0.38",
      foreign_net: "0.00",
      business_net_income: "0.38",
      weighted_yield: null,
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "interbank_deposits",
      category_name: "同业存放",
      side: "liability",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "75.24",
      cny_scale: "75.73",
      foreign_scale: "0.49",
      cnx_cash: "0.07",
      cny_cash: "0.06",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "0.13" : "0.10",
      foreign_ftp: "0.00",
      cny_net: scenarioRate ? "-0.07" : "0.04",
      foreign_net: "0.00",
      business_net_income: scenarioRate ? "-0.07" : "0.03",
      weighted_yield: "1.18",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "interbank_borrowings",
      category_name: "同业拆入",
      side: "liability",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "424.48",
      cny_scale: "425.10",
      foreign_scale: "0.63",
      cnx_cash: "0.51",
      cny_cash: "0.51",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "0.72" : "0.57",
      foreign_ftp: "0.00",
      cny_net: scenarioRate ? "-0.21" : "0.06",
      foreign_net: "0.00",
      business_net_income: scenarioRate ? "-0.21" : "0.06",
      weighted_yield: "1.58",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "repo_liabilities",
      category_name: "卖出回购",
      side: "liability",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "197.03",
      cny_scale: "196.89",
      foreign_scale: "0.14",
      cnx_cash: "0.21",
      cny_cash: "0.21",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "0.33" : "0.26",
      foreign_ftp: "0.00",
      cny_net: scenarioRate ? "-0.12" : "0.05",
      foreign_net: "0.00",
      business_net_income: scenarioRate ? "-0.12" : "0.05",
      weighted_yield: "1.41",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "interbank_cds",
      category_name: "同业存单",
      side: "liability",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "1013.32",
      cny_scale: "1013.32",
      foreign_scale: "0.01",
      cnx_cash: "1.32",
      cny_cash: "1.32",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "1.74" : "1.36",
      foreign_ftp: "0.00",
      cny_net: scenarioRate ? "-0.42" : "0.04",
      foreign_net: "0.00",
      business_net_income: scenarioRate ? "-0.42" : "0.04",
      weighted_yield: "1.70",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
    {
      category_id: "credit_linked_notes",
      category_name: "信用联结票据",
      side: "liability",
      level: 0,
      view: options.view,
      report_date: options.reportDate,
      baseline_ftp_rate_pct: "1.75",
      cnx_scale: "18.51",
      cny_scale: "18.51",
      foreign_scale: "0.00",
      cnx_cash: "0.04",
      cny_cash: "0.04",
      foreign_cash: "0.00",
      cny_ftp: scenarioRate ? "0.03" : "0.02",
      foreign_ftp: "0.00",
      cny_net: scenarioRate ? "0.01" : "0.02",
      foreign_net: "0.00",
      business_net_income: scenarioRate ? "0.01" : "0.02",
      weighted_yield: "3.13",
      is_total: false,
      children: [],
      scenario_rate_pct: scenarioRate,
    },
  ];
  const assetTotal: ProductCategoryPnlRow = {
    category_id: "asset_total",
    category_name: "资产端合计",
    side: "asset",
    level: 0,
    view: options.view,
    report_date: options.reportDate,
    baseline_ftp_rate_pct: "1.75",
    cnx_scale: "3763.49",
    cny_scale: "3692.72",
    foreign_scale: "70.76",
    cnx_cash: "7.75",
    cny_cash: "7.51",
    foreign_cash: "0.24",
    cny_ftp: scenarioRate ? "6.32" : "4.96",
    foreign_ftp: scenarioRate ? "0.11" : "0.09",
    cny_net: scenarioRate ? "1.19" : "2.56",
    foreign_net: scenarioRate ? "0.13" : "0.14",
    business_net_income: scenarioRate ? "1.32" : "2.70",
    weighted_yield: "2.68",
    is_total: true,
    children: [],
    scenario_rate_pct: scenarioRate,
  };
  const liabilityTotal: ProductCategoryPnlRow = {
    category_id: "liability_total",
    category_name: "负债端合计",
    side: "liability",
    level: 0,
    view: options.view,
    report_date: options.reportDate,
    baseline_ftp_rate_pct: "1.75",
    cnx_scale: "1728.58",
    cny_scale: "1729.55",
    foreign_scale: "0.97",
    cnx_cash: "2.16",
    cny_cash: "2.16",
    foreign_cash: "0.00",
    cny_ftp: scenarioRate ? "2.96" : "2.32",
    foreign_ftp: "0.00",
    cny_net: scenarioRate ? "-0.80" : "0.16",
    foreign_net: "0.00",
    business_net_income: scenarioRate ? "-0.80" : "0.16",
    weighted_yield: "1.63",
    is_total: true,
    children: [],
    scenario_rate_pct: scenarioRate,
  };
  const grandTotal: ProductCategoryPnlRow = {
    category_id: "grand_total",
    category_name: "grand_total",
    side: "all",
    level: 0,
    view: options.view,
    report_date: options.reportDate,
    baseline_ftp_rate_pct: "1.75",
    cnx_scale: "0",
    cny_scale: "0",
    foreign_scale: "0",
    cnx_cash: "0",
    cny_cash: "0",
    foreign_cash: "0",
    cny_ftp: "0",
    foreign_ftp: "0",
    cny_net: "0",
    foreign_net: "0",
    business_net_income: scenarioRate ? "0.52" : "2.85",
    weighted_yield: null,
    is_total: true,
    children: [],
    scenario_rate_pct: scenarioRate,
  };
  const assetRows = rows.filter((row) => row.side === "asset");
  const liabilityRows = rows.filter((row) => row.side === "liability");

  return buildMockApiEnvelope(
    "product_category_pnl.detail",
    {
      report_date: options.reportDate,
      view: options.view,
      available_views: ["monthly", "qtd", "ytd", "year_to_report_month_end"],
      scenario_rate_pct: scenarioRate,
      rows: [...assetRows, assetTotal, ...liabilityRows, liabilityTotal, grandTotal],
      asset_total: assetTotal,
      liability_total: liabilityTotal,
      grand_total: grandTotal,
    },
    {
      basis: scenarioRate ? "scenario" : "formal",
      formal_use_allowed: !scenarioRate,
      scenario_flag: Boolean(scenarioRate),
    },
  );
}

function buildMockChoiceNewsEnvelope(options: {
  limit: number;
  offset: number;
  groupId?: string;
  topicCode?: string;
  errorOnly?: boolean;
  receivedFrom?: string;
  receivedTo?: string;
}): ApiEnvelope<ChoiceNewsEventsPayload> {
  const filtered = MOCK_CHOICE_NEWS_EVENTS.filter((event) => {
    if (options.groupId?.trim() && event.group_id !== options.groupId.trim()) {
      return false;
    }
    if (options.topicCode?.trim() && event.topic_code !== options.topicCode.trim()) {
      return false;
    }
    if (options.errorOnly && event.error_code === 0) {
      return false;
    }
    if (options.receivedFrom?.trim() && event.received_at < options.receivedFrom.trim()) {
      return false;
    }
    if (options.receivedTo?.trim() && event.received_at > options.receivedTo.trim()) {
      return false;
    }
    return true;
  });

  return buildMockApiEnvelope("news.choice.latest", {
    total_rows: filtered.length,
    limit: options.limit,
    offset: options.offset,
    events: filtered.slice(options.offset, options.offset + options.limit),
  });
}

const buildPhase1PnlDisabledResponse = (): FormalPnlDisabledResponse => ({
  enabled: false as const,
  phase: "phase1" as const,
  detail: "Formal /api/pnl endpoints are planned but disabled in Phase 1.",
});

const normalizeBaseUrl = (value?: string) =>
  value ? value.replace(/\/$/, "") : "";

const parseEnvMode = (): DataSourceMode => {
  const envValue = import.meta.env.VITE_DATA_SOURCE;
  return envValue === "real" ? "real" : "mock";
};

const parseBaseUrl = () => normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);

function extractApiErrorDetail(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const body = payload as Record<string, unknown>;
  const errMsg = body.error_message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    return errMsg;
  }
  const detail = body.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (typeof item === "string") {
        return item;
      }
      if (item && typeof item === "object" && "msg" in item) {
        return String((item as { msg: unknown }).msg);
      }
      try {
        return JSON.stringify(item);
      } catch {
        return String(item);
      }
    });
    const joined = parts.filter((p) => p.trim()).join("; ");
    return joined || undefined;
  }
  return undefined;
}

const requestJson = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
): Promise<ApiEnvelope<T>> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as ApiEnvelope<T>;
};

const requestActionJson = async <T>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail: string | undefined;
    try {
      detail = extractApiErrorDetail(await response.json());
    } catch {
      detail = undefined;
    }
    throw new Error(detail ?? `Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as T;
};

const requestText = async (
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
): Promise<{ content: string; filename: string }> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept: "text/csv, text/plain;q=0.9, */*;q=0.8",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  const contentDisposition = response.headers.get("Content-Disposition") ?? "";
  const filenameMatch = /filename=\"?([^\";]+)\"?/i.exec(contentDisposition);
  return {
    content: await response.text(),
    filename: filenameMatch?.[1] ?? "product-category-audit.csv",
  };
};

const requestActionWithBody = async <TResponse, TBody>(
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  body: TBody,
): Promise<TResponse> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as TResponse;
};

const requestPhase1Disabled = async (
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<FormalPnlDisabledResponse> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (response.status !== 503) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return (await response.json()) as FormalPnlDisabledResponse;
};

export function createApiClient(options: ApiClientOptions = {}): ApiClient {
  const mode = options.mode ?? parseEnvMode();
  const baseUrl = normalizeBaseUrl(options.baseUrl ?? parseBaseUrl());
  const fetchImpl = options.fetchImpl ?? defaultFetch;
  const mockManualAdjustments: ProductCategoryManualAdjustmentPayload[] = [];
  let mockManualAdjustmentSeq = 0;

  const mockClient: ApiClient = {
    mode: "mock",
    async getHealth() {
      await delay();
      return { status: "ok" };
    },
    async getOverview() {
      await delay();
      return buildMockApiEnvelope("executive.overview", overviewPayload);
    },
    async getSummary() {
      await delay();
      return buildMockApiEnvelope("executive.summary", summaryPayload);
    },
    async getFormalPnlDates() {
      await delay();
      return buildPhase1PnlDisabledResponse();
    },
    async getFormalPnlData(date: string) {
      void date;
      await delay();
      return buildPhase1PnlDisabledResponse();
    },
    async getFormalPnlOverview(reportDate: string) {
      void reportDate;
      await delay();
      return buildPhase1PnlDisabledResponse();
    },
    async refreshFormalPnl() {
      await delay();
      return {
        status: "queued",
        run_id: "pnl_materialize:mock-run",
        job_name: "pnl_materialize",
        trigger_mode: "async",
        cache_key: "pnl.phase2.materialize",
        report_date: "2026-02-28",
      };
    },
    async getFormalPnlImportStatus(runId?: string) {
      await delay();
      return {
        status: runId ? "completed" : "idle",
        run_id: runId ?? "pnl_materialize:mock-run",
        job_name: "pnl_materialize",
        trigger_mode: runId ? "terminal" : "idle",
        cache_key: "pnl.phase2.materialize",
        report_date: "2026-02-28",
        source_version: "sv_mock_dashboard_v2",
      };
    },
    async getPnlAttribution() {
      await delay();
      return buildMockApiEnvelope("executive.pnl-attribution", pnlAttributionPayload);
    },
    async getRiskOverview() {
      await delay();
      return buildMockApiEnvelope("executive.risk-overview", riskOverviewPayload);
    },
    async getContribution() {
      await delay();
      return buildMockApiEnvelope("executive.contribution", contributionPayload);
    },
    async getAlerts() {
      await delay();
      return buildMockApiEnvelope("executive.alerts", alertsPayload);
    },
    async getPlaceholderSnapshot(key: string) {
      await delay();
      return buildMockApiEnvelope(
        `workbench.${key}`,
        placeholderSnapshots[key] ?? placeholderSnapshots.dashboard,
      );
    },
    async getSourceFoundation() {
      await delay();
      return buildMockApiEnvelope("preview.source-foundation", {
        sources: MOCK_SOURCE_FOUNDATION_SUMMARIES,
      });
    },
    async refreshSourcePreview() {
      await delay();
      return {
        status: "queued",
        run_id: "source_preview_refresh:mock-run",
        job_name: "source_preview_refresh",
        trigger_mode: "async",
        cache_key: "source_preview.foundation",
        preview_sources: ["zqtz", "tyw"],
      };
    },
    async getSourcePreviewRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "source_preview_refresh",
        trigger_mode: "terminal",
        cache_key: "source_preview.foundation",
        preview_sources: ["zqtz", "tyw"],
        ingest_batch_id: "ib_mock_preview",
        source_version: "sv_mock_preview_refresh",
      };
    },
    async getSourceFoundationHistory({ sourceFamily, limit, offset }) {
      await delay();
      const rows = sourceFamily
        ? MOCK_SOURCE_FOUNDATION_SUMMARIES.filter(
            (summary) => summary.source_family === sourceFamily,
          )
        : MOCK_SOURCE_FOUNDATION_SUMMARIES;
      return buildMockApiEnvelope("preview.source-foundation.history", {
        limit,
        offset,
        total_rows: rows.length,
        rows: rows.slice(offset, offset + limit),
      });
    },
    async getSourceFoundationRows({ sourceFamily, ingestBatchId, limit, offset }) {
      await delay();
      const rows =
        sourceFamily === "zqtz"
          ? [
              {
                ingest_batch_id: ingestBatchId,
                row_locator: 1,
                report_date: "2025-12-31",
                business_type_primary: "其他债券",
                business_type_final: "公募基金",
                asset_group: "基金类",
                instrument_code: "SA0001",
                instrument_name: "MOCK-ZQTZ",
                account_category: "银行账户",
                manual_review_needed: false,
              },
            ]
          : [
              {
                ingest_batch_id: ingestBatchId,
                row_locator: 1,
                report_date: "2025-12-31",
                business_type_primary: "同业拆入",
                product_group: "拆借类",
                institution_category: "bank",
                special_nature: "普通",
                counterparty_name: "MOCK-TYW",
                investment_portfolio: "拆借自营",
                manual_review_needed: false,
              },
            ];
      return buildMockApiEnvelope(`preview.${sourceFamily}.rows`, {
        source_family: sourceFamily,
        ingest_batch_id: ingestBatchId,
        limit,
        offset,
        total_rows: rows.length,
        columns: buildMockSourcePreviewColumns(rows),
        rows,
      });
    },
    async getSourceFoundationTraces({ sourceFamily, ingestBatchId, limit, offset }) {
      await delay();
      const rows = [
        {
          ingest_batch_id: ingestBatchId,
          row_locator: 1,
          trace_step: 1,
          field_name: sourceFamily === "zqtz" ? "业务种类1" : "产品类型",
          field_value: sourceFamily === "zqtz" ? "其他债券" : "同业拆入",
          derived_label: sourceFamily === "zqtz" ? "公募基金" : "拆借类",
          manual_review_needed: false,
        },
      ];
      return buildMockApiEnvelope(`preview.${sourceFamily}.traces`, {
        source_family: sourceFamily,
        ingest_batch_id: ingestBatchId,
        limit,
        offset,
        total_rows: rows.length,
        columns: buildMockSourcePreviewColumns(rows),
        rows,
      });
    },
    async getMacroFoundation() {
      await delay();
      return buildMockApiEnvelope(
        "preview.macro-foundation",
        MOCK_MACRO_FOUNDATION_PAYLOAD,
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_macro_vendor_mock",
          vendor_version: "vv_choice_catalog_v1",
          rule_version: "rv_phase1_macro_vendor_v1",
          cache_version: "cv_phase1_macro_vendor_v1",
        },
      );
    },
    async getChoiceMacroLatest() {
      await delay();
      return buildMockApiEnvelope(
        "macro.choice.latest",
        MOCK_CHOICE_MACRO_LATEST_PAYLOAD,
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_choice_macro_mock",
          vendor_version: "vv_choice_macro_20260410",
          rule_version: "rv_choice_macro_thin_slice_v1",
          cache_version: "cv_choice_macro_thin_slice_v1",
        },
      );
    },
    async getChoiceNewsEvents(options) {
      await delay();
      return buildMockChoiceNewsEnvelope(options);
    },
    async getProductCategoryDates() {
      await delay();
      return buildMockApiEnvelope(
        "product_category_pnl.dates",
        {
          report_dates: ["2026-02-28", "2026-01-31"],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async refreshProductCategoryPnl() {
      await delay();
      return {
        status: "queued",
        run_id: "product_category_pnl:mock-run",
        job_name: "product_category_pnl",
        trigger_mode: "async",
        cache_key: "product_category_pnl.formal",
      };
    },
    async getProductCategoryRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "product_category_pnl",
        trigger_mode: "async",
        cache_key: "product_category_pnl.formal",
        month_count: 2,
        report_dates: ["2026-01-31", "2026-02-28"],
        rule_version: "rv_product_category_pnl_v1",
        source_version: "sv_mock_dashboard_v2",
      };
    },
    async createProductCategoryManualAdjustment(payload) {
      await delay();
      mockManualAdjustmentSeq += 1;
      const record = {
        adjustment_id: `pca-mock-${mockManualAdjustmentSeq}`,
        event_type: "created",
        created_at: "2026-04-10T09:30:00Z",
        stream: "product_category_pnl_adjustments",
        report_date: payload.report_date,
        operator: payload.operator,
        approval_status: payload.approval_status,
        account_code: payload.account_code,
        currency: payload.currency,
        account_name: payload.account_name ?? "",
        beginning_balance: payload.beginning_balance ?? null,
        ending_balance: payload.ending_balance ?? null,
        monthly_pnl: payload.monthly_pnl ?? null,
        daily_avg_balance: payload.daily_avg_balance ?? null,
        annual_avg_balance: payload.annual_avg_balance ?? null,
      };
      mockManualAdjustments.unshift(record);
      return record;
    },
    async getProductCategoryManualAdjustments(reportDate, options = {}) {
      await delay();
      const allEvents = mockManualAdjustments.filter(
        (item) => item.report_date === reportDate,
      );
      const events = sortManualAdjustments(
        filterManualAdjustments(allEvents, options, true),
        options.eventSortField ?? "created_at",
        options.eventSortDir ?? "desc",
      );
      const limit = options.limit ?? 20;
      const offset = options.offset ?? 0;
      const adjustmentLimit = options.adjustmentLimit ?? 20;
      const adjustmentOffset = options.adjustmentOffset ?? 0;
      const pagedEvents = events.slice(offset, offset + limit);
      const adjustments = sortManualAdjustments(
        filterManualAdjustments(reduceLatestManualAdjustments(allEvents), options, false),
        options.currentSortField ?? "created_at",
        options.currentSortDir ?? "desc",
      );
      return {
        report_date: reportDate,
        adjustment_count: adjustments.length,
        adjustment_limit: adjustmentLimit,
        adjustment_offset: adjustmentOffset,
        event_total: events.length,
        event_limit: limit,
        event_offset: offset,
        adjustments: adjustments.slice(
          adjustmentOffset,
          adjustmentOffset + adjustmentLimit,
        ),
        events: pagedEvents,
      };
    },
    async exportProductCategoryManualAdjustmentsCsv(reportDate, options = {}) {
      await delay();
      const allEvents = mockManualAdjustments.filter(
        (item) => item.report_date === reportDate,
      );
      const filteredEvents = sortManualAdjustments(
        filterManualAdjustments(allEvents, options, true),
        options.eventSortField ?? "created_at",
        options.eventSortDir ?? "desc",
      );
      const filteredAdjustments = sortManualAdjustments(
        filterManualAdjustments(reduceLatestManualAdjustments(allEvents), options, false),
        options.currentSortField ?? "created_at",
        options.currentSortDir ?? "desc",
      );
      const headers = [
        "adjustment_id",
        "event_type",
        "created_at",
        "report_date",
        "operator",
        "approval_status",
        "account_code",
        "currency",
        "account_name",
      ];
      const toCsv = (rows: ProductCategoryManualAdjustmentPayload[]) =>
        rows
          .map((row) =>
            headers
              .map((header) => {
                const value = String(
                  (row as Record<string, string | number | null | undefined>)[header] ?? "",
                ).replace(/"/g, '""');
                return `"${value}"`;
              })
              .join(","),
          )
          .join("\n");
      return {
        filename: `product-category-audit-${reportDate}.csv`,
        content: [
          "Current State",
          headers.join(","),
          toCsv(filteredAdjustments),
          "",
          "Event Timeline",
          headers.join(","),
          toCsv(filteredEvents),
        ].join("\n"),
      };
    },
    async updateProductCategoryManualAdjustment(adjustmentId, payload) {
      await delay();
      const index = mockManualAdjustments.findIndex(
        (item) => item.adjustment_id === adjustmentId,
      );
      if (index === -1) {
        throw new Error(`Unknown adjustment: ${adjustmentId}`);
      }
      const updated = {
        ...mockManualAdjustments[index],
        ...payload,
        event_type: "edited",
        created_at: "2026-04-10T09:40:00Z",
      };
      mockManualAdjustments.unshift(updated);
      return updated;
    },
    async revokeProductCategoryManualAdjustment(adjustmentId) {
      await delay();
      const index = mockManualAdjustments.findIndex(
        (item) => item.adjustment_id === adjustmentId,
      );
      if (index === -1) {
        throw new Error(`Unknown adjustment: ${adjustmentId}`);
      }
      const revoked = {
        ...mockManualAdjustments[index],
        event_type: "revoked",
        approval_status: "rejected",
        created_at: "2026-04-10T09:45:00Z",
      };
      mockManualAdjustments.unshift(revoked);
      return revoked;
    },
    async restoreProductCategoryManualAdjustment(adjustmentId) {
      await delay();
      const index = mockManualAdjustments.findIndex(
        (item) => item.adjustment_id === adjustmentId,
      );
      if (index === -1) {
        throw new Error(`Unknown adjustment: ${adjustmentId}`);
      }
      const restored = {
        ...mockManualAdjustments[index],
        event_type: "restored",
        approval_status: "approved",
        created_at: "2026-04-10T09:50:00Z",
      };
      mockManualAdjustments.unshift(restored);
      return restored;
    },
    async getProductCategoryPnl(options) {
      await delay();
      return buildMockProductCategoryPnlEnvelope(options);
    },
  };

  if (mode === "mock") {
    return mockClient;
  }

  return {
    mode,
    async getHealth() {
      const response = await fetchImpl(`${baseUrl}/health/ready`, {
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        throw new Error(`Request failed: /health/ready (${response.status})`);
      }

      return (await response.json()) as HealthResponse;
    },
    getOverview: () =>
      requestJson<OverviewPayload>(fetchImpl, baseUrl, "/ui/home/overview"),
    getSummary: () =>
      requestJson<SummaryPayload>(fetchImpl, baseUrl, "/ui/home/summary"),
    getFormalPnlDates: () =>
      requestPhase1Disabled(fetchImpl, baseUrl, "/api/pnl/dates"),
    getFormalPnlData: (date: string) =>
      requestPhase1Disabled(
        fetchImpl,
        baseUrl,
        `/api/pnl/data?date=${encodeURIComponent(date)}`,
      ),
    getFormalPnlOverview: (reportDate: string) =>
      requestPhase1Disabled(
        fetchImpl,
        baseUrl,
        `/api/pnl/overview?report_date=${encodeURIComponent(reportDate)}`,
      ),
    refreshFormalPnl: () =>
      requestActionJson<FormalPnlRefreshPayload>(fetchImpl, baseUrl, "/api/data/refresh_pnl", {
        method: "POST",
      }),
    getFormalPnlImportStatus: (runId?: string) =>
      requestActionJson<FormalPnlRefreshPayload>(
        fetchImpl,
        baseUrl,
        runId
          ? `/api/data/import_status/pnl?run_id=${encodeURIComponent(runId)}`
          : "/api/data/import_status/pnl",
      ),
    getPnlAttribution: () =>
      requestJson<PnlAttributionPayload>(
        fetchImpl,
        baseUrl,
        "/ui/pnl/attribution",
      ),
    getRiskOverview: () =>
      requestJson<RiskOverviewPayload>(
        fetchImpl,
        baseUrl,
        "/ui/risk/overview",
      ),
    getContribution: () =>
      requestJson<ContributionPayload>(
        fetchImpl,
        baseUrl,
        "/ui/home/contribution",
      ),
    getAlerts: () =>
      requestJson<AlertsPayload>(fetchImpl, baseUrl, "/ui/home/alerts"),
    getPlaceholderSnapshot: mockClient.getPlaceholderSnapshot,
    getSourceFoundation: () =>
      requestJson<SourcePreviewPayload>(
        fetchImpl,
        baseUrl,
        "/ui/preview/source-foundation",
      ),
    refreshSourcePreview: () =>
      requestActionJson<SourcePreviewRefreshPayload>(
        fetchImpl,
        baseUrl,
        "/ui/preview/source-foundation/refresh",
        {
          method: "POST",
        },
      ),
    getSourcePreviewRefreshStatus: (runId: string) =>
      requestActionJson<SourcePreviewRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    getSourceFoundationHistory: ({ sourceFamily, limit, offset }) => {
      const params = new URLSearchParams();
      if (sourceFamily?.trim()) {
        params.set("source_family", sourceFamily);
      }
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      return requestJson<SourcePreviewHistoryPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/history?${params.toString()}`,
      );
    },
    getSourceFoundationRows: ({ sourceFamily, ingestBatchId, limit, offset }) =>
      requestJson<SourcePreviewRowsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/${encodeURIComponent(sourceFamily)}/rows?ingest_batch_id=${encodeURIComponent(ingestBatchId)}&limit=${limit}&offset=${offset}`,
      ),
    getSourceFoundationTraces: ({ sourceFamily, ingestBatchId, limit, offset }) =>
      requestJson<SourcePreviewTracesPayload>(
        fetchImpl,
        baseUrl,
        `/ui/preview/source-foundation/${encodeURIComponent(sourceFamily)}/traces?ingest_batch_id=${encodeURIComponent(ingestBatchId)}&limit=${limit}&offset=${offset}`,
      ),
    getMacroFoundation: () =>
      requestJson<MacroVendorPayload>(
        fetchImpl,
        baseUrl,
        "/ui/preview/macro-foundation",
      ),
    getChoiceMacroLatest: () =>
      requestJson<ChoiceMacroLatestPayload>(
        fetchImpl,
        baseUrl,
        "/ui/macro/choice-series/latest",
      ),
    getChoiceNewsEvents: ({
      limit,
      offset,
      groupId,
      topicCode,
      errorOnly,
      receivedFrom,
      receivedTo,
    }) => {
      const params = new URLSearchParams();
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      if (groupId?.trim()) {
        params.set("group_id", groupId.trim());
      }
      if (topicCode?.trim()) {
        params.set("topic_code", topicCode.trim());
      }
      if (errorOnly) {
        params.set("error_only", "true");
      }
      if (receivedFrom?.trim()) {
        params.set("received_from", receivedFrom.trim());
      }
      if (receivedTo?.trim()) {
        params.set("received_to", receivedTo.trim());
      }
      return requestJson<ChoiceNewsEventsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/news/choice-events/latest?${params.toString()}`,
      );
    },
    getProductCategoryDates: () =>
      requestJson<ProductCategoryDatesPayload>(
        fetchImpl,
        baseUrl,
        "/ui/pnl/product-category/dates",
      ),
    refreshProductCategoryPnl: () =>
      requestActionJson<ProductCategoryRefreshPayload>(
        fetchImpl,
        baseUrl,
        "/ui/pnl/product-category/refresh",
        {
          method: "POST",
        },
      ),
    getProductCategoryRefreshStatus: (runId: string) =>
      requestActionJson<ProductCategoryRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    createProductCategoryManualAdjustment: (payload) =>
      requestActionWithBody<
        ProductCategoryManualAdjustmentPayload,
        ProductCategoryManualAdjustmentRequest
      >(
        fetchImpl,
        baseUrl,
        "/ui/pnl/product-category/manual-adjustments",
        payload,
      ),
    getProductCategoryManualAdjustments: (reportDate, options = {}) => {
      const params = buildManualAdjustmentSearchParams(reportDate, options);
      return requestActionJson<ProductCategoryManualAdjustmentListPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments?${params.toString()}`,
      );
    },
    exportProductCategoryManualAdjustmentsCsv: (reportDate, options = {}) => {
      const params = buildManualAdjustmentSearchParams(reportDate, options);
      return requestText(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/export?${params.toString()}`,
      );
    },
    updateProductCategoryManualAdjustment: (adjustmentId, payload) =>
      requestActionWithBody<
        ProductCategoryManualAdjustmentPayload,
        ProductCategoryManualAdjustmentRequest
      >(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/${encodeURIComponent(adjustmentId)}/edit`,
        payload,
      ),
    revokeProductCategoryManualAdjustment: (adjustmentId) =>
      requestActionJson<ProductCategoryManualAdjustmentPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/${encodeURIComponent(adjustmentId)}/revoke`,
        {
          method: "POST",
        },
      ),
    restoreProductCategoryManualAdjustment: (adjustmentId) =>
      requestActionJson<ProductCategoryManualAdjustmentPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category/manual-adjustments/${encodeURIComponent(adjustmentId)}/restore`,
        {
          method: "POST",
        },
      ),
    getProductCategoryPnl: ({ reportDate, view, scenarioRatePct }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        view,
      });
      if (scenarioRatePct?.trim()) {
        params.set("scenario_rate_pct", scenarioRatePct);
      }
      return requestJson<ProductCategoryPnlPayload>(
        fetchImpl,
        baseUrl,
        `/ui/pnl/product-category?${params.toString()}`,
      );
    },
  };
}

const ApiClientContext = createContext<ApiClient | null>(null);

export function ApiClientProvider({
  children,
  client,
}: ApiClientProviderProps) {
  const resolvedClient = useMemo(
    () => client ?? createApiClient(),
    [client],
  );

  return createElement(
    ApiClientContext.Provider,
    { value: resolvedClient },
    children,
  );
}

export function useApiClient(): ApiClient {
  const client = useContext(ApiClientContext);

  if (!client) {
    throw new Error("ApiClientProvider is missing");
  }

  return client;
}
