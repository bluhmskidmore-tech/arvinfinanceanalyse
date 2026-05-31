import { useEffect, useState } from "react";
import { Collapse } from "antd";
import {
  CalendarOutlined,
  DownloadOutlined,
  FileExcelOutlined,
  FilterOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SwapOutlined,
} from "@ant-design/icons";
import "../../../lib/agGridSetup";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, ValueFormatterParams } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import "./BalanceAnalysisPage.css";

import { useApiClient } from "../../../api/client";
import type {
  BalanceAnalysisBasisBreakdownRow,
  BalanceAnalysisDecisionItemStatusRow,
  BalanceAnalysisEventCalendarRow,
  BalanceAnalysisRiskAlertRow,
  BalanceAnalysisSeverity,
  BalanceAnalysisTableRow,
  BalanceAnalysisWorkbookColumn,
  BalanceAnalysisWorkbookOperationalSection,
  BalanceAnalysisWorkbookTable,
  BalanceCurrencyBasis,
  BalancePositionScope,
} from "../../../api/contracts";
import { runPollingTask } from "../../../app/jobs/polling";
import { CalibrationBadge } from "../../../components/CalibrationBadge";
import { FilterBar } from "../../../components/FilterBar";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import {
  AnalysisGrid,
  DataStatusStrip,
  EvidencePanel,
  PageFilterTray,
  PageSectionLead,
  PageStateSurface,
} from "../../../components/page/PagePrimitives";
import { SectionCard } from "../../../components/SectionCard";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import AdbAnalyticalPreview from "../components/AdbAnalyticalPreview";
import BalanceAnalysisWorkbenchLayout, {
  type BalanceDeferredSurface,
  type BalanceEndpointGroup,
  type BalanceEndpointStatus,
  type BalanceStateSentinel,
} from "../components/BalanceAnalysisWorkbenchLayout";
import { BalanceBottomRow } from "../components/BalanceBottomRow";
import { BalanceContributionRow } from "../components/BalanceContributionRow";
import { BalanceSummaryRow } from "../components/BalanceSummaryRow";
import { useBalanceAnalysisData } from "../hooks/useBalanceAnalysisData";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import {
  actionButtonStyle,
  tableShellStyle,
  workbookPanelStyle,
  workbookPanelHeaderStyle,
  workbookPanelBadgeStyle,
  workbookSecondaryGridStyle,
} from "./BalanceAnalysisPage.styles";
import {
  buildBalanceAnalysisPageModel,
  distributionChartBarWidthPercent,
  formatBalanceAmountToYiFromWan,
  formatBalanceAmountToYiFromYuan,
  formatBalanceBusinessTextDisplay,
  formatBalanceGridThousandsValue,
  formatBalanceWorkbookCellDisplay,
  formatBalanceDecisionWorkflowStatusDisplay,
  formatBalanceGovernedSeverityDisplay,
  formatBalanceWorkbookMetricTwoDecimals,
  formatBalanceWorkbookOperationalSectionKeyDisplay,
  formatBalanceWorkbookWanAmountDisplay,
  formatBalanceWorkbookWanTextDisplay,
  buildBalanceReconciliationLinkModel,
  gapChartBarWidthPercent,
  maxAbsFiniteChartScale,
  maxFiniteChartScale,
  parseBalanceChartMagnitude,
} from "./balanceAnalysisPageModel";
import {
  getBalanceSummaryGridRowId,
  type BalanceAnalysisDetailGridRow,
  type BalanceAnalysisSummaryGridRow,
} from "./balanceAnalysisGridRows";

const primaryWorkbookTableKeys = [
  "bond_business_types",
  "rating_analysis",
  "maturity_gap",
  "issuance_business_types",
] as const;

const secondaryWorkbookPanelKeys = [
  "industry_distribution",
  "rate_distribution",
  "counterparty_types",
] as const;

type RightRailWorkbookKey = "event_calendar" | "risk_alerts";

const workbookPanelNotes: Record<(typeof primaryWorkbookTableKeys)[number], string> = {
  bond_business_types: "债券分类优先沿用余额变动的 ZQTZ 资产分类 CNX 期末余额；无联动数据时退回 Workbook 原币面值。",
  rating_analysis: "评级映射与余额变动集中度一致：空评级利率债归 AAA，其他空评级归未映射；金额仍为 Workbook 原币面值，CNY/CNX 控制数看上方联动核对。",
  maturity_gap: "用期限桶直接看资产负债缺口，不再只给纯表格。",
  issuance_business_types: "发行类单独成块，避免和资产端视图混在一起。",
};

const workbookSecondaryPanelNotes: Record<(typeof secondaryWorkbookPanelKeys)[number], string> = {
  industry_distribution: "行业分布优先沿用余额变动集中度的 CNX 期末余额；无联动数据时退回 Workbook 原币面值。",
  rate_distribution: "同一利率桶里并排看债券、同业资产和同业负债。",
  counterparty_types: "按对手方类型看资产、负债和净头寸。",
};

const workbookRightRailNotes: Record<RightRailWorkbookKey, string> = {
  event_calendar: "内部治理事件日历，只展示由现有正式结果和工作簿输入派生的事件。",
  risk_alerts: "阈值型风险预警，不在前端补正式金融判断。",
};

const decisionRailNote = "规则驱动的运营建议项通过处理流确认、忽略和跟踪，不把处理结果写回正式事实表。";

type BalanceEndpointQueryState = {
  isError: boolean;
  isLoading: boolean;
  isFetching?: boolean;
  isSuccess: boolean;
};

type BalanceAttentionSentinelKey = "stale" | "fallback" | "error";

type BalanceAttentionReason = {
  key: string;
  sentinel: BalanceAttentionSentinelKey;
  detail: string;
};

function queryEndpointStatus(
  query: BalanceEndpointQueryState,
  enabled = true,
): BalanceEndpointStatus {
  if (!enabled) {
    return "deferred";
  }
  if (query.isError) {
    return "error";
  }
  if (query.isLoading || query.isFetching) {
    return "loading";
  }
  if (query.isSuccess) {
    return "ready";
  }
  return "idle";
}

function actionEndpointStatus({
  isError,
  isLoading,
  isActive,
}: {
  isError?: boolean;
  isLoading?: boolean;
  isActive?: boolean;
}): BalanceEndpointStatus {
  if (isError) {
    return "error";
  }
  if (isLoading) {
    return "loading";
  }
  if (isActive) {
    return "ready";
  }
  return "idle";
}

function firstAttentionDetail(
  reasons: readonly BalanceAttentionReason[],
  sentinel: BalanceAttentionSentinelKey,
  fallback: string,
): string {
  return (
    reasons.find(
      (reason) => reason.sentinel === sentinel && !reason.key.startsWith("status-badge-"),
    )?.detail ??
    reasons.find((reason) => reason.sentinel === sentinel)?.detail ??
    fallback
  );
}

function formatAttentionBasis(value: string | undefined): string {
  if (value === "formal") return "正式口径";
  if (value === "analytical") return "分析口径";
  if (value === "scenario") return "情景口径";
  if (value === "mock") return "模拟口径";
  return "未知口径";
}

function formatAttentionQuality(value: string | undefined): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  if (value === "missing") return "缺失";
  return "未提供";
}

function formatAttentionFallback(value: string | undefined): string {
  if (value === "none") return "未降级";
  if (value === "latest_snapshot") return "最新快照降级";
  return "未提供";
}

function formatEvidenceTraceDisplay(value: string): string {
  if (!value || value === "未提供") {
    return "未提供";
  }
  return "已记录";
}

function formatRefreshStatusDisplay(status: string | undefined): string {
  if (status === "queued") return "刷新任务已排队";
  if (status === "running") return "刷新任务进行中";
  if (status === "completed") return "刷新结果已生成";
  if (status === "failed") return "刷新暂未完成";
  return "刷新任务已有反馈";
}

function formatOperationIssueDisplay(action: "refresh" | "decision" | "summary-export" | "workbook-export"): string {
  if (action === "decision") {
    return "治理处理结果暂未写入，请稍后重试或联系数据负责人。";
  }
  if (action === "summary-export") {
    return "汇总表暂未导出，请稍后重试。";
  }
  if (action === "workbook-export") {
    return "工作簿暂未导出，请稍后重试。";
  }
  return "正式结果暂未刷新，请稍后重试。";
}

function formatCurrentUserRoleDisplay(role: string | undefined): string {
  if (role === "viewer") return "查看者";
  if (role === "reviewer") return "复核人";
  if (role === "admin") return "管理员";
  return role || "未识别角色";
}

function formatCurrentUserDisplay(userId: string | undefined): string {
  if (!userId || userId === "anonymous") return "默认提交人";
  return userId;
}

function formatIdentitySourceDisplay(source: string | undefined): string {
  if (source === "fallback") return "兜底身份";
  if (source === "header") return "请求头身份";
  if (source === "session") return "会话身份";
  return source || "未知来源";
}

function formatAdvancedAttributionStatusDisplay(status: string | undefined): string {
  if (status === "not_ready") return "未就绪";
  if (status === "partial") return "部分可用";
  if (status === "ready") return "可用";
  return status ? "已有反馈" : "待返回";
}

function formatAdvancedAttributionModeDisplay(mode: string | undefined): string {
  if (mode === "analytical") return "分析口径";
  if (mode === "scenario") return "情景口径";
  if (mode === "formal") return "正式口径";
  return mode ? "补充口径" : "未提供";
}

function formatAdvancedAttributionInputDisplay(input: string): string {
  if (/yield_curves/i.test(input)) return "收益曲线对齐";
  if (/trade|position|cashflow/i.test(input)) return "成交、持仓与现金流明细";
  if (/benchmark|index/i.test(input)) return "基准指数收益序列";
  if (/pnl/i.test(input)) return "损益实绩对齐";
  return "上游治理输入";
}

function formatAdvancedAttributionWarningDisplay(warning: string): string {
  if (/advanced_attribution_bundle|partial/i.test(warning)) return "高阶归因仅返回部分分析材料。";
  if (/bond_analytics|phase3/i.test(warning)) return "债券分析三阶段结果尚未完整对齐。";
  if (/pnl|bridge|return_decomposition/i.test(warning)) return "归因材料来自已治理摘要，仍需底稿补齐。";
  return "补充提示已记录。";
}

const ratingBlockPalette = [
  designTokens.color.success[400],
  designTokens.color.info[400],
  designTokens.color.warning[400],
  designTokens.color.primary[400],
  designTokens.color.danger[400],
  designTokens.color.info[300],
] as const;

function downloadBlobFile(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function downloadCsvFile(filename: string, content: string) {
  downloadBlobFile(filename, new Blob([content], { type: "text/csv;charset=utf-8;" }));
}

function thousandsValueFormatter(params: ValueFormatterParams) {
  return formatBalanceGridThousandsValue(params.value);
}

function yuanAmountValueFormatter(params: ValueFormatterParams) {
  return formatBalanceAmountToYiFromYuan(params.value);
}

const workbookWanAmountFieldKeys = new Set([
  "asset_amount",
  "asset_total_amount",
  "balance_amount",
  "bond_amount",
  "bond_assets_amount",
  "bond_maturity_amount",
  "book_value_amount",
  "coupon_income_amount",
  "cumulative_gap_amount",
  "cumulative_net_cashflow_amount",
  "face_value_amount",
  "floating_pnl_amount",
  "full_scope_gap_amount",
  "full_scope_liability_amount",
  "gap_amount",
  "hqla_amount",
  "interbank_asset_amount",
  "interbank_asset_maturity_amount",
  "interbank_assets_amount",
  "interbank_liability_amount",
  "interbank_liability_maturity_amount",
  "interbank_liabilities_amount",
  "issuance_amount",
  "issuance_maturity_amount",
  "liability_amount",
  "market_value_amount",
  "net_cashflow_amount",
  "net_position_amount",
  "notional_amount",
  "price_return_amount",
  "spread_income_amount",
  "total_amount",
  "amortized_cost_amount",
]);

function isWorkbookWanAmountField(field: unknown): field is string {
  return typeof field === "string" && workbookWanAmountFieldKeys.has(field);
}

function workbookCellFormatter(params: ValueFormatterParams): string {
  if (isWorkbookWanAmountField(params.colDef.field)) {
    return formatBalanceWorkbookWanAmountDisplay(params.value);
  }
  if (typeof params.value === "string" && /(?:wan yuan|万元)/i.test(params.value)) {
    return formatBalanceWorkbookWanTextDisplay(params.value);
  }
  const formattedValue = formatBalanceGridThousandsValue(params.value);
  return typeof params.value === "string" && formattedValue === params.value
    ? formatBalanceBusinessTextDisplay(params.value)
    : formattedValue;
}

function businessTextValueFormatter(params: ValueFormatterParams): string {
  return formatBalanceBusinessTextDisplay(params.value);
}

function formatInvestAccountingDisplay(data: {
  invest_type_std?: unknown;
  accounting_basis?: unknown;
} | null | undefined): string {
  if (!data) {
    return "";
  }
  const investType = data.invest_type_std == null ? "" : formatBalanceBusinessTextDisplay(data.invest_type_std);
  const accountingBasis =
    data.accounting_basis == null ? "" : formatBalanceBusinessTextDisplay(data.accounting_basis);
  const parts = [investType, accountingBasis].filter((part) => part && part !== "—");
  return parts.length > 0 ? parts.join(" / ") : "—";
}

const balanceAnalysisGridDefaultColDef: ColDef = {
  sortable: true,
  filter: true,
  resizable: true,
  flex: 1,
  minWidth: 100,
  cellStyle: (params) =>
    params.colDef?.cellClass === "ag-right-aligned-cell" ? { ...tabularNumsStyle } : undefined,
};

const balanceAnalysisGridLocaleText = {
  noRowsToShow: "暂无数据",
};

const balanceSummaryColDefs: ColDef<BalanceAnalysisTableRow>[] = [
  {
    field: "source_family",
    headerName: "来源",
    valueFormatter: businessTextValueFormatter,
  },
  { field: "display_name", headerName: "展示名" },
  { field: "owner_name", headerName: "组合名称" },
  { field: "category_name", headerName: "分类" },
  { field: "position_scope", headerName: "头寸范围", valueFormatter: businessTextValueFormatter },
  { field: "currency_basis", headerName: "币种口径", valueFormatter: businessTextValueFormatter },
  {
    field: "market_value_amount",
    headerName: "规模(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "amortized_cost_amount",
    headerName: "摊余成本(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "accrued_interest_amount",
    headerName: "应计利息(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "detail_row_count",
    headerName: "明细行数",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    colId: "invest_accounting",
    headerName: "会计口径",
    valueGetter: (p) => formatInvestAccountingDisplay(p.data),
  },
];

const balanceDetailColDefs: ColDef<BalanceAnalysisDetailGridRow>[] = [
  {
    field: "source_family",
    headerName: "来源",
    valueFormatter: businessTextValueFormatter,
  },
  { field: "display_name", headerName: "标识" },
  { field: "report_date", headerName: "报告日" },
  { field: "position_scope", headerName: "范围", valueFormatter: businessTextValueFormatter },
  {
    colId: "invest_accounting",
    headerName: "会计口径",
    valueGetter: (p) => formatInvestAccountingDisplay(p.data),
  },
  {
    field: "market_value_amount",
    headerName: "规模(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "amortized_cost_amount",
    headerName: "摊余成本(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "accrued_interest_amount",
    headerName: "应计利息(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "is_issuance_like",
    headerName: "发行类",
    valueFormatter: (p) =>
      p.value === null || p.value === undefined ? "—" : p.value ? "是" : "否",
  },
];

const balanceDetailSummaryColDefs: ColDef<BalanceAnalysisSummaryGridRow>[] = [
  {
    field: "source_family",
    headerName: "来源",
    valueFormatter: businessTextValueFormatter,
  },
  { field: "position_scope", headerName: "头寸范围", valueFormatter: businessTextValueFormatter },
  { field: "currency_basis", headerName: "币种口径", valueFormatter: businessTextValueFormatter },
  {
    field: "row_count",
    headerName: "行数",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    field: "market_value_amount",
    headerName: "市值(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "amortized_cost_amount",
    headerName: "摊余成本(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "accrued_interest_amount",
    headerName: "应计利息(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
];

const balanceBasisBreakdownColDefs: ColDef<BalanceAnalysisBasisBreakdownRow>[] = [
  {
    field: "source_family",
    headerName: "来源",
    valueFormatter: businessTextValueFormatter,
  },
  { field: "invest_type_std", headerName: "投资类型", valueFormatter: businessTextValueFormatter },
  { field: "accounting_basis", headerName: "会计口径", valueFormatter: businessTextValueFormatter },
  { field: "position_scope", headerName: "头寸范围", valueFormatter: businessTextValueFormatter },
  { field: "currency_basis", headerName: "币种口径", valueFormatter: businessTextValueFormatter },
  {
    field: "detail_row_count",
    headerName: "明细行数",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    field: "market_value_amount",
    headerName: "市值(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "amortized_cost_amount",
    headerName: "摊余成本(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
  {
    field: "accrued_interest_amount",
    headerName: "应计利息(亿元)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: yuanAmountValueFormatter,
  },
];

const workbookColumnLabelDisplay: Record<string, string> = {
  Month: "月份",
  "Bond Maturity Amount": "债券到期金额",
  "Bond Maturity Count": "债券到期笔数",
  "Interbank Asset Maturity Amount": "同业资产到期金额",
  "Interbank Asset Maturity Count": "同业资产到期笔数",
  "Interbank Liability Maturity Amount": "同业负债到期金额",
  "Interbank Liability Maturity Count": "同业负债到期笔数",
  "Issuance Maturity Amount": "发行类到期金额",
  "Issuance Maturity Count": "发行类到期笔数",
  "Net Cashflow Amount": "净现金流金额",
  "Cumulative Net Cashflow Amount": "累计净现金流金额",
  Cumulative: "累计值",
  指标键: "指标",
  指标名称: "指标名称",
  参考阈值: "参考线",
  状态: "判断",
  口径说明: "口径",
};

function formatWorkbookColumnLabelDisplay(label: string): string {
  return workbookColumnLabelDisplay[label] ?? formatBalanceBusinessTextDisplay(label);
}

function buildWorkbookGridColumnDefs(columns: BalanceAnalysisWorkbookColumn[]): ColDef[] {
  return columns.map((col) => ({
    field: col.key,
    headerName: formatWorkbookColumnLabelDisplay(col.label),
    valueFormatter: workbookCellFormatter,
    cellStyle: { ...tabularNumsStyle },
  }));
}

function renderWorkbookContractMismatch(
  table: Pick<BalanceAnalysisWorkbookTable, "key"> | Pick<BalanceAnalysisWorkbookOperationalSection, "key">,
  message: string,
) {
  return (
    <div
      data-testid={`balance-analysis-workbook-table-${table.key}`}
      className="balance-analysis-workbook-alert balance-analysis-workbook-alert--warning"
    >
      {message}
    </div>
  );
}

function renderWorkbookEmptyState(message: string) {
  return (
    <div className="balance-analysis-workbook-alert balance-analysis-workbook-alert--empty">
      {message}
    </div>
  );
}

function hasWorkbookFields(rows: Array<Record<string, unknown>>, requiredKeys: string[]) {
  if (rows.length === 0) {
    return true;
  }
  return rows.every((row) => requiredKeys.every((key) => row[key] !== undefined && row[key] !== null));
}

function renderDistributionPanel(
  table: BalanceAnalysisWorkbookTable,
  {
    labelKey,
    valueKey,
    color,
  }: {
    labelKey: string;
    valueKey: string;
    color: string;
  },
) {
  const rows = table.rows.slice(0, 6);
  if (!hasWorkbookFields(rows, [labelKey, valueKey])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：缺少主分布图所需字段。");
  }
  const maxAmong = maxFiniteChartScale(rows.map((row) => row[valueKey]));
  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list">
      {rows.map((row, index) => {
        const mag = parseBalanceChartMagnitude(row[valueKey]);
        const widthPct = distributionChartBarWidthPercent(mag, maxAmong);
        const width = widthPct == null ? "0%" : `${widthPct}%`;
        return (
          <div key={`${table.key}-${index}`} className="balance-analysis-mini-row">
            <div className="balance-analysis-mini-topline">
              <span className="balance-analysis-mini-label">
                {formatBalanceWorkbookCellDisplay(row[labelKey])}
              </span>
              <span className="balance-analysis-mini-value">
                {formatBalanceWorkbookWanAmountDisplay(row[valueKey])}
              </span>
            </div>
            <div className="balance-analysis-mini-bar-track">
              <div
                data-testid={`balance-analysis-distribution-bar-${table.key}-${index}`}
                style={{
                  width,
                  background: color,
                }}
                className="balance-analysis-mini-bar-fill"
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function renderRatingPanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 6);
  if (!hasWorkbookFields(rows, ["rating", "balance_amount"])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：评级分布字段不完整。");
  }
  const maxValue = maxFiniteChartScale(rows.map((row) => row.balance_amount));
  let hasFiniteTotal = false;
  let totalWan = 0;
  for (const row of table.rows) {
    const mag = parseBalanceChartMagnitude(row.balance_amount);
    if (mag.kind === "finite") {
      hasFiniteTotal = true;
      totalWan += mag.value;
    }
  }
  return (
    <div
      data-testid={`balance-analysis-workbook-table-${table.key}`}
      className="balance-analysis-rating-panel"
    >
      <div className="balance-analysis-rating-panel__grid">
        {rows.map((row, index) => {
          const mag = parseBalanceChartMagnitude(row.balance_amount);
          const ratio = mag.kind === "finite" ? Math.max(0.35, mag.value / maxValue) : 0.35;
          return (
            <article
              key={`${table.key}-${index}`}
              className="balance-analysis-rating-card"
              style={{
                background: ratingBlockPalette[index % ratingBlockPalette.length],
                opacity: 0.55 + ratio * 0.45,
              }}
            >
              <div className="balance-analysis-rating-card__label">{formatBalanceWorkbookCellDisplay(row.rating)}</div>
              <div className="balance-analysis-rating-card__value">
                {formatBalanceWorkbookWanAmountDisplay(row.balance_amount)}
              </div>
            </article>
          );
        })}
      </div>
      <div className="balance-analysis-rating-reconciliation">
        <span className="balance-analysis-rating-reconciliation__total">
          评级合计 {hasFiniteTotal ? formatBalanceWorkbookWanAmountDisplay(totalWan) : "未取到"}
        </span>
        <span className="balance-analysis-rating-reconciliation__note">
          Workbook 原币面值口径，合计对齐债券资产卡片；不等同于页面 CNY 市值或 CNX 总账控制数。
        </span>
      </div>
    </div>
  );
}

function renderMaturityGapPanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 6);
  if (!hasWorkbookFields(rows, ["bucket", "gap_amount"])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：期限缺口字段不完整。");
  }
  const maxAbs = maxAbsFiniteChartScale(rows.map((row) => row.gap_amount));
  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list balance-analysis-mini-list--tight">
      {rows.map((row, index) => {
        const mag = parseBalanceChartMagnitude(row.gap_amount);
        const widthPct = gapChartBarWidthPercent(mag, maxAbs);
        const width = widthPct == null ? "0%" : `${widthPct}%`;
        const positive = mag.kind === "finite" ? mag.value >= 0 : true;
        return (
          <article
            key={`${table.key}-${index}`}
            className="balance-analysis-gap-card"
            data-direction={positive ? "positive" : "negative"}
          >
            <div className="balance-analysis-mini-topline">
              <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">
                {formatBalanceWorkbookCellDisplay(row.bucket)}
              </div>
              <div
                className={`balance-analysis-mini-value balance-analysis-mini-value--${positive ? "info" : "warning"}`}
              >
                {formatBalanceWorkbookWanAmountDisplay(row.gap_amount)}
              </div>
            </div>
            <div className="balance-analysis-mini-bar-track">
              <div
                data-testid={`balance-analysis-maturity-gap-bar-${table.key}-${index}`}
                style={{
                  width,
                  background: positive
                    ? `linear-gradient(90deg, ${designTokens.color.info[300]} 0%, ${designTokens.color.info[600]} 100%)`
                    : `linear-gradient(90deg, ${designTokens.color.warning[300]} 0%, ${designTokens.color.warning[400]} 100%)`,
                }}
                className="balance-analysis-mini-bar-fill"
              />
            </div>
            {!positive ? (
              <div className="balance-analysis-gap-note">
                负缺口，应优先结合右侧治理信号处理。
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

function renderIssuancePanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 4);
  if (!hasWorkbookFields(rows, ["bond_type", "balance_amount"])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：发行类分析字段不完整。");
  }
  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list">
      {rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          className="balance-analysis-ledger-card"
        >
          <div className="balance-analysis-mini-topline">
            <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">{formatBalanceWorkbookCellDisplay(row.bond_type)}</div>
            <div className="balance-analysis-mini-value balance-analysis-mini-value--info">
              {formatBalanceWorkbookWanAmountDisplay(row.balance_amount)}
            </div>
          </div>
          <div className="balance-analysis-ledger-meta-row">
            <span>笔数 {formatBalanceWorkbookCellDisplay(row.count)}</span>
            <span>利率 {formatBalanceWorkbookMetricTwoDecimals(row.weighted_rate_pct)}</span>
            <span>期限 {formatBalanceWorkbookMetricTwoDecimals(row.weighted_term_years)}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function withYiUnit(value: string): string {
  return value === "—" ? value : `${value} 亿`;
}

function formatSignedBalanceYuanToYi(value: number | null): string {
  if (value === null) {
    return "—";
  }
  const formatted = formatBalanceAmountToYiFromYuan(value);
  return value > 0 ? `+${formatted}` : formatted;
}

function renderReconciliationMetricTile({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="balance-analysis-reconciliation__tile">
      <span className="balance-analysis-reconciliation__tile-label">{label}</span>
      <strong className="balance-analysis-reconciliation__tile-value">
        {value}
      </strong>
      <span className="balance-analysis-reconciliation__tile-detail">{detail}</span>
    </div>
  );
}

function renderBalanceReconciliationLinkPanel(
  model: ReturnType<typeof buildBalanceReconciliationLinkModel>,
) {
  const failedInternalCheck = model.internalChecks.find((check) => !check.aligned);
  const bridgeDetail = model.bridgeComponents
    .map((component) => `${component.label} ${withYiUnit(formatBalanceAmountToYiFromYuan(component.amountYuan))}`)
    .join(" · ");

  return (
    <section data-testid="balance-analysis-reconciliation-link" className="balance-analysis-reconciliation">
      <div className="balance-analysis-reconciliation__header">
        <div>
          <h3 className="balance-analysis-reconciliation__title">口径联动核对</h3>
          <p className="balance-analysis-reconciliation__copy">
            从 workbook 原币面值出发，桥接到 Formal CNY 的 AC/OCI/TPL，再落到余额变动 CNX 控制数。
          </p>
        </div>
        <span className={`balance-analysis-reconciliation__status balance-analysis-reconciliation__status--${model.status}`}>
          {model.statusLabel}
        </span>
      </div>
      <div className="balance-analysis-reconciliation__grid">
        {renderReconciliationMetricTile({
          label: "工作簿自校验",
          value: model.allInternalChecksAligned ? "已对齐" : "待复核",
          detail: failedInternalCheck
            ? `${failedInternalCheck.label}：${failedInternalCheck.leftLabel} 与 ${failedInternalCheck.rightLabel} 不一致`
            : "债券业务、评级、期限债券和发行类切片已回到同一组卡片值。",
        })}
        {renderReconciliationMetricTile({
          label: "Workbook 原币资产",
          value: withYiUnit(formatBalanceAmountToYiFromWan(model.workbookAssetTotalWan)),
          detail: `债券资产 ${withYiUnit(formatBalanceAmountToYiFromWan(model.workbookBondWan))}，期限缺口 ${withYiUnit(formatBalanceAmountToYiFromWan(model.workbookGapWan))}`,
        })}
        {renderReconciliationMetricTile({
          label: "Formal CNY 桥",
          value: withYiUnit(formatBalanceAmountToYiFromYuan(model.formalBridgeYuan)),
          detail: bridgeDetail || "等待口径拆解返回 AC/OCI/TPL 分桶。",
        })}
        {renderReconciliationMetricTile({
          label: "余额变动 CNX",
          value: withYiUnit(formatBalanceAmountToYiFromYuan(model.movementControlYuan)),
          detail: `残差 ${withYiUnit(formatSignedBalanceYuanToYi(model.residualYuan))}；${model.statusDetail}`,
        })}
      </div>
      <div className="balance-analysis-reconciliation__footer">
        <a href={model.movementHref} className="balance-analysis-reconciliation__link">
          打开余额变动核对
        </a>
        <span className="balance-analysis-reconciliation__footnote">
          全口径缺口 {withYiUnit(formatBalanceAmountToYiFromWan(model.workbookFullScopeGapWan))}
        </span>
      </div>
    </section>
  );
}

function renderWorkbookPrimaryPanel(table: BalanceAnalysisWorkbookTable) {
  if (table.key === "bond_business_types") {
    return renderDistributionPanel(table, {
      labelKey: "bond_type",
      valueKey: "balance_amount",
      color: `linear-gradient(90deg, ${designTokens.color.info[300]} 0%, ${designTokens.color.info[600]} 100%)`,
    });
  }
  if (table.key === "rating_analysis") {
    return renderRatingPanel(table);
  }
  if (table.key === "maturity_gap") {
    return renderMaturityGapPanel(table);
  }
  if (table.key === "issuance_business_types") {
    return renderIssuancePanel(table);
  }
  return null;
}

function renderIndustryPanel(table: BalanceAnalysisWorkbookTable) {
  return renderDistributionPanel(table, {
    labelKey: "industry_name",
    valueKey: "balance_amount",
    color: `linear-gradient(90deg, ${designTokens.color.success[200]} 0%, ${designTokens.color.success[500]} 100%)`,
  });
}

function renderRateDistributionPanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 5);
  if (!hasWorkbookFields(rows, [
    "bucket",
    "bond_amount",
    "interbank_asset_amount",
    "interbank_liability_amount",
  ])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：利率分布字段不完整。");
  }

  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list">
      {rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          className="balance-analysis-ledger-card"
        >
          <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">{formatBalanceWorkbookCellDisplay(row.bucket)}</div>
          <div className="balance-analysis-rate-grid">
            <div>
              <div className="balance-analysis-rate-grid__label">债券</div>
              <div className="balance-analysis-mini-value balance-analysis-mini-value--info">
                {formatBalanceWorkbookWanAmountDisplay(row.bond_amount)}
              </div>
            </div>
            <div>
              <div className="balance-analysis-rate-grid__label">同业资产</div>
              <div className="balance-analysis-mini-value balance-analysis-mini-value--success">
                {formatBalanceWorkbookWanAmountDisplay(row.interbank_asset_amount)}
              </div>
            </div>
            <div>
              <div className="balance-analysis-rate-grid__label">同业负债</div>
              <div className="balance-analysis-mini-value balance-analysis-mini-value--warning-soft">
                {formatBalanceWorkbookWanAmountDisplay(row.interbank_liability_amount)}
              </div>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

function renderCounterpartyPanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 4);
  if (!hasWorkbookFields(rows, [
    "counterparty_type",
    "asset_amount",
    "liability_amount",
    "net_position_amount",
  ])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：对手方类型字段不完整。");
  }

  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list">
      {rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          className="balance-analysis-ledger-card"
        >
          <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">{formatBalanceWorkbookCellDisplay(row.counterparty_type)}</div>
          <div className="balance-analysis-ledger-meta-row">
            <span className="balance-analysis-mini-value--info">
              资产 {formatBalanceWorkbookWanAmountDisplay(row.asset_amount)}
            </span>
            <span className="balance-analysis-mini-value--warning-soft">
              负债 {formatBalanceWorkbookWanAmountDisplay(row.liability_amount)}
            </span>
            <span className="balance-analysis-mini-value--net">
              净头寸 {formatBalanceWorkbookWanAmountDisplay(row.net_position_amount)}
            </span>
          </div>
        </article>
      ))}
    </div>
  );
}

function renderDecisionItemsPanel(
  rows: BalanceAnalysisDecisionItemStatusRow[],
  {
    selectedKey,
    updatingKey,
    onSelect,
    onUpdateStatus,
  }: {
    selectedKey: string | null;
    updatingKey: string | null;
    onSelect: (row: BalanceAnalysisDecisionItemStatusRow) => void;
    onUpdateStatus: (
      row: BalanceAnalysisDecisionItemStatusRow,
      status: "confirmed" | "dismissed",
    ) => void;
  },
) {
  if (rows.length === 0) {
    return renderWorkbookEmptyState("暂无治理事项。");
  }
  const hasRequiredFields = rows.every(
    (row) =>
      row.decision_key &&
      row.title &&
      row.action_label &&
      row.severity &&
      row.reason &&
      row.source_section &&
      row.rule_id &&
      row.rule_version &&
      row.latest_status &&
      row.latest_status.decision_key &&
      row.latest_status.status,
  );
  if (!hasRequiredFields) {
    return renderWorkbookContractMismatch(
      { key: "decision_items" },
      "Workbook contract mismatch：决策事项字段不完整。",
    );
  }

  return (
    <div data-testid="balance-analysis-workbook-table-decision_items" className="balance-analysis-mini-list">
      {rows.map((row, index) => (
        <article
          key={row.decision_key}
          className="balance-analysis-ledger-card"
          data-selected={selectedKey === row.decision_key ? "true" : "false"}
        >
          <div className="balance-analysis-mini-topline">
            <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">
              {formatBalanceBusinessTextDisplay(row.title)}
            </div>
            <span className="balance-analysis-panel-badge">{formatBalanceGovernedSeverityDisplay(row.severity)}</span>
          </div>
          <div className="balance-analysis-ledger-copy-text">
            {formatBalanceBusinessTextDisplay(row.reason)}
          </div>
          <div className="balance-analysis-ledger-meta-row">
            <span>{formatBalanceBusinessTextDisplay(row.action_label)}</span>
            <span>{formatBalanceDecisionWorkflowStatusDisplay(row.latest_status.status)}</span>
            <span>
              更新人：{row.latest_status.updated_by ? row.latest_status.updated_by : "未更新"}
            </span>
          </div>
          <div className="balance-analysis-action-row">
            <button
              data-testid={`balance-analysis-decision-confirm-${index}`}
              type="button"
              disabled={updatingKey === row.decision_key}
              className="balance-analysis-mini-button"
              onClick={() => onUpdateStatus(row, "confirmed")}
            >
              确认
            </button>
            <button
              data-testid={`balance-analysis-decision-dismiss-${index}`}
              type="button"
              disabled={updatingKey === row.decision_key}
              className="balance-analysis-mini-button"
              onClick={() => onUpdateStatus(row, "dismissed")}
            >
              忽略
            </button>
            <button
              data-testid={`balance-analysis-decision-view-status-${index}`}
              type="button"
              className="balance-analysis-mini-button"
              onClick={() => onSelect(row)}
            >
              详情
            </button>
          </div>
        </article>
      ))}
    </div>
  );
}

function renderEventCalendarPanel(
  table: Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "event_calendar" }>,
  {
    onSelect,
    selectedKey,
  }: {
    onSelect: (row: BalanceAnalysisEventCalendarRow) => void;
    selectedKey: string | null;
  },
) {
  if (table.rows.length === 0) {
    return renderWorkbookEmptyState("暂无治理事项。");
  }
  if (
    !hasWorkbookFields(table.rows, [
      "event_date",
      "event_type",
      "title",
      "source",
      "impact_hint",
      "source_section",
    ])
  ) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：事件日历字段不完整。");
  }

  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list">
      {table.rows.map((row, index) => (
        <button
          key={`${table.key}-${index}`}
          type="button"
          onClick={() => onSelect(row)}
          className="balance-analysis-right-rail-button"
        >
          <article
            className="balance-analysis-ledger-card"
            data-selected={selectedKey === `${row.event_date}:${row.title}` ? "true" : "false"}
          >
            <div className="balance-analysis-mini-topline">
              <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">
                {formatBalanceBusinessTextDisplay(row.title)}
              </div>
              <div className="balance-analysis-mini-value--info">{formatBalanceWorkbookCellDisplay(row.event_date)}</div>
            </div>
            <div className="balance-analysis-ledger-copy-text">
              {formatBalanceBusinessTextDisplay(row.impact_hint)}
            </div>
            <div className="balance-analysis-ledger-meta-row">
              <span>{formatBalanceBusinessTextDisplay(row.event_type)}</span>
              <span>{formatBalanceBusinessTextDisplay(row.source)}</span>
            </div>
          </article>
        </button>
      ))}
    </div>
  );
}

function renderRiskAlertsPanel(
  table: Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "risk_alerts" }>,
  {
    onSelect,
    selectedKey,
  }: {
    onSelect: (row: BalanceAnalysisRiskAlertRow) => void;
    selectedKey: string | null;
  },
) {
  if (table.rows.length === 0) {
    return renderWorkbookEmptyState("暂无治理事项。");
  }
  if (
    !hasWorkbookFields(table.rows, [
      "title",
      "severity",
      "reason",
      "source_section",
      "rule_id",
      "rule_version",
    ])
  ) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：风险预警字段不完整。");
  }

  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} className="balance-analysis-mini-list">
      {table.rows.map((row, index) => (
        <button
          key={`${table.key}-${index}`}
          type="button"
          onClick={() => onSelect(row)}
          className="balance-analysis-right-rail-button"
        >
          <article
            className="balance-analysis-ledger-card balance-analysis-ledger-card--warning"
            data-selected={selectedKey === `${row.severity}:${row.title}` ? "true" : "false"}
          >
            <div className="balance-analysis-mini-topline">
              <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">
                {formatBalanceBusinessTextDisplay(row.title)}
              </div>
              <span className="balance-analysis-panel-badge balance-analysis-panel-badge--warning">
                {formatBalanceGovernedSeverityDisplay(row.severity)}
              </span>
            </div>
            <div className="balance-analysis-ledger-copy-text balance-analysis-ledger-copy-text--warning">
              {formatBalanceBusinessTextDisplay(row.reason)}
            </div>
            <div className="balance-analysis-ledger-meta-row balance-analysis-ledger-meta-row--warning">
              <span>{formatBalanceWorkbookOperationalSectionKeyDisplay(row.source_section)}</span>
            </div>
          </article>
        </button>
      ))}
    </div>
  );
}

function renderWorkbookSecondaryPanel(table: BalanceAnalysisWorkbookTable) {
  if (table.key === "industry_distribution") {
    return renderIndustryPanel(table);
  }
  if (table.key === "rate_distribution") {
    return renderRateDistributionPanel(table);
  }
  if (table.key === "counterparty_types") {
    return renderCounterpartyPanel(table);
  }
  return null;
}

function renderWorkbookRightRailPanel(table: BalanceAnalysisWorkbookOperationalSection) {
  void table;
  return null;
}

export default function BalanceAnalysisPage() {
  const client = useApiClient();
  const [summaryOffset, setSummaryOffset] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isExportingCsv, setIsExportingCsv] = useState(false);
  const [isExportingWorkbook, setIsExportingWorkbook] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [decisionActionError, setDecisionActionError] = useState<string | null>(null);
  const [updatingDecisionKey, setUpdatingDecisionKey] = useState<string | null>(null);
  const [eventTypeFilter, setEventTypeFilter] = useState("all");
  const [riskSeverityFilter, setRiskSeverityFilter] = useState<"all" | BalanceAnalysisSeverity>("all");
  const [selectedDecisionKey, setSelectedDecisionKey] = useState<string | null>(null);
  const [selectedEventCalendarKey, setSelectedEventCalendarKey] = useState<string | null>(null);
  const [selectedRiskAlertKey, setSelectedRiskAlertKey] = useState<string | null>(null);
  const [decisionStatusComment, setDecisionStatusComment] = useState("");
  const {
    selectedReportDate,
    positionScope,
    currencyBasis,
    setSelectedReportDate,
    setPositionScope,
    setCurrencyBasis,
    datesQuery,
    overviewQuery,
    detailQuery,
    workbookQuery,
    currentUserQuery,
    decisionItemsQuery,
    summaryQuery,
    basisBreakdownQuery,
    adbComparisonQuery,
    advancedAttributionQuery,
    movementDatesQuery,
    movementLinkQuery,
    overview,
    overviewMeta,
    detailMeta,
    decisionItemsMeta,
    workbookMeta,
    summaryMeta,
    currentUser,
    decisionRows,
    workbook,
    summaryTable,
    workbookTables,
    primaryWorkbookTables,
    secondaryWorkbookPanelTables,
    filteredRightRailWorkbookTables,
    eventTypeOptions,
    eventCalendarRows,
    riskAlertRows,
    workbookDecisionRows,
    detailSummaryGridRows,
    detailGridRows,
    selectedDecision,
    selectedEventCalendar,
    selectedRiskAlert,
    isBondBusinessLinkedToMovement,
    isIndustryLinkedToMovement,
    movementDateAvailable,
    deferredAnalysisQueriesEnabled,
    deferredAnalysisQueriesPending,
    totalPages,
    currentPage,
    adbHref,
    PAGE_SIZE: pageSize,
  } = useBalanceAnalysisData({
    summaryOffset,
    eventTypeFilter,
    riskSeverityFilter,
    selectedDecisionKey,
    selectedEventCalendarKey,
    selectedRiskAlertKey,
  });

  useEffect(() => {
    setSummaryOffset(0);
  }, [selectedReportDate, positionScope, currencyBasis]);

  useEffect(() => {
    setDecisionActionError(null);
    setSelectedDecisionKey(null);
    setSelectedEventCalendarKey(null);
    setSelectedRiskAlertKey(null);
    setDecisionStatusComment("");
  }, [selectedReportDate, positionScope, currencyBasis]);

  const secondaryWorkbookTables = workbookTables.filter(
    (table) =>
      !primaryWorkbookTableKeys.includes(table.key as (typeof primaryWorkbookTableKeys)[number]) &&
      !secondaryWorkbookPanelKeys.includes(table.key as (typeof secondaryWorkbookPanelKeys)[number]),
  );
  const resultMetaSections = [
    overviewMeta ? { key: "overview", title: "总览结果元信息", meta: overviewMeta } : null,
    decisionItemsMeta
      ? { key: "decision-items", title: "决策结果元信息", meta: decisionItemsMeta }
      : null,
    workbookMeta ? { key: "workbook", title: "工作簿结果元信息", meta: workbookMeta } : null,
    summaryMeta ? { key: "summary", title: "汇总结果元信息", meta: summaryMeta } : null,
    detailMeta ? { key: "detail", title: "明细结果元信息", meta: detailMeta } : null,
  ].filter(
    (
      section,
    ): section is { key: string; title: string; meta: NonNullable<typeof overviewMeta> } =>
      section !== null,
  );
  const pageModel = buildBalanceAnalysisPageModel({
    clientMode: client.mode,
    selectedReportDate,
    positionScope,
    currencyBasis,
    overview,
    summary: summaryTable,
    decisionItems: decisionItemsQuery.data?.result,
    workbook,
    summaryRows: detailQuery.data?.result.summary ?? [],
    decisionRows,
    workbookDecisionRows,
    eventCalendarRows,
    riskAlertRows,
    metaSections: resultMetaSections,
  });
  const pageReadModel = pageModel.readModel;
  const evidenceMetas = resultMetaSections.map((section) => section.meta);
  const balanceAttentionReasons: BalanceAttentionReason[] = [
    ...(pageReadModel.dateStatus === "mismatch"
      ? [
          {
            key: "date-mismatch",
            sentinel: "error" as const,
            detail: "请求报告日与返回报告日不一致。",
          },
        ]
      : []),
    ...pageReadModel.statusBadges
      .filter((badge) => ["danger", "warning"].includes(badge.tone))
      .map((badge): BalanceAttentionReason => ({
        key: `status-badge-${badge.key}`,
        sentinel: badge.key === "stale" ? "stale" : badge.key === "fallback" ? "fallback" : "error",
        detail: `读面标记需关注：${badge.label}`,
      })),
    ...resultMetaSections.flatMap((section): BalanceAttentionReason[] => {
      const reasons: BalanceAttentionReason[] = [];
      if (section.meta.basis !== "formal") {
        reasons.push({
          key: `meta-basis-${section.key}`,
          sentinel: "error",
          detail: `${section.title} 当前为${formatAttentionBasis(section.meta.basis)}，需复核。`,
        });
      }
      if (section.meta.quality_flag === "stale") {
        reasons.push({
          key: `meta-stale-${section.key}`,
          sentinel: "stale",
          detail: `${section.title} 标记为陈旧。`,
        });
      } else if (section.meta.quality_flag !== "ok") {
        reasons.push({
          key: `meta-quality-${section.key}`,
          sentinel: "error",
          detail: `${section.title} 质量标记为${formatAttentionQuality(section.meta.quality_flag)}。`,
        });
      }
      if (section.meta.fallback_mode !== "none") {
        reasons.push({
          key: `meta-fallback-${section.key}`,
          sentinel: "fallback",
          detail: `${section.title} 使用${formatAttentionFallback(section.meta.fallback_mode)}。`,
        });
      }
      return reasons;
    }),
    ...pageReadModel.stateSurfaces
      .filter((state) => ["error", "stale", "fallback-date"].includes(state.variant))
      .map((state): BalanceAttentionReason => ({
        key: `state-surface-${state.key}`,
        sentinel: state.variant === "stale" ? "stale" : state.variant === "fallback-date" ? "fallback" : "error",
        detail: `${state.title}：${state.description}`,
      })),
    ...(refreshError
      ? [
          {
            key: "refresh-error",
            sentinel: "error" as const,
            detail: refreshError,
          },
        ]
      : []),
    ...(decisionActionError
      ? [
          {
            key: "decision-action-error",
            sentinel: "error" as const,
            detail: decisionActionError,
          },
        ]
      : []),
    ...[
      { key: "dates-query", label: "报告日读面暂未返回", query: datesQuery },
      { key: "overview-query", label: "首屏总览暂未返回", query: overviewQuery },
      { key: "workbook-query", label: "工作簿图谱暂未返回", query: workbookQuery },
      { key: "decision-items-query", label: "治理队列暂未返回", query: decisionItemsQuery },
      { key: "summary-query", label: "汇总分页暂未返回", query: summaryQuery },
      { key: "detail-query", label: "明细底稿暂未返回", query: detailQuery },
      { key: "basis-query", label: "口径拆解暂未返回", query: basisBreakdownQuery },
      { key: "adb-query", label: "日均对比暂未返回", query: adbComparisonQuery },
      { key: "advanced-attribution-query", label: "高阶归因暂未返回", query: advancedAttributionQuery },
      { key: "movement-dates-query", label: "余额变动报告日暂未返回", query: movementDatesQuery },
      { key: "movement-link-query", label: "余额变动联动暂未返回", query: movementLinkQuery },
      { key: "current-user-query", label: "当前权限暂未返回", query: currentUserQuery },
    ].flatMap(({ key, label, query }): BalanceAttentionReason[] =>
      query.isError
        ? [
            {
              key,
              sentinel: "error",
              detail: label,
            },
          ]
        : [],
    ),
  ];
  const evidenceLedgerNeedsAttention = balanceAttentionReasons.length > 0;
  const evidenceLedgerSummary =
    evidenceMetas.length > 0
      ? evidenceLedgerNeedsAttention
        ? [
            `${evidenceMetas.length} 个读面`,
            evidenceMetas.every((meta) => meta.basis === "formal") ? "formal" : "混合口径",
            evidenceMetas.every((meta) => meta.quality_flag === "ok")
              ? "质量正常"
              : "质量需复核",
            evidenceMetas.every((meta) => meta.fallback_mode === "none")
              ? "未降级"
              : "存在降级",
            evidenceMetas.every((meta) => Boolean(meta.trace_id))
              ? "链路可追溯"
              : "链路待补齐",
          ].join(" · ")
        : [
            `${evidenceMetas.length} 个读面`,
            evidenceMetas.every((meta) => Boolean(meta.trace_id))
              ? "链路可追溯"
              : "链路待补齐",
          ].join(" · ")
      : "等待正式读面元数据";
  const attentionStatusBadges = pageReadModel.statusBadges.filter((badge) =>
    ["danger", "warning"].includes(badge.tone) &&
    (badge.key !== "date" || pageReadModel.dateStatus === "mismatch"),
  );
  const reportDateUnavailable = !selectedReportDate && !datesQuery.isLoading;
  const reportDateUnavailableTitle = datesQuery.isError
    ? "报告日暂未接入"
    : "当前没有可用报告日";
  const reportDateUnavailableDescription = datesQuery.isError
    ? "页面暂时拿不到报告日，先收起空指标和底稿区；重新读取后会展示缺口、规模和治理动作。"
    : "等报告日返回后，会自动展示缺口、规模和治理动作；当前先保留筛选和读取入口。";
  const reconciliationLinkModel = buildBalanceReconciliationLinkModel({
    reportDate: selectedReportDate,
    workbook,
    basisRows: basisBreakdownQuery.data?.result.rows ?? [],
    movement: movementLinkQuery.data?.result ?? null,
    movementAvailableForDate: movementDateAvailable,
    isPending:
      deferredAnalysisQueriesPending ||
      basisBreakdownQuery.isLoading ||
      movementDatesQuery.isLoading ||
      (movementDateAvailable && movementLinkQuery.isLoading),
  });

  const summaryEndpointStatus = queryEndpointStatus(
    summaryQuery,
    Boolean(selectedReportDate) && overviewQuery.isSuccess,
  );
  const detailEndpointStatus = queryEndpointStatus(detailQuery, deferredAnalysisQueriesEnabled);
  const basisEndpointStatus = queryEndpointStatus(basisBreakdownQuery, deferredAnalysisQueriesEnabled);
  const adbEndpointStatus = queryEndpointStatus(adbComparisonQuery, deferredAnalysisQueriesEnabled);
  const movementDetailEndpointStatus =
    deferredAnalysisQueriesEnabled && !movementDateAvailable
      ? "idle"
      : queryEndpointStatus(
          movementLinkQuery,
          deferredAnalysisQueriesEnabled && movementDateAvailable,
        );
  const attributionEndpointStatus = queryEndpointStatus(
    advancedAttributionQuery,
    deferredAnalysisQueriesEnabled,
  );
  const endpointGroups: BalanceEndpointGroup[] = [
    {
      key: "first-screen",
      title: "首屏",
      description: "报告日、总览、工作簿、治理、汇总、权限、余额变动",
      count: 7,
      tone: "primary",
      endpoints: [
        {
          key: "dates",
          label: "报告日列表",
          path: "GET /ui/balance-analysis/dates",
          status: queryEndpointStatus(datesQuery),
          value: datesQuery.data ? `${datesQuery.data.result.report_dates.length} 个报告日` : "待返回",
          detail: "报告日选择器与默认报告日。",
        },
        {
          key: "overview",
          label: "首屏总览",
          path: "GET /ui/balance-analysis/overview",
          status: queryEndpointStatus(overviewQuery, Boolean(selectedReportDate)),
          value: overviewMeta?.basis === "formal" ? "正式口径" : (overviewMeta?.basis ?? "待返回"),
          detail: "正式读面、规模和首屏 KPI 的主来源。",
        },
        {
          key: "workbook",
          label: "工作簿图谱",
          path: "GET /ui/balance-analysis/workbook",
          status: queryEndpointStatus(workbookQuery, Boolean(selectedReportDate)),
          value: workbook ? `${workbook.cards.length} 张卡片` : "待返回",
          detail: "工作簿结构、风险预警、事件和治理动作。",
        },
        {
          key: "decision-items",
          label: "治理队列",
          path: "GET /ui/balance-analysis/decision-items",
          status: queryEndpointStatus(decisionItemsQuery, Boolean(selectedReportDate)),
          value: `${decisionRows.length} 项`,
          detail: "治理队列和首页主动作。",
        },
        {
          key: "summary",
          label: "汇总分页",
          path: "GET /ui/balance-analysis/summary",
          status: summaryEndpointStatus,
          value: summaryTable ? `${summaryTable.rows.length} 行` : "待返回",
          detail: "汇总表分页和有效读面行数。",
        },
        {
          key: "current-user",
          label: "当前权限",
          path: "GET /ui/balance-analysis/current-user",
          status: queryEndpointStatus(currentUserQuery),
          value: currentUser ? formatCurrentUserRoleDisplay(currentUser.role) : "待返回",
          detail: "治理动作提交人与身份来源。",
        },
        {
          key: "movement-dates",
          label: "余额变动报告日",
          path: "GET /ui/balance-movement-analysis/dates",
          status: queryEndpointStatus(movementDatesQuery, Boolean(selectedReportDate)),
          value: movementDatesQuery.data ? `${movementDatesQuery.data.result.report_dates.length} 个报告日` : "待返回",
          detail: "判断余额变动联动是否可用。",
        },
      ],
    },
    {
      key: "deferred",
      title: "补充",
      description: "明细、口径、日均、变动、归因",
      count: 5,
      tone: "info",
      endpoints: [
        {
          key: "detail",
          label: "明细底稿",
          path: "GET /ui/balance-analysis",
          status: detailEndpointStatus,
          value: detailQuery.data ? `${detailQuery.data.result.details.length} 行` : "等待首屏",
          detail: "明细底稿和明细汇总下钻。",
        },
        {
          key: "summary-by-basis",
          label: "口径拆解",
          path: "GET /ui/balance-analysis/summary-by-basis",
          status: basisEndpointStatus,
          value: basisBreakdownQuery.data ? `${basisBreakdownQuery.data.result.rows.length} 组` : "待口径",
          detail: "按会计口径、头寸范围和币种拆解。",
        },
        {
          key: "adb-comparison",
          label: "日均对比",
          path: "GET /api/analysis/adb/comparison",
          status: adbEndpointStatus,
          value:
            adbComparisonQuery.data?.net_interest_margin == null
              ? "等待日均"
              : `${adbComparisonQuery.data.net_interest_margin.toFixed(2)}% 净息差`,
          detail: "日均资产负债和净息差解释材料。",
        },
        {
          key: "movement-detail",
          label: "余额变动联动",
          path: "GET /ui/balance-movement-analysis",
          status: movementDetailEndpointStatus,
          value: movementDateAvailable ? "可联动" : "无联动",
          detail: movementDateAvailable ? "余额变动联动可用。" : "当前报告日无余额变动联动。",
        },
        {
          key: "advanced-attribution",
          label: "高阶归因",
          path: "GET /ui/balance-analysis/advanced-attribution",
          status: attributionEndpointStatus,
          value:
            advancedAttributionQuery.data?.result.status === "not_ready" ? "部分可用" : "情景材料",
          detail: "高阶归因的可用组件、缺失输入和提示。",
        },
      ],
    },
    {
      key: "actions",
      title: "动作",
      description: "刷新、进度、导出、治理处理",
      count: 5,
      tone: "action",
      endpoints: [
        {
          key: "refresh",
          label: "刷新正式结果",
          path: "POST /ui/balance-analysis/refresh",
          status: actionEndpointStatus({
            isError: Boolean(refreshError),
            isLoading: isRefreshing,
            isActive: Boolean(selectedReportDate),
          }),
          value: isRefreshing ? "刷新中" : "手动触发",
          detail: "触发正式结果重建。",
        },
        {
          key: "refresh-status",
          label: "刷新进度",
          path: "GET /ui/balance-analysis/refresh-status",
          status: actionEndpointStatus({
            isError: Boolean(refreshError),
            isLoading: Boolean(refreshStatus && isRefreshing),
            isActive: Boolean(refreshStatus),
          }),
          value: refreshStatus ?? "待触发",
          detail: refreshStatus ? "刷新任务已有反馈。" : "刷新任务反馈轮询。",
        },
        {
          key: "summary-export",
          label: "导出汇总表",
          path: "GET /ui/balance-analysis/summary/export",
          status: actionEndpointStatus({
            isError: Boolean(refreshError),
            isLoading: isExportingCsv,
            isActive: Boolean(selectedReportDate),
          }),
          value: "CSV",
          detail: "导出汇总 CSV。",
        },
        {
          key: "workbook-export",
          label: "导出工作簿",
          path: "GET /ui/balance-analysis/workbook/export",
          status: actionEndpointStatus({
            isError: Boolean(refreshError),
            isLoading: isExportingWorkbook,
            isActive: Boolean(selectedReportDate),
          }),
          value: "Excel",
          detail: "导出工作簿 Excel。",
        },
        {
          key: "decision-status",
          label: "治理处理",
          path: "POST /ui/balance-analysis/decision-items/status",
          status: actionEndpointStatus({
            isError: Boolean(decisionActionError),
            isLoading: Boolean(updatingDecisionKey),
            isActive: decisionItemsQuery.isSuccess,
          }),
          value: `${decisionRows.length} 项`,
          detail: "确认、忽略并同步治理处理结果。",
        },
      ],
    },
  ];
  const deferredSurfaces: BalanceDeferredSurface[] = [
    {
      key: "detail-ledger",
      title: "明细底稿",
      endpoint: "明细读面",
      status: detailEndpointStatus,
      value: detailQuery.data ? `${detailQuery.data.result.details.length} 行` : "等待首屏",
      detail: `明细汇总 ${detailQuery.data?.result.summary.length ?? 0} 组，用于正式汇总下钻。`,
    },
    {
      key: "basis-breakdown",
      title: "口径分解",
      endpoint: "口径读面",
      status: basisEndpointStatus,
      value: `${basisBreakdownQuery.data?.result.rows.length ?? 0} 组`,
      detail: "解释不同会计口径、头寸范围和币种组合。",
    },
    {
      key: "adb-comparison",
      title: "日均对比",
      endpoint: "日均读面",
      status: adbEndpointStatus,
      value:
        adbComparisonQuery.data?.net_interest_margin == null
          ? "等待日均"
          : `${adbComparisonQuery.data.net_interest_margin.toFixed(2)}% 净息差`,
      detail: "辅助比较时点与日均口径，不提升为正式主指标。",
    },
    {
      key: "movement-link",
      title: "变动联动",
      endpoint: "变动读面",
      status: movementDetailEndpointStatus,
      value: movementDateAvailable ? "可联动" : "无同日报告",
      detail: "承接资产分类和行业分布联动证据。",
    },
    {
      key: "advanced-attribution",
      title: "高级归因",
      endpoint: "归因读面",
      status: attributionEndpointStatus,
      value:
        advancedAttributionQuery.data?.result.status === "not_ready"
          ? "未就绪"
          : advancedAttributionQuery.data?.result.status
            ? "情景材料"
            : "等待输入",
      detail: `缺失输入 ${advancedAttributionQuery.data?.result.missing_inputs.length ?? 0} 项，提示 ${
        advancedAttributionQuery.data?.result.warnings.length ?? 0
      } 条。`,
    },
  ];
  const hasStaleAttention = balanceAttentionReasons.some((reason) => reason.sentinel === "stale");
  const hasFallbackAttention = balanceAttentionReasons.some((reason) => reason.sentinel === "fallback");
  const hasErrorAttention = balanceAttentionReasons.some((reason) => reason.sentinel === "error");
  const stateSentinels: BalanceStateSentinel[] = [
    {
      key: "stale",
      label: "陈旧",
      active: hasStaleAttention,
      status: hasStaleAttention ? "error" : "ready",
      detail: firstAttentionDetail(balanceAttentionReasons, "stale", "未发现陈旧读面。"),
    },
    {
      key: "fallback",
      label: "降级",
      active: hasFallbackAttention,
      status: hasFallbackAttention ? "error" : "ready",
      detail: firstAttentionDetail(balanceAttentionReasons, "fallback", "未发现降级读面。"),
    },
    {
      key: "error",
      label: "需处理",
      active: hasErrorAttention,
      status: hasErrorAttention ? "error" : "ready",
      detail: firstAttentionDetail(balanceAttentionReasons, "error", "未发现待处理事项。"),
    },
  ];

  async function handleRefresh() {
    if (!selectedReportDate) {
      return;
    }
    setIsRefreshing(true);
    setRefreshError(null);
    try {
      const payload = await runPollingTask({
        start: () => client.refreshBalanceAnalysis(selectedReportDate),
        getStatus: (runId) => client.getBalanceAnalysisRefreshStatus(runId),
        onUpdate: (nextPayload) => {
          setRefreshStatus(formatRefreshStatusDisplay(nextPayload.status));
        },
      });
      if (payload.status !== "completed") {
        throw new Error(payload.error_message ?? payload.detail ?? `刷新未完成：${payload.status}`);
      }
      await Promise.all([
        datesQuery.refetch(),
        overviewQuery.refetch(),
        decisionItemsQuery.refetch(),
        workbookQuery.refetch(),
        detailQuery.refetch(),
        summaryQuery.refetch(),
        basisBreakdownQuery.refetch(),
        movementDatesQuery.refetch(),
        movementDateAvailable ? movementLinkQuery.refetch() : Promise.resolve(),
        adbComparisonQuery.refetch(),
        advancedAttributionQuery.refetch(),
      ]);
    } catch {
      setRefreshError(formatOperationIssueDisplay("refresh"));
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleDecisionStatusUpdate(
    row: BalanceAnalysisDecisionItemStatusRow,
    status: "confirmed" | "dismissed",
  ) {
    if (!selectedReportDate) {
      return;
    }
    setDecisionActionError(null);
    setUpdatingDecisionKey(row.decision_key);
    setSelectedEventCalendarKey(null);
    setSelectedRiskAlertKey(null);
    setSelectedDecisionKey(row.decision_key);
    try {
      await client.updateBalanceAnalysisDecisionStatus({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
        decisionKey: row.decision_key,
        status,
        comment: decisionStatusComment.trim() || undefined,
      });
      await Promise.all([decisionItemsQuery.refetch(), currentUserQuery.refetch()]);
    } catch {
      setDecisionActionError(formatOperationIssueDisplay("decision"));
    } finally {
      setUpdatingDecisionKey(null);
    }
  }

  async function handleExport() {
    if (!selectedReportDate) {
      return;
    }
    setIsExportingCsv(true);
    setRefreshError(null);
    try {
      const payload = await client.exportBalanceAnalysisSummaryCsv({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      });
      downloadCsvFile(payload.filename, payload.content);
    } catch {
      setRefreshError(formatOperationIssueDisplay("summary-export"));
    } finally {
      setIsExportingCsv(false);
    }
  }

  async function handleWorkbookExport() {
    if (!selectedReportDate) {
      return;
    }
    setIsExportingWorkbook(true);
    setRefreshError(null);
    try {
      const payload = await client.exportBalanceAnalysisWorkbookXlsx({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      });
      downloadBlobFile(payload.filename, payload.content);
    } catch {
      setRefreshError(formatOperationIssueDisplay("workbook-export"));
    } finally {
      setIsExportingWorkbook(false);
    }
  }

  return (
    <section data-testid="balance-analysis-page" className="balance-analysis-page">
      <section
        data-testid="balance-analysis-contract-hero"
        className="balance-analysis-hero"
      >
        <div className="balance-analysis-hero__identity">
          <span className="balance-analysis-hero__tab">首屏问题</span>
          <div className="balance-analysis-hero__title-row">
            <h1 data-testid="balance-analysis-page-title">资产负债分析</h1>
            <span>报告日判断 · 缺口优先 · 证据闭环</span>
          </div>
          <p data-testid="balance-analysis-page-subtitle">
            先看资产负债缺口、净头寸和治理动作，再进入证据与汇总底稿。
          </p>
          <span className="balance-analysis-hero-conclusion">
            <strong>{pageReadModel.conclusionTitle}</strong>
            <span>{pageReadModel.filterLine}</span>
          </span>
        </div>
        <div className="balance-analysis-hero__meta">
          <span
            className="balance-analysis-hero__report"
            data-testid="balance-analysis-report-date-slot"
          >
            报告日 {pageReadModel.resolvedReportDate}
          </span>
          <div className="balance-analysis-hero-actions">
            <CalibrationBadge calibration={overview?.calibration} />
            <span
              className="balance-analysis-source-badge"
              data-tone={pageReadModel.sourceBadge.tone}
            >
              <SafetyCertificateOutlined aria-hidden className="balance-analysis-inline-icon" />
              {pageReadModel.sourceBadge.label}
            </span>
          </div>
        </div>
        <PageFilterTray testId="balance-analysis-filter-tray">
          <FilterBar className="balance-analysis-filter-bar">
            <label>
              <span>
                <CalendarOutlined aria-hidden className="balance-analysis-inline-icon" />
                报告日
              </span>
              <select
                aria-label="balance-report-date"
                value={selectedReportDate}
                onChange={(event) => setSelectedReportDate(event.target.value)}
                className="balance-analysis-control"
              >
                {(datesQuery.data?.result.report_dates ?? []).map((reportDate) => (
                  <option key={reportDate} value={reportDate}>
                    {reportDate}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span>
                <FilterOutlined aria-hidden className="balance-analysis-inline-icon" />
                头寸范围
              </span>
              <select
                aria-label="balance-position-scope"
                value={positionScope}
                onChange={(event) => setPositionScope(event.target.value as BalancePositionScope)}
                className="balance-analysis-control"
              >
                <option value="all">全部</option>
                <option value="asset">资产</option>
                <option value="liability">负债</option>
              </select>
            </label>

            <label>
              <span>
                <SwapOutlined aria-hidden className="balance-analysis-inline-icon" />
                币种口径
              </span>
              <select
                aria-label="balance-currency-basis"
                value={currencyBasis}
                onChange={(event) => setCurrencyBasis(event.target.value as BalanceCurrencyBasis)}
                className="balance-analysis-control"
              >
                <option value="CNY">人民币</option>
                <option value="native">原币</option>
              </select>
            </label>

            <button
              data-testid="balance-analysis-refresh-button"
              type="button"
              onClick={() => void handleRefresh()}
              disabled={!selectedReportDate || isRefreshing}
              className="balance-analysis-action-button"
            >
              <ReloadOutlined aria-hidden className="balance-analysis-inline-icon" />
              {isRefreshing ? "刷新中..." : "刷新正式结果"}
            </button>
            <button
              data-testid="balance-analysis-export-button"
              type="button"
              onClick={() => void handleExport()}
              disabled={!selectedReportDate || isExportingCsv}
              className="balance-analysis-action-button"
            >
              <DownloadOutlined aria-hidden className="balance-analysis-inline-icon" />
              {isExportingCsv ? "导出中..." : "导出 CSV"}
            </button>
            <button
              data-testid="balance-analysis-workbook-export-button"
              type="button"
              onClick={() => void handleWorkbookExport()}
              disabled={!selectedReportDate || isExportingWorkbook}
              className="balance-analysis-action-button"
            >
              <FileExcelOutlined aria-hidden className="balance-analysis-inline-icon" />
              {isExportingWorkbook ? "导出中..." : "导出 Excel"}
            </button>
          </FilterBar>
        </PageFilterTray>
      </section>

      {attentionStatusBadges.length > 0 ? (
        <DataStatusStrip
          testId="balance-analysis-data-status"
          className="balance-analysis-data-status"
        >
          {attentionStatusBadges.map((badge) => (
            <span key={badge.key} className="balance-analysis-status-badge" data-tone={badge.tone}>
              {badge.label}
            </span>
          ))}
        </DataStatusStrip>
      ) : null}

      {(refreshStatus || refreshError) && (
        <PageStateSurface
          variant={refreshError ? "error" : isRefreshing ? "loading" : "neutral"}
          title={refreshError ? "刷新未完成" : isRefreshing ? "刷新进行中" : "刷新已完成"}
          description={refreshError ?? refreshStatus}
          className="balance-analysis-refresh-state"
        />
      )}

      {reportDateUnavailable ? (
        <section
          data-testid="balance-analysis-report-date-empty"
          className="balance-analysis-report-date-empty"
        >
          <div>
            <span>等待读面</span>
            <h2>{reportDateUnavailableTitle}</h2>
            <p>{reportDateUnavailableDescription}</p>
          </div>
          <button
            type="button"
            className="balance-analysis-action-button"
            onClick={() => void datesQuery.refetch()}
          >
            <ReloadOutlined aria-hidden className="balance-analysis-inline-icon" />
            重新读取报告日
          </button>
        </section>
      ) : (
        <>
          <BalanceAnalysisWorkbenchLayout
            overview={overview}
            summary={summaryTable}
            workbook={workbook}
            detail={detailQuery.data?.result}
            formalStatus={overviewMeta}
            currentUser={currentUser}
            decisionRows={decisionRows}
            riskAlerts={riskAlertRows}
            calendarEvents={eventCalendarRows}
            tableRows={summaryTable?.rows ?? []}
            metrics={pageModel.balanceWorkbenchMetrics}
            kpiBars={[]}
            endpointGroups={endpointGroups}
            deferredSurfaces={deferredSurfaces}
            stateSentinels={stateSentinels}
            compactFilters={
              <p className="balance-analysis-compact-filter-note">
                报告日、头寸范围与币种口径请使用页眉筛选。
              </p>
            }
          />

          <details
            className="balance-analysis-evidence-details"
            data-testid="balance-analysis-evidence-details"
            open={evidenceLedgerNeedsAttention}
          >
        <summary className="balance-analysis-evidence-details__summary">
          <span className="balance-analysis-evidence-details__eyebrow">证据链路</span>
          <strong>{evidenceLedgerSummary}</strong>
          <span>常规校验默认收起，需处理事项、降级或日期不一致时自动展开。</span>
        </summary>
        <AnalysisGrid columns={2} className="balance-analysis-ledger-grid">
          <EvidencePanel heading="读面证据" className="balance-analysis-ledger-panel">
            <p className="balance-analysis-ledger-copy">{pageReadModel.conclusionDetail}</p>
            <div className="balance-analysis-state-stack">
              {pageReadModel.stateSurfaces.map((state) => (
                <PageStateSurface
                  key={state.key}
                  variant={state.variant}
                  title={state.title}
                  description={state.description}
                />
              ))}
            </div>
          </EvidencePanel>
          <EvidencePanel heading="证据账本" className="balance-analysis-ledger-panel">
            <div className="balance-analysis-evidence-ledger">
              {pageReadModel.evidenceCards.length > 0 ? (
                pageReadModel.evidenceCards.map((card) => (
                  <article key={card.key} className="balance-analysis-evidence-card">
                    <div className="balance-analysis-evidence-card__top">
                      <strong>{card.title}</strong>
                      <span>{card.basisLabel}</span>
                    </div>
                    <dl>
                      <div>
                        <dt>读面类型</dt>
                        <dd>{card.resultKind}</dd>
                      </div>
                      <div>
                        <dt>质量</dt>
                        <dd>{card.qualityLabel}</dd>
                      </div>
                      <div>
                        <dt>降级</dt>
                        <dd>{card.fallbackLabel}</dd>
                      </div>
                      <div>
                        <dt>数据日</dt>
                        <dd>{card.asOfDate}</dd>
                      </div>
                      <div>
                        <dt>追踪记录</dt>
                        <dd title={card.traceId}>{formatEvidenceTraceDisplay(card.traceId)}</dd>
                      </div>
                    </dl>
                  </article>
                ))
              ) : (
                <PageStateSurface
                  variant="loading"
                  title="证据账本等待数据"
                  description="正式读面元数据返回后，会在这里展示来源、质量、降级和追踪记录。"
                />
              )}
            </div>
          </EvidencePanel>
        </AnalysisGrid>
      </details>

      <div data-testid="balance-analysis-summary" className="balance-analysis-hidden-summary">
        {String(overview?.detail_row_count ?? 0)} {String(overview?.summary_row_count ?? 0)}{" "}
        {pageModel.headlineAmountCards.map((card) => card.value).join(" ")}
      </div>

      <details
        data-testid="balance-analysis-formal-summary-details"
        className="balance-analysis-stage-details balance-analysis-stage-details--summary"
      >
        <summary className="balance-analysis-stage-details__summary">
          <span className="balance-analysis-stage-details__eyebrow">汇总</span>
          <h2 className="balance-analysis-stage-details__heading">正式汇总驾驶舱</h2>
          <span>
            分页汇总、明细汇总和明细下钻默认收起；首屏先保留缺口判断、规模证据和治理行动。
          </span>
        </summary>
        <div className="balance-analysis-stage-details__content">
        <AsyncSection
          title="资产负债汇总"
          isLoading={
            datesQuery.isLoading ||
            overviewQuery.isLoading ||
            summaryQuery.isLoading
          }
          isError={
            datesQuery.isError ||
            overviewQuery.isError ||
            summaryQuery.isError
          }
          isEmpty={!summaryQuery.isLoading && (summaryTable?.rows.length ?? 0) === 0}
          onRetry={() => {
            void Promise.all([
              datesQuery.refetch(),
              overviewQuery.refetch(),
              workbookQuery.refetch(),
              detailQuery.refetch(),
              summaryQuery.refetch(),
            ]);
          }}
        >
          <div
            className="ag-theme-alpine"
            data-testid="balance-analysis-summary-table"
            style={{ ...tableShellStyle, height: 360, width: "100%", padding: 0 }}
          >
            <AgGridReact<BalanceAnalysisTableRow>
              theme="legacy"
              rowData={summaryTable?.rows ?? []}
              columnDefs={balanceSummaryColDefs}
              defaultColDef={balanceAnalysisGridDefaultColDef}
              localeText={balanceAnalysisGridLocaleText}
              getRowId={(p) => getBalanceSummaryGridRowId(p.data)}
            />
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              gap: 10,
              marginTop: 12,
            }}
          >
            <button
              type="button"
              onClick={() => setSummaryOffset((current) => Math.max(0, current - pageSize))}
              disabled={summaryOffset === 0}
              style={actionButtonStyle}
            >
              上一页
            </button>
            <span>{`第 ${currentPage} / ${totalPages} 页`}</span>
            <button
              type="button"
              onClick={() => setSummaryOffset((current) => current + pageSize)}
              disabled={summaryOffset + pageSize >= (summaryTable?.total_rows ?? 0)}
              style={actionButtonStyle}
            >
              下一页
            </button>
          </div>
          <div style={{ marginTop: 18 }}>
            <div style={{ color: designTokens.color.neutral[600], fontSize: 12, marginBottom: 8 }}>明细下钻预留</div>
            {deferredAnalysisQueriesPending ? (
              <div>明细下钻等待首屏数据完成…</div>
            ) : !detailQuery.isLoading &&
            !detailQuery.isError &&
            (detailQuery.data?.result.summary?.length ?? 0) > 0 ? (
              <div style={{ marginBottom: 14 }}>
                <div style={{ color: designTokens.color.neutral[600], fontSize: 12, marginBottom: 8 }}>
                  明细底稿返回的汇总切片
                </div>
                <div
                  className="ag-theme-alpine"
                  data-testid="balance-analysis-detail-summary-grid"
                  style={{ ...tableShellStyle, height: 200, width: "100%" }}
                >
                  <AgGridReact<BalanceAnalysisSummaryGridRow>
                    theme="legacy"
                    rowData={detailSummaryGridRows}
                    columnDefs={balanceDetailSummaryColDefs}
                    defaultColDef={balanceAnalysisGridDefaultColDef}
                    localeText={balanceAnalysisGridLocaleText}
                    getRowId={(p) => p.data.__gridId}
                  />
                </div>
              </div>
            ) : null}
            {deferredAnalysisQueriesPending ? null : detailQuery.isError ? (
              <div
                style={{
                  borderRadius: 14,
                  border: `1px solid ${designTokens.color.warning[200]}`,
                  background: designTokens.color.warning[50],
                  color: designTokens.color.warning[700],
                  padding: 14,
                  fontSize: 13,
                }}
              >
                明细下钻暂时不可用，汇总驾驶舱仍可继续使用。
              </div>
            ) : detailQuery.isLoading ? (
              <div style={{ color: designTokens.color.neutral[600], fontSize: 13 }}>明细下钻加载中…</div>
            ) : (
              <div
                className="ag-theme-alpine"
                data-testid="balance-analysis-table"
                style={{ ...tableShellStyle, height: 320, width: "100%", padding: 0, marginTop: 8 }}
              >
                <AgGridReact<BalanceAnalysisDetailGridRow>
                  theme="legacy"
                  rowData={detailGridRows}
                  columnDefs={balanceDetailColDefs}
                  defaultColDef={balanceAnalysisGridDefaultColDef}
                  localeText={balanceAnalysisGridLocaleText}
                  getRowId={(p) => p.data.__gridId}
                />
              </div>
            )}
          </div>
        </AsyncSection>
        </div>
      </details>

      <details
        data-testid="balance-analysis-supplemental-panels"
        className="balance-analysis-supplemental"
      >
        <summary className="balance-analysis-supplemental__summary">
          <span className="balance-analysis-supplemental__eyebrow">分析口径</span>
          <strong className="balance-analysis-supplemental__title">辅助分析口径</strong>
          <span className="balance-analysis-supplemental__description">
            日均预览、会计口径拆解和高阶归因默认收起，作为解释正式结果的辅助材料，不替代正式结论。
          </span>
        </summary>
        <div className="balance-analysis-supplemental__grid">
          <SectionCard
            title="日均分析预览"
            loading={deferredAnalysisQueriesPending || adbComparisonQuery.isLoading}
            error={adbComparisonQuery.isError}
            onRetry={() => void adbComparisonQuery.refetch()}
          >
            {adbComparisonQuery.data ? <AdbAnalyticalPreview comparison={adbComparisonQuery.data} href={adbHref} /> : null}
          </SectionCard>
          <SectionCard
            title="按会计口径分解"
            loading={deferredAnalysisQueriesPending || basisBreakdownQuery.isLoading}
            error={basisBreakdownQuery.isError}
            onRetry={() => void basisBreakdownQuery.refetch()}
            noPadding
          >
            <div
              className="ag-theme-alpine"
              data-testid="balance-analysis-basis-breakdown-grid"
              style={{ ...tableShellStyle, height: 240, width: "100%" }}
            >
              <AgGridReact<BalanceAnalysisBasisBreakdownRow>
                theme="legacy"
                rowData={basisBreakdownQuery.data?.result.rows ?? []}
                columnDefs={balanceBasisBreakdownColDefs}
                defaultColDef={balanceAnalysisGridDefaultColDef}
                localeText={balanceAnalysisGridLocaleText}
                getRowId={(p) =>
                  `${p.data.source_family}-${p.data.invest_type_std}-${p.data.accounting_basis}-${p.data.position_scope}-${p.data.currency_basis}`
                }
              />
            </div>
          </SectionCard>
          <SectionCard
            title="高阶归因"
            loading={deferredAnalysisQueriesPending || advancedAttributionQuery.isLoading}
            error={advancedAttributionQuery.isError}
            onRetry={() => void advancedAttributionQuery.refetch()}
          >
            {advancedAttributionQuery.data?.result ? (
              (() => {
                const attribution = advancedAttributionQuery.data.result;
                const inputLabels = Array.from(
                  new Set(attribution.missing_inputs.map(formatAdvancedAttributionInputDisplay)),
                );
                const warningLabels = Array.from(
                  new Set(attribution.warnings.map(formatAdvancedAttributionWarningDisplay)),
                );

                return (
                  <div style={{ display: "grid", gap: 10, fontSize: 13, color: designTokens.color.neutral[800] }}>
                    <div>
                      <strong>归因可用性</strong>：
                      {formatAdvancedAttributionStatusDisplay(attribution.status)} ·{" "}
                      {formatAdvancedAttributionModeDisplay(attribution.mode)}
                    </div>
                    <div>
                      <strong>缺口材料</strong>：缺 {attribution.missing_inputs.length} 项输入
                      {inputLabels.length > 0 ? (
                        <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                          {inputLabels.slice(0, 4).map((label) => (
                            <li key={label}>{label}</li>
                          ))}
                        </ul>
                      ) : (
                        <span>，关键输入已齐备。</span>
                      )}
                    </div>
                    <div>
                      <strong>提示</strong>：{attribution.warnings.length} 条
                      {warningLabels.length > 0 ? (
                        <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                          {warningLabels.slice(0, 4).map((label) => (
                            <li key={label}>{label}</li>
                          ))}
                        </ul>
                      ) : (
                        <span>，暂无补充提示。</span>
                      )}
                    </div>
                  </div>
                );
              })()
            ) : null}
          </SectionCard>
        </div>
      </details>

      <div style={{ marginTop: 24 }}>
        <PageSectionLead
          eyebrow="工作台"
          title="治理闭环与工作簿底稿"
          description="先处理决策事项、事件日历和风险预警；工作簿结构默认收起，作为下方可展开底稿。"
        />
        <AsyncSection
          title="治理闭环"
          isLoading={
            datesQuery.isLoading ||
            workbookQuery.isLoading ||
            decisionItemsQuery.isLoading
          }
          isError={
            datesQuery.isError ||
            workbookQuery.isError ||
            decisionItemsQuery.isError
          }
          isEmpty={!workbookQuery.isLoading && (workbook?.tables.length ?? 0) === 0}
          onRetry={() => {
            void Promise.all([
              datesQuery.refetch(),
              workbookQuery.refetch(),
              currentUserQuery.refetch(),
              decisionItemsQuery.refetch(),
            ]);
          }}
        >
          <div data-testid="balance-analysis-workbook-cockpit" className="balance-analysis-workbook-cockpit">
            <details className="balance-analysis-workbook-main-details">
              <summary className="balance-analysis-workbook-main-details__summary">
                <span className="balance-analysis-workbook-full-details__eyebrow">工作簿图谱</span>
                <strong>工作簿结构与分布面板</strong>
                <span>默认收起，治理行动保持常驻；展开后查看债券分类、评级、期限缺口和支持面板。</span>
              </summary>
              <div className="balance-analysis-workbook-main">
                {renderBalanceReconciliationLinkPanel(reconciliationLinkModel)}
                <div
                  data-testid="balance-analysis-workbook-primary-grid"
                  className="balance-analysis-workbook-primary-grid"
                >
                  {primaryWorkbookTables.map((table) => (
                    <article
                      key={table.key}
                      data-testid={`balance-analysis-workbook-panel-${table.key}`}
                      style={workbookPanelStyle}
                    >
                      <div style={workbookPanelHeaderStyle}>
                        <div>
                          <div style={{ color: designTokens.color.neutral[900], fontSize: 18, fontWeight: 600 }}>
                            {formatBalanceBusinessTextDisplay(table.title)}
                          </div>
                          <p
                            style={{
                              marginTop: 6,
                              marginBottom: 0,
                              color: designTokens.color.neutral[700],
                              fontSize: 13,
                              lineHeight: 1.6,
                            }}
                          >
                            {workbookPanelNotes[table.key as (typeof primaryWorkbookTableKeys)[number]]}
                          </p>
                        </div>
                        <span style={workbookPanelBadgeStyle}>
                          {table.key === "bond_business_types" && isBondBusinessLinkedToMovement ? "movement" : "workbook"}
                        </span>
                      </div>
                      {renderWorkbookPrimaryPanel(table)}
                    </article>
                  ))}
                </div>

                <div
                  data-testid="balance-analysis-workbook-secondary-panels"
                  className="balance-analysis-workbook-secondary-panels"
                >
                  {secondaryWorkbookPanelTables.map((table) => (
                    <article
                      key={table.key}
                      data-testid={`balance-analysis-workbook-panel-${table.key}`}
                      style={workbookPanelStyle}
                    >
                      <div style={workbookPanelHeaderStyle}>
                        <div>
                          <div style={{ color: designTokens.color.neutral[900], fontSize: 18, fontWeight: 600 }}>
                            {formatBalanceBusinessTextDisplay(table.title)}
                          </div>
                          <p
                            style={{
                              marginTop: 6,
                              marginBottom: 0,
                              color: designTokens.color.neutral[700],
                              fontSize: 13,
                              lineHeight: 1.6,
                            }}
                          >
                            {workbookSecondaryPanelNotes[table.key as (typeof secondaryWorkbookPanelKeys)[number]]}
                          </p>
                        </div>
                        <span style={workbookPanelBadgeStyle}>
                          {table.key === "industry_distribution" && isIndustryLinkedToMovement ? "movement" : "supporting"}
                        </span>
                      </div>
                      {renderWorkbookSecondaryPanel(table)}
                    </article>
                  ))}
                </div>
              </div>
            </details>

            <aside
              data-testid="balance-analysis-right-rail"
              className="balance-analysis-right-rail"
              aria-label="资产负债治理闭环"
            >
              <article
                data-testid="balance-analysis-right-rail-panel-decision_items"
                className="balance-analysis-right-rail__panel balance-analysis-right-rail__panel--decision"
              >
                <div className="balance-analysis-governance-panel__header">
                  <div>
                    <div className="balance-analysis-governance-panel__title">决策事项</div>
                    <p className="balance-analysis-governance-panel__note">
                      {decisionRailNote}
                    </p>
                  </div>
                  <span className="balance-analysis-governance-panel__badge">{decisionRows.length} 项</span>
                </div>
                {decisionActionError ? (
                  <div
                    data-testid="balance-analysis-decision-error"
                    style={{
                      marginBottom: 12,
                      borderRadius: 12,
                      border: `1px solid ${designTokens.color.warning[200]}`,
                      background: designTokens.color.warning[50],
                      color: designTokens.color.warning[700],
                      padding: 12,
                      fontSize: 13,
                    }}
                  >
                    {decisionActionError}
                  </div>
                ) : null}
                <label
                  className="balance-analysis-decision-note"
                >
                  <span>决策备注（可选，随确认/忽略提交）</span>
                  <textarea
                    value={decisionStatusComment}
                    onChange={(event) => setDecisionStatusComment(event.target.value)}
                    rows={2}
                    className="balance-analysis-decision-note__input"
                  />
                </label>
                {currentUser ? (
                  <div
                    data-testid="balance-analysis-current-user"
                    className="balance-analysis-current-user"
                    title={`身份来源：${formatIdentitySourceDisplay(currentUser.identity_source)}`}
                  >
                    <span>提交人</span>
                    <strong>{formatCurrentUserDisplay(currentUser.user_id)}</strong>
                    <span>{formatCurrentUserRoleDisplay(currentUser.role)}</span>
                  </div>
                ) : null}
                {renderDecisionItemsPanel(decisionRows, {
                  selectedKey: selectedDecisionKey,
                  updatingKey: updatingDecisionKey,
                  onSelect: (row) => {
                    setSelectedEventCalendarKey(null);
                    setSelectedRiskAlertKey(null);
                    setSelectedDecisionKey(row.decision_key);
                  },
                  onUpdateStatus: (row, status) => {
                    void handleDecisionStatusUpdate(row, status);
                  },
                })}
              </article>
              {filteredRightRailWorkbookTables.map((table) => (
                <article
                  key={table.key}
                  data-testid={`balance-analysis-right-rail-panel-${table.key}`}
                  className={`balance-analysis-right-rail__panel ${
                    table.section_kind === "event_calendar"
                      ? "balance-analysis-right-rail__panel--event"
                      : table.section_kind === "risk_alerts"
                        ? "balance-analysis-right-rail__panel--risk"
                        : "balance-analysis-right-rail__panel--support"
                  }`}
                >
                  <div className="balance-analysis-governance-panel__header">
                    <div>
                      <div className="balance-analysis-governance-panel__title">
                        {formatBalanceBusinessTextDisplay(table.title)}
                      </div>
                      <p className="balance-analysis-governance-panel__note">
                        {workbookRightRailNotes[table.key as RightRailWorkbookKey]}
                      </p>
                    </div>
                    <span className="balance-analysis-governance-panel__badge">
                      {table.rows.length}
                      {table.section_kind === "event_calendar" ? " 件" : " 条"}
                    </span>
                  </div>
                  {table.section_kind === "event_calendar" ? (
                    <>
                      <div className="balance-analysis-governance-filter-row">
                        <label>
                          <span className="balance-analysis-governance-filter-row__label">
                            事件类型
                          </span>
                          <select
                            aria-label="balance-event-type-filter"
                            value={eventTypeFilter}
                            onChange={(event) => setEventTypeFilter(event.target.value)}
                            className="balance-analysis-governance-select"
                          >
                            <option value="all">全部</option>
                            {eventTypeOptions.map((eventType) => (
                              <option key={eventType} value={eventType}>
                                {formatBalanceBusinessTextDisplay(eventType)}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                      {renderEventCalendarPanel(table, {
                        onSelect: (row) => {
                          setSelectedDecisionKey(null);
                          setSelectedRiskAlertKey(null);
                          setSelectedEventCalendarKey(`${row.event_date}:${row.title}`);
                        },
                        selectedKey: selectedEventCalendarKey,
                      })}
                    </>
                  ) : table.section_kind === "risk_alerts" ? (
                    <>
                      <div className="balance-analysis-governance-filter-row">
                        <label>
                          <span className="balance-analysis-governance-filter-row__label">
                            预警等级
                          </span>
                          <select
                            aria-label="balance-risk-severity-filter"
                            value={riskSeverityFilter}
                            onChange={(event) =>
                              setRiskSeverityFilter(event.target.value as "all" | BalanceAnalysisSeverity)
                            }
                            className="balance-analysis-governance-select"
                          >
                            <option value="all">全部</option>
                            <option value="high">高</option>
                            <option value="medium">中</option>
                            <option value="low">低</option>
                          </select>
                        </label>
                      </div>
                      {renderRiskAlertsPanel(table, {
                        onSelect: (row) => {
                          setSelectedDecisionKey(null);
                          setSelectedEventCalendarKey(null);
                          setSelectedRiskAlertKey(`${row.severity}:${row.title}`);
                        },
                        selectedKey: selectedRiskAlertKey,
                      })}
                    </>
                  ) : (
                    renderWorkbookRightRailPanel(table)
                  )}
                </article>
              ))}
              <article
                data-testid="balance-analysis-right-rail-drilldown"
                className="balance-analysis-right-rail__panel balance-analysis-right-rail__panel--drilldown"
              >
                <div className="balance-analysis-governance-panel__header">
                  <div>
                    <div className="balance-analysis-governance-panel__title">详情下钻</div>
                    <p className="balance-analysis-governance-panel__note">
                      选择决策、事件或预警后，在这里查看完整说明和证据。
                    </p>
                  </div>
                  <span className="balance-analysis-governance-panel__badge">详情</span>
                </div>
                {selectedDecision ? (
                  <div data-testid="balance-analysis-right-rail-drilldown-decision" style={{ display: "grid", gap: 8 }}>
                    <div style={{ color: designTokens.color.neutral[900], fontWeight: 700 }}>
                      {formatBalanceBusinessTextDisplay(selectedDecision.title)}
                    </div>
                    <div style={{ color: designTokens.color.info[600], fontSize: 13 }}>
                      处理进度：{formatBalanceDecisionWorkflowStatusDisplay(selectedDecision.latest_status.status)}
                    </div>
                    <div style={{ color: designTokens.color.neutral[700], fontSize: 13, lineHeight: 1.6 }}>
                      {formatBalanceBusinessTextDisplay(selectedDecision.reason)}
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: designTokens.color.neutral[600] }}>
                      <span>{formatBalanceWorkbookOperationalSectionKeyDisplay(selectedDecision.source_section)}</span>
                      <span>{selectedDecision.rule_id}</span>
                      <span>{selectedDecision.rule_version}</span>
                    </div>
                    <div style={{ display: "grid", gap: 4, fontSize: 12, color: designTokens.color.neutral[700] }}>
                      <span>
                        更新人：{" "}
                        {selectedDecision.latest_status.updated_by
                          ? selectedDecision.latest_status.updated_by
                          : "未更新"}
                      </span>
                      <span>
                        更新时间：{" "}
                        {selectedDecision.latest_status.updated_at
                          ? selectedDecision.latest_status.updated_at
                          : "暂无"}
                      </span>
                      {selectedDecision.latest_status.comment ? (
                        <span>{selectedDecision.latest_status.comment}</span>
                      ) : null}
                    </div>
                  </div>
                ) : selectedEventCalendar ? (
                  <div data-testid="balance-analysis-right-rail-drilldown-event" style={{ display: "grid", gap: 8 }}>
                    <div style={{ color: designTokens.color.neutral[900], fontWeight: 700 }}>
                      {formatBalanceBusinessTextDisplay(selectedEventCalendar.title)}
                    </div>
                    <div style={{ color: designTokens.color.info[600], fontSize: 13 }}>{selectedEventCalendar.event_date}</div>
                    <div style={{ color: designTokens.color.neutral[700], fontSize: 13 }}>
                      {formatBalanceBusinessTextDisplay(selectedEventCalendar.impact_hint)}
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: designTokens.color.neutral[600] }}>
                      <span>{formatBalanceBusinessTextDisplay(selectedEventCalendar.event_type)}</span>
                      <span>{formatBalanceBusinessTextDisplay(selectedEventCalendar.source)}</span>
                      <span>{formatBalanceWorkbookOperationalSectionKeyDisplay(selectedEventCalendar.source_section)}</span>
                    </div>
                  </div>
                ) : selectedRiskAlert ? (
                  <div data-testid="balance-analysis-right-rail-drilldown-risk" style={{ display: "grid", gap: 8 }}>
                    <div style={{ color: designTokens.color.neutral[900], fontWeight: 700 }}>
                      {formatBalanceBusinessTextDisplay(selectedRiskAlert.title)}
                    </div>
                    <div style={{ color: designTokens.color.warning[600], fontSize: 13 }}>{formatBalanceGovernedSeverityDisplay(selectedRiskAlert.severity)}</div>
                    <div style={{ color: designTokens.color.warning[700], fontSize: 13, lineHeight: 1.6 }}>
                      {formatBalanceBusinessTextDisplay(selectedRiskAlert.reason)}
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: designTokens.color.warning[700] }}>
                      <span>{formatBalanceWorkbookOperationalSectionKeyDisplay(selectedRiskAlert.source_section)}</span>
                      <span>{selectedRiskAlert.rule_id}</span>
                      <span>{selectedRiskAlert.rule_version}</span>
                    </div>
                  </div>
                ) : (
                  renderWorkbookEmptyState(
                    "请选择一条决策事项、事件日历或风险预警后查看详情。",
                  )
                )}
              </article>
            </aside>
          </div>

          <details
            data-testid="balance-analysis-workbook-full-details"
            className="balance-analysis-workbook-full-details"
          >
            <summary className="balance-analysis-workbook-full-details__summary">
              <span className="balance-analysis-workbook-full-details__eyebrow">完整明细</span>
              <strong>完整工作簿明细</strong>
              <span>展开查看工作簿宽表，默认收起以保持结论和治理证据优先。</span>
            </summary>
            <div data-testid="balance-analysis-workbook-secondary-grid" style={workbookSecondaryGridStyle}>
              {secondaryWorkbookTables.map((table) => (
                <div key={table.key} data-testid={`balance-analysis-workbook-table-${table.key}`}>
                  <div style={{ marginBottom: 8, color: designTokens.color.neutral[900], fontWeight: 600 }}>
                    {formatBalanceBusinessTextDisplay(table.title)}
                  </div>
                  <div
                    className="ag-theme-alpine"
                    style={{ ...tableShellStyle, height: 280, width: "100%", padding: 0 }}
                  >
                    <AgGridReact
                      theme="legacy"
                      rowData={table.rows.map((row, index) =>
                        Object.assign({}, row as object, { __gridId: `${table.key}-${index}` }),
                      )}
                      columnDefs={buildWorkbookGridColumnDefs(table.columns)}
                      defaultColDef={balanceAnalysisGridDefaultColDef}
                      localeText={balanceAnalysisGridLocaleText}
                      getRowId={(p) => String((p.data as { __gridId: string }).__gridId)}
                    />
                  </div>
                </div>
              ))}
            </div>
          </details>
        </AsyncSection>
      </div>

      <details data-testid="balance-analysis-stage-details" className="balance-analysis-stage-details">
        <summary className="balance-analysis-stage-details__summary">
          <span className="balance-analysis-stage-details__eyebrow">真实数据</span>
          <strong>真实数据场景阅读</strong>
          <span>
            保留当前报告日派生视图，默认收起，正式总览、汇总、明细和治理信号仍是主判断来源。
          </span>
        </summary>
        <div className="balance-analysis-stage-details__content">
          <div className="balance-analysis-stage-warning">
            当前区块已切换为真实数据派生视图，报告日为 {pageModel.stageModel.summary.tags[0]?.label ?? "—"}；
            仍以页面上方正式总览、汇总、明细和受治理信号作为正式判断来源。
            {pageModel.stageModel.hasRealData ? "" : " 当前筛选条件下未返回可展示的真实阶段切片。"}
          </div>
          <BalanceSummaryRow model={pageModel.stageModel.summary} />
          <BalanceContributionRow model={pageModel.stageModel.contribution} />
          <BalanceBottomRow model={pageModel.stageModel.bottom} />
        </div>
      </details>

          {resultMetaSections.length > 0 && (
            <Collapse
              data-testid="balance-analysis-result-meta-collapse"
              defaultActiveKey={[]}
              items={[
                {
                  key: "result-meta",
                  label: "开发调试：结果元信息",
                  forceRender: true,
                  children: (
                    <FormalResultMetaPanel
                      testId="balance-analysis-result-meta"
                      sections={resultMetaSections}
                    />
                  ),
                },
              ]}
              style={{ marginTop: 20 }}
            />
          )}
        </>
      )}
    </section>
  );
}
