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
  BalanceAnalysisCurrentUserPayload,
  BalanceAnalysisDecisionItemsPayload,
  BalanceAnalysisDecisionStatus,
  BalanceAnalysisDecisionStatusRecord,
  BalanceAnalysisOverviewPayload,
  BalanceAnalysisDatesPayload,
  BalanceCurrencyBasis,
  BalanceAnalysisPayload,
  BalanceAnalysisWorkbookPayload,
  BalancePositionScope,
  BalanceAnalysisRefreshPayload,
  BondAnalyticsRefreshPayload,
  BalanceAnalysisSummaryExportPayload,
  BalanceAnalysisWorkbookExportPayload,
  BalanceAnalysisSummaryTablePayload,
  BalanceAnalysisTableRow,
  ChoiceMacroLatestPayload,
  ChoiceNewsEventsPayload,
  ContributionPayload,
  FormalPnlRefreshPayload,
  HealthResponse,
  MacroVendorPayload,
  OverviewPayload,
  PnlBridgePayload,
  PnlDataPayload,
  PnlDatesPayload,
  PnlOverviewPayload,
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
  RiskTensorPayload,
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
  getFormalPnlDates: () => Promise<ApiEnvelope<PnlDatesPayload>>;
  getFormalPnlData: (date: string) => Promise<ApiEnvelope<PnlDataPayload>>;
  getFormalPnlOverview: (reportDate: string) => Promise<ApiEnvelope<PnlOverviewPayload>>;
  getPnlBridge: (reportDate: string) => Promise<ApiEnvelope<PnlBridgePayload>>;
  refreshFormalPnl: () => Promise<FormalPnlRefreshPayload>;
  getFormalPnlImportStatus: (runId?: string) => Promise<FormalPnlRefreshPayload>;
  getPnlAttribution: () => Promise<ApiEnvelope<PnlAttributionPayload>>;
  getRiskOverview: () => Promise<ApiEnvelope<RiskOverviewPayload>>;
  getRiskTensor: (reportDate: string) => Promise<ApiEnvelope<RiskTensorPayload>>;
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
  getBalanceAnalysisDates: () => Promise<ApiEnvelope<BalanceAnalysisDatesPayload>>;
  getBalanceAnalysisOverview: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<ApiEnvelope<BalanceAnalysisOverviewPayload>>;
  getBalanceAnalysisSummary: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
    limit: number;
    offset: number;
  }) => Promise<ApiEnvelope<BalanceAnalysisSummaryTablePayload>>;
  getBalanceAnalysisWorkbook: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<ApiEnvelope<BalanceAnalysisWorkbookPayload>>;
  getBalanceAnalysisCurrentUser: () => Promise<BalanceAnalysisCurrentUserPayload>;
  getBalanceAnalysisDecisionItems: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<ApiEnvelope<BalanceAnalysisDecisionItemsPayload>>;
  updateBalanceAnalysisDecisionStatus: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
    decisionKey: string;
    status: BalanceAnalysisDecisionStatus;
    comment?: string;
  }) => Promise<BalanceAnalysisDecisionStatusRecord>;
  getBalanceAnalysisDetail: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<ApiEnvelope<BalanceAnalysisPayload>>;
  exportBalanceAnalysisSummaryCsv: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<BalanceAnalysisSummaryExportPayload>;
  exportBalanceAnalysisWorkbookXlsx: (options: {
    reportDate: string;
    positionScope: BalancePositionScope;
    currencyBasis: BalanceCurrencyBasis;
  }) => Promise<BalanceAnalysisWorkbookExportPayload>;
  refreshBalanceAnalysis: (reportDate: string) => Promise<BalanceAnalysisRefreshPayload>;
  getBalanceAnalysisRefreshStatus: (
    runId: string,
  ) => Promise<BalanceAnalysisRefreshPayload>;
  refreshBondAnalytics: (reportDate: string) => Promise<BondAnalyticsRefreshPayload>;
  getBondAnalyticsRefreshStatus: (
    runId: string,
  ) => Promise<BondAnalyticsRefreshPayload>;
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
  vendor_status: "ok",
  fallback_mode: "none",
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
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "main refresh date-slice lane",
    },
    {
      series_id: "M002",
      series_name: "DR007",
      vendor_name: "choice",
      vendor_version: "vv_choice_catalog_v1",
      frequency: "daily",
      unit: "%",
      refresh_tier: "fallback",
      fetch_mode: "latest",
      fetch_granularity: "single",
      policy_note: "low-frequency latest-only lane",
    },
    {
      series_id: "M003",
      series_name: "1年期国债到期收益率",
      vendor_name: "choice",
      vendor_version: "vv_choice_catalog_v1",
      frequency: "daily",
      unit: "%",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "main refresh date-slice lane",
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
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "main refresh date-slice lane",
    },
    {
      series_id: "M002",
      series_name: "DR007",
      trade_date: "2026-04-10",
      value_numeric: 1.83,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_20260410",
      refresh_tier: "fallback",
      fetch_mode: "latest",
      fetch_granularity: "single",
      policy_note: "low-frequency latest-only lane",
    },
    {
      series_id: "M003",
      series_name: "1年期国债到期收益率",
      trade_date: "2026-04-10",
      value_numeric: 1.56,
      unit: "%",
      source_version: "sv_choice_macro_mock",
      vendor_version: "vv_choice_macro_20260410",
      refresh_tier: "stable",
      fetch_mode: "date_slice",
      fetch_granularity: "batch",
      policy_note: "main refresh date-slice lane",
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

const normalizeBaseUrl = (value?: string) =>
  value ? value.replace(/\/$/, "") : "";

const parseEnvMode = (): DataSourceMode => {
  const envValue = import.meta.env.VITE_DATA_SOURCE;
  return envValue === "real" ? "real" : "mock";
};

const parseBaseUrl = () => normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);

function buildMockBalanceAnalysisTableRows(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): BalanceAnalysisTableRow[] {
  const rows: BalanceAnalysisTableRow[] = [
    {
      row_key: "zqtz:240001.IB:portfolio-a:cc-1:CNY:asset:A:FVOCI",
      source_family: "zqtz",
      display_name: "240001.IB",
      owner_name: "利率债组合",
      category_name: "交易账户",
      position_scope: "asset",
      currency_basis: "CNY",
      invest_type_std: "A",
      accounting_basis: "FVOCI",
      detail_row_count: 3,
      market_value_amount: "720.00",
      amortized_cost_amount: "648.00",
      accrued_interest_amount: "36.00",
    },
    {
      row_key: "tyw:repo-1:CNY:liability:H:AC",
      source_family: "tyw",
      display_name: "repo-1",
      owner_name: "同业负债池",
      category_name: "卖出回购",
      position_scope: "liability",
      currency_basis: "CNY",
      invest_type_std: "H",
      accounting_basis: "AC",
      detail_row_count: 1,
      market_value_amount: "72.00",
      amortized_cost_amount: "72.00",
      accrued_interest_amount: "14.40",
    },
    {
      row_key: "zqtz:240002.IB:portfolio-b:cc-2:CNY:asset:H:AC",
      source_family: "zqtz",
      display_name: "240002.IB",
      owner_name: "高等级组合",
      category_name: "摊余成本",
      position_scope: "asset",
      currency_basis: "CNY",
      invest_type_std: "H",
      accounting_basis: "AC",
      detail_row_count: 2,
      market_value_amount: "410.00",
      amortized_cost_amount: "403.00",
      accrued_interest_amount: "20.00",
    },
  ];
  return rows.filter((row) => {
    const matchesScope = positionScope === "all" || row.position_scope === positionScope;
    const matchesBasis = row.currency_basis === currencyBasis;
    return matchesScope && matchesBasis;
  });
}

function buildMockBalanceAnalysisSummaryTable(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
  limit: number,
  offset: number,
): ApiEnvelope<BalanceAnalysisSummaryTablePayload> {
  const rows = buildMockBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis);
  return buildMockApiEnvelope(
    "balance-analysis.summary",
    {
      report_date: reportDate,
      position_scope: positionScope,
      currency_basis: currencyBasis,
      limit,
      offset,
      total_rows: rows.length,
      rows: rows.slice(offset, offset + limit),
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_balance_mock",
      rule_version: "rv_balance_analysis_formal_materialize_v1",
      cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
    },
  );
}

function buildMockBalanceAnalysisSummaryCsv(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): BalanceAnalysisSummaryExportPayload {
  const rows = buildMockBalanceAnalysisTableRows(reportDate, positionScope, currencyBasis);
  const headers = [
    "row_key",
    "source_family",
    "display_name",
    "owner_name",
    "category_name",
    "position_scope",
    "currency_basis",
    "invest_type_std",
    "accounting_basis",
    "detail_row_count",
    "market_value_amount",
    "amortized_cost_amount",
    "accrued_interest_amount",
    "report_date",
    "source_version",
    "rule_version",
  ];
  const lines = rows.map((row) =>
    [
      row.row_key,
      row.source_family,
      row.display_name,
      row.owner_name,
      row.category_name,
      row.position_scope,
      row.currency_basis,
      row.invest_type_std,
      row.accounting_basis,
      String(row.detail_row_count),
      String(row.market_value_amount),
      String(row.amortized_cost_amount),
      String(row.accrued_interest_amount),
      reportDate,
      "sv_balance_mock",
      "rv_balance_analysis_formal_materialize_v1",
    ].join(","),
  );
  return {
    filename: `balance-analysis-summary-${reportDate}-${positionScope}-${currencyBasis}.csv`,
    content: [headers.join(","), ...lines].join("\n"),
  };
}

function buildMockBalanceAnalysisWorkbook(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): ApiEnvelope<BalanceAnalysisWorkbookPayload> {
  return buildMockApiEnvelope(
    "balance-analysis.workbook",
    {
      report_date: reportDate,
      position_scope: positionScope,
      currency_basis: currencyBasis,
      cards: [
        {
          key: "bond_assets_excluding_issue",
          label: "债券资产(剔除发行类)",
          value: "720.00",
          note: "ZQTZ 资产端剔除发行类后的余额。",
        },
        {
          key: "interbank_assets",
          label: "同业资产",
          value: "36.00",
          note: "TYW 资产端余额。",
        },
        {
          key: "interbank_liabilities",
          label: "同业负债",
          value: "72.00",
          note: "TYW 负债端余额。",
        },
        {
          key: "issuance_liabilities",
          label: "发行类负债",
          value: "18.00",
          note: "ZQTZ 发行类单列余额。",
        },
        {
          key: "net_position",
          label: "净头寸",
          value: "648.00",
          note: "资产端合计 - 同业负债。",
        },
      ],
      tables: [
        {
          key: "bond_business_types",
          title: "债券业务种类",
          section_kind: "table",
          columns: [
            { key: "bond_type", label: "业务种类" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              bond_type: "政策性金融债",
              balance_amount: "720.00",
            },
          ],
        },
        {
          key: "maturity_gap",
          title: "期限缺口分析",
          section_kind: "table",
          columns: [
            { key: "bucket", label: "期限分类" },
            { key: "gap_amount", label: "缺口" },
          ],
          rows: [
            {
              bucket: "1-2年",
              gap_amount: "648.00",
            },
          ],
        },
        {
          key: "rating_analysis",
          title: "信用评级分析",
          section_kind: "table",
          columns: [
            { key: "rating", label: "评级" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              rating: "AAA",
              balance_amount: "720.00",
            },
          ],
        },
        {
          key: "issuance_business_types",
          title: "发行类分析",
          section_kind: "table",
          columns: [
            { key: "bond_type", label: "业务种类" },
            { key: "balance_amount", label: "金额" },
          ],
          rows: [
            {
              bond_type: "同业存单",
              balance_amount: "180.00",
            },
          ],
        },
        {
          key: "industry_distribution",
          title: "行业分布",
          section_kind: "table",
          columns: [
            { key: "industry_name", label: "行业" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              industry_name: "金融业",
              balance_amount: "720.00",
            },
          ],
        },
        {
          key: "rate_distribution",
          title: "利率分布分析",
          section_kind: "table",
          columns: [
            { key: "bucket", label: "利率区间" },
            { key: "bond_amount", label: "债券面值" },
            { key: "interbank_asset_amount", label: "同业资产" },
            { key: "interbank_liability_amount", label: "同业负债" },
          ],
          rows: [
            {
              bucket: "1.5%-2.0%",
              bond_amount: "9900.75",
              interbank_asset_amount: "958.00",
              interbank_liability_amount: "2206.08",
            },
          ],
        },
        {
          key: "counterparty_types",
          title: "对手方类型",
          section_kind: "table",
          columns: [
            { key: "counterparty_type", label: "对手方类型" },
            { key: "asset_amount", label: "资产金额" },
            { key: "liability_amount", label: "负债金额" },
            { key: "net_position_amount", label: "净头寸" },
          ],
          rows: [
            {
              counterparty_type: "股份制银行",
              asset_amount: "120.00",
              liability_amount: "86.08",
              net_position_amount: "33.92",
            },
          ],
        },
        {
          key: "interest_modes",
          title: "计息方式",
          section_kind: "table",
          columns: [
            { key: "interest_mode", label: "计息方式" },
            { key: "balance_amount", label: "面值/余额" },
          ],
          rows: [
            {
              interest_mode: "固定",
              balance_amount: "32874.42",
            },
          ],
        },
      ],
      operational_sections: [
        {
          key: "decision_items",
          title: "决策事项",
          section_kind: "decision_items",
          columns: [
            { key: "title", label: "Title" },
            { key: "action_label", label: "Action" },
            { key: "severity", label: "Severity" },
            { key: "reason", label: "Reason" },
          ],
          rows: [
            {
              title: "Review 1-2 year gap positioning",
              action_label: "Review gap",
              severity: "high",
              reason: "Bucket gap is 648.00 wan yuan.",
              source_section: "maturity_gap",
              rule_id: "bal_wb_decision_gap_001",
              rule_version: "v1",
            },
          ],
        },
        {
          key: "event_calendar",
          title: "事件日历",
          section_kind: "event_calendar",
          columns: [
            { key: "event_date", label: "Event Date" },
            { key: "event_type", label: "Event Type" },
            { key: "title", label: "Title" },
            { key: "impact_hint", label: "Impact Hint" },
          ],
          rows: [
            {
              event_date: "2026-01-31",
              event_type: "asset_maturity",
              title: "asset-1 maturity",
              source: "internal_governed_schedule",
              impact_hint: "asset book / 拆放同业",
              source_section: "maturity_gap",
            },
            {
              event_date: "2026-02-05",
              event_type: "funding_rollover",
              title: "repo-1 maturity",
              source: "internal_governed_schedule",
              impact_hint: "liability book / 卖出回购",
              source_section: "maturity_gap",
            },
          ],
        },
        {
          key: "risk_alerts",
          title: "风险预警",
          section_kind: "risk_alerts",
          columns: [
            { key: "title", label: "Title" },
            { key: "severity", label: "Severity" },
            { key: "reason", label: "Reason" },
          ],
          rows: [
            {
              title: "Issuance liabilities outstanding",
              severity: "medium",
              reason: "Issuance book totals 18.00 wan yuan.",
              source_section: "issuance_business_types",
              rule_id: "bal_wb_risk_issuance_001",
              rule_version: "v1",
            },
            {
              title: "Negative gap in 1-2 year bucket",
              severity: "high",
              reason: "Gap dropped to -128.00 wan yuan.",
              source_section: "maturity_gap",
              rule_id: "bal_wb_risk_gap_001",
              rule_version: "v1",
            },
          ],
        },
      ],
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_balance_mock",
      rule_version: "rv_balance_analysis_formal_materialize_v1",
      cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
    },
  );
}

function buildMockBalanceAnalysisDecisionItems(
  reportDate: string,
  positionScope: BalancePositionScope,
  currencyBasis: BalanceCurrencyBasis,
): ApiEnvelope<BalanceAnalysisDecisionItemsPayload> {
  return buildMockApiEnvelope(
    "balance-analysis.decision-items",
    {
      report_date: reportDate,
      position_scope: positionScope,
      currency_basis: currencyBasis,
      columns: [
        { key: "title", label: "Title" },
        { key: "action_label", label: "Action" },
        { key: "severity", label: "Severity" },
        { key: "reason", label: "Reason" },
        { key: "source_section", label: "Source Section" },
        { key: "rule_id", label: "Rule Id" },
        { key: "rule_version", label: "Rule Version" },
      ],
      rows: [
        {
          decision_key: "bal_wb_decision_gap_001::maturity_gap::Review 1-2 year gap positioning",
          title: "Review 1-2 year gap positioning",
          action_label: "Review gap",
          severity: "high",
          reason: "Bucket gap is 648.00 wan yuan.",
          source_section: "maturity_gap",
          rule_id: "bal_wb_decision_gap_001",
          rule_version: "v1",
          latest_status: {
            decision_key:
              "bal_wb_decision_gap_001::maturity_gap::Review 1-2 year gap positioning",
            status: "pending",
            updated_at: null,
            updated_by: null,
            comment: null,
          },
        },
      ],
    },
    {
      basis: "formal",
      formal_use_allowed: true,
      source_version: "sv_balance_mock",
      rule_version: "rv_balance_analysis_formal_materialize_v1",
      cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
    },
  );
}

export class ActionRequestError extends Error {
  readonly status: number;
  readonly runId?: string;
  /** Top-level `error_message` from the JSON body when present. */
  readonly errorMessage?: string;
  /** Raw `detail` field from the JSON body (string, object, or array). */
  readonly detail?: unknown;

  constructor(
    message: string,
    opts: {
      status: number;
      runId?: string;
      errorMessage?: string;
      detail?: unknown;
    },
  ) {
    super(message);
    this.name = "ActionRequestError";
    this.status = opts.status;
    this.runId = opts.runId;
    this.errorMessage = opts.errorMessage;
    this.detail = opts.detail;
  }
}

function extractApiRunId(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const body = payload as Record<string, unknown>;
  const top = body.run_id;
  if (typeof top === "string" && top.trim()) {
    return top;
  }
  const detail = body.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const nested = (detail as Record<string, unknown>).run_id;
    if (typeof nested === "string" && nested.trim()) {
      return nested;
    }
  }
  return undefined;
}

function extractTopLevelErrorMessage(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  const errMsg = (payload as Record<string, unknown>).error_message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    return errMsg;
  }
  return undefined;
}

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
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as Record<string, unknown>;
    const nestedMsg = d.error_message;
    if (typeof nestedMsg === "string" && nestedMsg.trim()) {
      return nestedMsg;
    }
    const nestedDetail = d.detail;
    if (typeof nestedDetail === "string" && nestedDetail.trim()) {
      return nestedDetail;
    }
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

function extractRawDetail(payload: unknown): unknown {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  if (!("detail" in (payload as Record<string, unknown>))) {
    return undefined;
  }
  return (payload as Record<string, unknown>).detail;
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
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    const detailText =
      extractApiErrorDetail(body) ?? `Request failed: ${path} (${response.status})`;
    const runId = extractApiRunId(body);
    const rawDetail = extractRawDetail(body);
    const topErrorMessage = extractTopLevelErrorMessage(body);
    const nestedDetail =
      rawDetail && typeof rawDetail === "object" && !Array.isArray(rawDetail)
        ? (rawDetail as Record<string, unknown>).error_message
        : undefined;
    const errorMessageField =
      topErrorMessage ??
      (typeof nestedDetail === "string" && nestedDetail.trim() ? nestedDetail : undefined);
    throw new ActionRequestError(detailText, {
      status: response.status,
      runId,
      errorMessage: errorMessageField,
      detail: rawDetail,
    });
  }

  return (await response.json()) as T;
};

const requestText = async (
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  fallbackFilename = "download.csv",
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
  return {
    content: await response.text(),
    filename: parseDownloadFilename(contentDisposition, fallbackFilename),
  };
};

function parseDownloadFilename(contentDisposition: string, fallbackFilename: string) {
  const utf8Match = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(contentDisposition);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const filenameMatch = /filename=\"?([^\";]+)\"?/i.exec(contentDisposition);
  return filenameMatch?.[1] ?? fallbackFilename;
}

const requestBlob = async (
  fetchImpl: typeof fetch,
  baseUrl: string,
  path: string,
  fallbackFilename = "download.bin",
): Promise<{ content: Blob; filename: string }> => {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: {
      Accept:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/octet-stream;q=0.9, */*;q=0.8",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  const contentDisposition = response.headers.get("Content-Disposition") ?? "";
  return {
    content: await response.blob(),
    filename: parseDownloadFilename(contentDisposition, fallbackFilename),
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
      return buildMockApiEnvelope(
        "pnl.dates",
        {
          report_dates: [],
          formal_fi_report_dates: [],
          nonstd_bridge_report_dates: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getFormalPnlData(date: string) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.data",
        {
          report_date: date,
          formal_fi_rows: [],
          nonstd_bridge_rows: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getFormalPnlOverview(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.overview",
        {
          report_date: reportDate,
          formal_fi_row_count: 0,
          nonstd_bridge_row_count: 0,
          interest_income_514: "0.00",
          fair_value_change_516: "0.00",
          capital_gain_517: "0.00",
          manual_adjustment: "0.00",
          total_pnl: "0.00",
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getPnlBridge(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "pnl.bridge",
        {
          report_date: reportDate,
          rows: [],
          summary: {
            row_count: 0,
            ok_count: 0,
            warning_count: 0,
            error_count: 0,
            total_beginning_dirty_mv: "0",
            total_ending_dirty_mv: "0",
            total_carry: "0",
            total_roll_down: "0",
            total_treasury_curve: "0",
            total_credit_spread: "0",
            total_fx_translation: "0",
            total_realized_trading: "0",
            total_unrealized_fv: "0",
            total_manual_adjustment: "0",
            total_explained_pnl: "0",
            total_actual_pnl: "0",
            total_residual: "0",
            quality_flag: "ok",
          },
          warnings: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async refreshFormalPnl() {
      await delay();
      return {
        status: "queued",
        run_id: "pnl_materialize:mock-run",
        job_name: "pnl_materialize",
        trigger_mode: "async",
        cache_key: "pnl:phase2:materialize:formal",
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
        cache_key: "pnl:phase2:materialize:formal",
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
    async getRiskTensor(reportDate: string) {
      await delay();
      const zero = "0.00000000";
      return buildMockApiEnvelope(
        "risk.tensor",
        {
          report_date: reportDate,
          portfolio_dv01: zero,
          krd_1y: zero,
          krd_3y: zero,
          krd_5y: zero,
          krd_7y: zero,
          krd_10y: zero,
          krd_30y: zero,
          cs01: zero,
          portfolio_convexity: zero,
          portfolio_modified_duration: zero,
          issuer_concentration_hhi: zero,
          issuer_top5_weight: zero,
          liquidity_gap_30d: zero,
          liquidity_gap_90d: zero,
          liquidity_gap_30d_ratio: zero,
          total_market_value: zero,
          bond_count: 0,
          quality_flag: "ok",
          warnings: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
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
    async getBalanceAnalysisDates() {
      await delay();
      return buildMockApiEnvelope(
        "balance-analysis.dates",
        {
          report_dates: ["2025-12-31"],
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisOverview({ reportDate, positionScope, currencyBasis }) {
      await delay();
      const detailRows = [
        {
          source_family: "zqtz" as const,
          position_scope: "asset" as const,
          currency_basis: "CNY" as const,
          market_value_amount: "720.00",
          amortized_cost_amount: "648.00",
          accrued_interest_amount: "36.00",
        },
        {
          source_family: "tyw" as const,
          position_scope: "liability" as const,
          currency_basis: "CNY" as const,
          market_value_amount: "72.00",
          amortized_cost_amount: "72.00",
          accrued_interest_amount: "14.40",
        },
      ].filter((row) => {
        const matchesScope = positionScope === "all" || row.position_scope === positionScope;
        const matchesBasis = row.currency_basis === currencyBasis;
        return matchesScope && matchesBasis;
      });
      const totals = detailRows.reduce(
        (acc, row) => ({
          detailRowCount: acc.detailRowCount + 1,
          summaryRowCount: acc.summaryRowCount + 1,
          marketValue: acc.marketValue + Number.parseFloat(row.market_value_amount),
          amortizedCost: acc.amortizedCost + Number.parseFloat(row.amortized_cost_amount),
          accruedInterest: acc.accruedInterest + Number.parseFloat(row.accrued_interest_amount),
        }),
        {
          detailRowCount: 0,
          summaryRowCount: 0,
          marketValue: 0,
          amortizedCost: 0,
          accruedInterest: 0,
        },
      );
      return buildMockApiEnvelope(
        "balance-analysis.overview",
        {
          report_date: reportDate,
          position_scope: positionScope,
          currency_basis: currencyBasis,
          detail_row_count: totals.detailRowCount,
          summary_row_count: totals.summaryRowCount,
          total_market_value_amount: totals.marketValue.toFixed(2),
          total_amortized_cost_amount: totals.amortizedCost.toFixed(2),
          total_accrued_interest_amount: totals.accruedInterest.toFixed(2),
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisDetail({ reportDate, positionScope, currencyBasis }) {
      await delay();
      const baseDetails = [
        {
          source_family: "zqtz" as const,
          report_date: reportDate,
          row_key: "zqtz:mock",
          display_name: "240001.IB",
          position_scope: "asset" as const,
          currency_basis: "CNY" as const,
          invest_type_std: "A",
          accounting_basis: "FVOCI",
          market_value_amount: "720.00",
          amortized_cost_amount: "648.00",
          accrued_interest_amount: "36.00",
          is_issuance_like: false,
        },
        {
          source_family: "tyw" as const,
          report_date: reportDate,
          row_key: "tyw:mock",
          display_name: "pos-1",
          position_scope: "liability" as const,
          currency_basis: "CNY" as const,
          invest_type_std: "H",
          accounting_basis: "AC",
          market_value_amount: "72.00",
          amortized_cost_amount: "72.00",
          accrued_interest_amount: "14.40",
          is_issuance_like: null,
        },
      ].filter((row) => {
        const matchesScope = positionScope === "all" || row.position_scope === positionScope;
        const matchesBasis = row.currency_basis === currencyBasis;
        return matchesScope && matchesBasis;
      });
      const summary = baseDetails.map((row) => ({
        source_family: row.source_family,
        position_scope: row.position_scope,
        currency_basis: row.currency_basis,
        row_count: 1,
        market_value_amount: row.market_value_amount,
        amortized_cost_amount: row.amortized_cost_amount,
        accrued_interest_amount: row.accrued_interest_amount,
      }));
      return buildMockApiEnvelope(
        "balance-analysis.detail",
        {
          report_date: reportDate,
          position_scope: positionScope,
          currency_basis: currencyBasis,
          details: baseDetails,
          summary,
        },
        {
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_balance_mock",
          rule_version: "rv_balance_analysis_formal_materialize_v1",
          cache_version: "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        },
      );
    },
    async getBalanceAnalysisSummary({ reportDate, positionScope, currencyBasis, limit, offset }) {
      await delay();
      return buildMockBalanceAnalysisSummaryTable(
        reportDate,
        positionScope,
        currencyBasis,
        limit,
        offset,
      );
    },
    async getBalanceAnalysisWorkbook({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return buildMockBalanceAnalysisWorkbook(reportDate, positionScope, currencyBasis);
    },
    async getBalanceAnalysisCurrentUser() {
      await delay();
      return {
        user_id: "phase1-dev-user",
        role: "admin",
        identity_source: "fallback",
      };
    },
    async getBalanceAnalysisDecisionItems({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return buildMockBalanceAnalysisDecisionItems(reportDate, positionScope, currencyBasis);
    },
    async updateBalanceAnalysisDecisionStatus({
      decisionKey,
      status,
      comment,
    }) {
      await delay();
      return {
        decision_key: decisionKey,
        status,
        updated_at: "2026-04-12T08:00:00Z",
        updated_by: "phase1-dev-user",
        comment: comment ?? null,
      };
    },
    async exportBalanceAnalysisSummaryCsv({ reportDate, positionScope, currencyBasis }) {
      await delay();
      return buildMockBalanceAnalysisSummaryCsv(reportDate, positionScope, currencyBasis);
    },
    async exportBalanceAnalysisWorkbookXlsx({ reportDate }) {
      await delay();
      return {
        filename: `资产负债分析_${reportDate}.xlsx`,
        content: new Blob(["mock-workbook"], {
          type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }),
      };
    },
    async refreshBalanceAnalysis(reportDate: string) {
      await delay();
      return {
        status: "queued",
        run_id: "balance_analysis_materialize:mock-run",
        job_name: "balance_analysis_materialize",
        trigger_mode: "async",
        cache_key: "balance_analysis:materialize:formal",
        report_date: reportDate,
      };
    },
    async getBalanceAnalysisRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "balance_analysis_materialize",
        trigger_mode: "terminal",
        cache_key: "balance_analysis:materialize:formal",
        report_date: "2025-12-31",
        source_version: "sv_balance_mock",
        rule_version: "rv_balance_analysis_formal_materialize_v1",
      };
    },
    async refreshBondAnalytics(reportDate: string) {
      await delay();
      return {
        status: "queued",
        run_id: "bond_analytics_refresh:mock-run",
        job_name: "bond_analytics_refresh",
        cache_key: "bond_analytics:materialize",
        report_date: reportDate,
      };
    },
    async getBondAnalyticsRefreshStatus(runId: string) {
      await delay();
      return {
        status: "completed",
        run_id: runId,
        job_name: "bond_analytics_refresh",
        cache_key: "bond_analytics:materialize",
        report_date: "2025-12-31",
      };
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
      requestJson<PnlDatesPayload>(fetchImpl, baseUrl, "/api/pnl/dates"),
    getFormalPnlData: (date: string) =>
      requestJson<PnlDataPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/data?date=${encodeURIComponent(date)}`,
      ),
    getFormalPnlOverview: (reportDate: string) =>
      requestJson<PnlOverviewPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/overview?report_date=${encodeURIComponent(reportDate)}`,
      ),
    getPnlBridge: (reportDate: string) =>
      requestJson<PnlBridgePayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/bridge?report_date=${encodeURIComponent(reportDate)}`,
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
    getRiskTensor: (reportDate: string) =>
      requestJson<RiskTensorPayload>(
        fetchImpl,
        baseUrl,
        `/api/risk/tensor?report_date=${encodeURIComponent(reportDate)}`,
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
        "product-category-audit.csv",
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
    getBalanceAnalysisDates: () =>
      requestJson<BalanceAnalysisDatesPayload>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/dates",
      ),
    getBalanceAnalysisOverview: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisOverviewPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/overview?${params.toString()}`,
      );
    },
    getBalanceAnalysisSummary: ({
      reportDate,
      positionScope,
      currencyBasis,
      limit,
      offset,
    }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
        limit: String(limit),
        offset: String(offset),
      });
      return requestJson<BalanceAnalysisSummaryTablePayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/summary?${params.toString()}`,
      );
    },
    getBalanceAnalysisWorkbook: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisWorkbookPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/workbook?${params.toString()}`,
      );
    },
    getBalanceAnalysisCurrentUser: () =>
      requestActionJson<BalanceAnalysisCurrentUserPayload>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/current-user",
      ),
    getBalanceAnalysisDecisionItems: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisDecisionItemsPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/decision-items?${params.toString()}`,
      );
    },
    updateBalanceAnalysisDecisionStatus: ({
      reportDate,
      positionScope,
      currencyBasis,
      decisionKey,
      status,
      comment,
    }) =>
      requestActionJson<BalanceAnalysisDecisionStatusRecord>(
        fetchImpl,
        baseUrl,
        "/ui/balance-analysis/decision-items/status",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            report_date: reportDate,
            position_scope: positionScope,
            currency_basis: currencyBasis,
            decision_key: decisionKey,
            status,
            comment,
          }),
        },
      ),
    getBalanceAnalysisDetail: ({ reportDate, positionScope, currencyBasis }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestJson<BalanceAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis?${params.toString()}`,
      );
    },
    exportBalanceAnalysisSummaryCsv: ({
      reportDate,
      positionScope,
      currencyBasis,
    }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestText(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/summary/export?${params.toString()}`,
        "balance-analysis-summary.csv",
      );
    },
    exportBalanceAnalysisWorkbookXlsx: ({
      reportDate,
      positionScope,
      currencyBasis,
    }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      return requestBlob(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/workbook/export?${params.toString()}`,
        "balance-analysis-workbook.xlsx",
      );
    },
    refreshBalanceAnalysis: (reportDate: string) =>
      requestActionJson<BalanceAnalysisRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/refresh?report_date=${encodeURIComponent(reportDate)}`,
        {
          method: "POST",
        },
      ),
    getBalanceAnalysisRefreshStatus: (runId: string) =>
      requestActionJson<BalanceAnalysisRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
    refreshBondAnalytics: (reportDate: string) =>
      requestActionJson<BondAnalyticsRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/refresh?report_date=${encodeURIComponent(reportDate)}`,
        {
          method: "POST",
        },
      ),
    getBondAnalyticsRefreshStatus: (runId: string) =>
      requestActionJson<BondAnalyticsRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/api/bond-analytics/refresh-status?run_id=${encodeURIComponent(runId)}`,
      ),
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


