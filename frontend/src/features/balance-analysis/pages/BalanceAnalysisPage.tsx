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
  KpiBand,
  KpiBandMetric,
  PageDecisionHero,
  PageFilterTray,
  PageSectionLead,
  PageStateSurface,
} from "../../../components/page/PagePrimitives";
import { SectionCard } from "../../../components/SectionCard";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import AdbAnalyticalPreview from "../components/AdbAnalyticalPreview";
import BalanceAnalysisWorkbenchLayout from "../components/BalanceAnalysisWorkbenchLayout";
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
  rightRailFilterRowStyle,
  rightRailFilterStyle,
  currentUserCardStyle,
} from "./BalanceAnalysisPage.styles";
import {
  buildBalanceAnalysisPageModel,
  distributionChartBarWidthPercent,
  formatBalanceAmountToYiFromWan,
  formatBalanceAmountToYiFromYuan,
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

const decisionRailNote = "规则驱动的运营建议项通过治理状态流确认、忽略和跟踪，不把状态写回正式事实表。";

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
  return formatBalanceGridThousandsValue(params.value);
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

const balanceSummaryColDefs: ColDef<BalanceAnalysisTableRow>[] = [
  {
    field: "source_family",
    headerName: "来源",
    valueFormatter: (p) => (p.value == null ? "—" : String(p.value).toUpperCase()),
  },
  { field: "row_key", headerName: "行键", minWidth: 160 },
  { field: "display_name", headerName: "展示名" },
  { field: "owner_name", headerName: "组合名称" },
  { field: "category_name", headerName: "分类" },
  { field: "position_scope", headerName: "头寸范围" },
  { field: "currency_basis", headerName: "币种口径" },
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
    valueGetter: (p) =>
      p.data ? `${p.data.invest_type_std} / ${p.data.accounting_basis}` : "",
  },
];

const balanceDetailColDefs: ColDef<BalanceAnalysisDetailGridRow>[] = [
  {
    field: "source_family",
    headerName: "来源",
    valueFormatter: (p) => (p.value == null ? "—" : String(p.value).toUpperCase()),
  },
  { field: "display_name", headerName: "标识" },
  { field: "report_date", headerName: "报告日" },
  { field: "position_scope", headerName: "范围" },
  {
    colId: "invest_accounting",
    headerName: "会计口径",
    valueGetter: (p) =>
      p.data ? `${p.data.invest_type_std} / ${p.data.accounting_basis}` : "",
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
    valueFormatter: (p) => (p.value == null ? "—" : String(p.value).toUpperCase()),
  },
  { field: "position_scope", headerName: "头寸范围" },
  { field: "currency_basis", headerName: "币种口径" },
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
    valueFormatter: (p) => (p.value == null ? "—" : String(p.value).toUpperCase()),
  },
  { field: "invest_type_std", headerName: "投资类型" },
  { field: "accounting_basis", headerName: "会计口径" },
  { field: "position_scope", headerName: "头寸范围" },
  { field: "currency_basis", headerName: "币种口径" },
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

function buildWorkbookGridColumnDefs(columns: BalanceAnalysisWorkbookColumn[]): ColDef[] {
  return columns.map((col) => ({
    field: col.key,
    headerName: col.label,
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
          detail: bridgeDetail || "等待 summary-by-basis 返回 AC/OCI/TPL 分桶。",
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
            <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">{formatBalanceWorkbookCellDisplay(row.title)}</div>
            <span className="balance-analysis-panel-badge">{formatBalanceGovernedSeverityDisplay(row.severity)}</span>
          </div>
          <div className="balance-analysis-ledger-copy-text">
            {formatBalanceWorkbookWanTextDisplay(row.reason)}
          </div>
          <div className="balance-analysis-ledger-meta-row">
            <span>{formatBalanceWorkbookCellDisplay(row.action_label)}</span>
            <span>{formatBalanceWorkbookOperationalSectionKeyDisplay(row.source_section)}</span>
            <span>{formatBalanceWorkbookCellDisplay(row.rule_id)}</span>
            <span>{formatBalanceWorkbookCellDisplay(row.rule_version)}</span>
          </div>
          <div className="balance-analysis-ledger-meta-row balance-analysis-ledger-meta-row--strong">
            <span>状态：{formatBalanceDecisionWorkflowStatusDisplay(row.latest_status.status)}</span>
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
              查看状态
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
              <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">{formatBalanceWorkbookCellDisplay(row.title)}</div>
              <div className="balance-analysis-mini-value--info">{formatBalanceWorkbookCellDisplay(row.event_date)}</div>
            </div>
            <div className="balance-analysis-ledger-copy-text">{formatBalanceWorkbookCellDisplay(row.impact_hint)}</div>
            <div className="balance-analysis-ledger-meta-row">
              <span>{formatBalanceWorkbookCellDisplay(row.event_type)}</span>
              <span>{formatBalanceWorkbookCellDisplay(row.source)}</span>
              <span>{formatBalanceWorkbookCellDisplay(row.source_section)}</span>
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
              <div className="balance-analysis-mini-label balance-analysis-mini-label--strong">{formatBalanceWorkbookCellDisplay(row.title)}</div>
              <span className="balance-analysis-panel-badge balance-analysis-panel-badge--warning">
                {formatBalanceWorkbookCellDisplay(row.severity)}
              </span>
            </div>
            <div className="balance-analysis-ledger-copy-text balance-analysis-ledger-copy-text--warning">
              {formatBalanceWorkbookWanTextDisplay(row.reason)}
            </div>
            <div className="balance-analysis-ledger-meta-row balance-analysis-ledger-meta-row--warning">
              <span>{formatBalanceWorkbookCellDisplay(row.source_section)}</span>
              <span>{formatBalanceWorkbookCellDisplay(row.rule_id)}</span>
              <span>{formatBalanceWorkbookCellDisplay(row.rule_version)}</span>
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
          setRefreshStatus(
            [nextPayload.status, nextPayload.run_id, nextPayload.source_version]
              .filter(Boolean)
              .join(" · "),
          );
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
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "刷新资产负债分析失败");
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
    } catch (error) {
      setDecisionActionError(error instanceof Error ? error.message : "决策状态更新失败。");
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
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "导出资产负债分析失败");
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
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "资产负债分析工作簿导出失败。");
    } finally {
      setIsExportingWorkbook(false);
    }
  }

  return (
    <section data-testid="balance-analysis-page" className="balance-analysis-page">
      <PageDecisionHero
        testId="balance-analysis-contract-hero"
        className="balance-analysis-hero"
        title="资产负债分析"
        titleTestId="balance-analysis-page-title"
        questionTestId="balance-analysis-page-subtitle"
        businessQuestion="正式链路下先判断资产负债状态，再进入证据、汇总与治理行动。"
        eyebrow="正式余额"
        reportDateSlot={
          <span data-testid="balance-analysis-report-date-slot">
            报告日 {pageReadModel.resolvedReportDate}
          </span>
        }
        conclusion={
          <span className="balance-analysis-hero-conclusion">
            <strong>{pageReadModel.conclusionTitle}</strong>
            <span>{pageReadModel.filterLine}</span>
          </span>
        }
        actions={
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
        }
      >
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
      </PageDecisionHero>

      <DataStatusStrip
        testId="balance-analysis-data-status"
        className="balance-analysis-data-status"
      >
        {pageReadModel.statusBadges.map((badge) => (
          <span key={badge.key} className="balance-analysis-status-badge" data-tone={badge.tone}>
            {badge.label}
          </span>
        ))}
      </DataStatusStrip>

      <KpiBand testId="balance-analysis-contract-kpis" className="balance-analysis-contract-kpis">
        {pageReadModel.kpis.map((kpi) => (
          <KpiBandMetric
            key={kpi.key}
            testId={`balance-analysis-contract-kpi-${kpi.key}`}
            label={kpi.label}
            value={
              <>
                {kpi.value}
                {kpi.unit ? <span className="balance-analysis-kpi-unit">{kpi.unit}</span> : null}
              </>
            }
            footer={kpi.detail}
          />
        ))}
      </KpiBand>

      {(refreshStatus || refreshError) && (
        <PageStateSurface
          variant={refreshError ? "error" : "loading"}
          title={refreshError ? "刷新失败" : "刷新进行中"}
          description={refreshError ?? refreshStatus}
          className="balance-analysis-refresh-state"
        />
      )}

      <BalanceAnalysisWorkbenchLayout
        overview={overview}
        summary={summaryTable}
        workbook={workbook}
        detail={detailQuery.data?.result}
        formalStatus={overviewMeta}
        decisionRows={decisionRows}
        riskAlerts={riskAlertRows}
        calendarEvents={eventCalendarRows}
        tableRows={summaryTable?.rows ?? []}
        metrics={pageModel.balanceWorkbenchMetrics}
        kpiBars={[]}
        compactFilters={
          <p className="balance-analysis-compact-filter-note">
            报告日、头寸范围与币种口径请使用页眉筛选。
          </p>
        }
      />

      <AnalysisGrid columns={2} className="balance-analysis-ledger-grid">
        <EvidencePanel heading="正式状态证据" className="balance-analysis-ledger-panel">
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
                      <dt>kind</dt>
                      <dd>{card.resultKind}</dd>
                    </div>
                    <div>
                      <dt>quality</dt>
                      <dd>{card.qualityLabel}</dd>
                    </div>
                    <div>
                      <dt>fallback</dt>
                      <dd>{card.fallbackLabel}</dd>
                    </div>
                    <div>
                      <dt>as-of</dt>
                      <dd>{card.asOfDate}</dd>
                    </div>
                    <div>
                      <dt>trace</dt>
                      <dd>{card.traceId}</dd>
                    </div>
                  </dl>
                </article>
              ))
            ) : (
              <PageStateSurface
                variant="loading"
                title="证据账本等待数据"
                description="正式读面 result_meta 返回后，会在这里展示来源、质量、降级和 trace。"
              />
            )}
          </div>
        </EvidencePanel>
      </AnalysisGrid>

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
            分页汇总、明细汇总和明细下钻默认收起；首屏先保留状态判断、规模证据和治理行动。
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
                  明细接口返回的汇总切片（summary[]）
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
              <div style={{ display: "grid", gap: 10, fontSize: 13, color: designTokens.color.neutral[800] }}>
                <div>
                  <strong>状态</strong>：
                  {advancedAttributionQuery.data.result.status === "not_ready"
                    ? "未就绪"
                    : advancedAttributionQuery.data.result.status} ·{" "}
                  {advancedAttributionQuery.data.result.mode === "analytical"
                    ? "分析口径"
                    : advancedAttributionQuery.data.result.mode}
                </div>
                <div>
                  <strong>缺失输入</strong>（节选）：
                  <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                    {advancedAttributionQuery.data.result.missing_inputs.slice(0, 5).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <strong>提示</strong>：
                  <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                    {advancedAttributionQuery.data.result.warnings.slice(0, 4).map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : null}
          </SectionCard>
        </div>
      </details>

      <div style={{ marginTop: 24 }}>
        <PageSectionLead
          eyebrow="工作台"
          title="工作簿与治理侧栏"
          description="工作簿主栏承载正式工作簿面板，右侧栏承载治理事项、事件日历、风险预警和详情下钻，保持现有契约和阅读顺序。"
        />
        <AsyncSection
          title="工作簿与分析面板"
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
                          <div style={{ color: designTokens.color.neutral[900], fontSize: 18, fontWeight: 600 }}>{table.title}</div>
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
                          <div style={{ color: designTokens.color.neutral[900], fontSize: 18, fontWeight: 600 }}>{table.title}</div>
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

            <aside data-testid="balance-analysis-right-rail" className="balance-analysis-right-rail">
              <article
                data-testid="balance-analysis-right-rail-panel-decision_items"
                style={workbookPanelStyle}
              >
                <div style={workbookPanelHeaderStyle}>
                  <div>
                    <div style={{ color: designTokens.color.neutral[900], fontSize: 18, fontWeight: 600 }}>决策事项</div>
                    <p
                      style={{
                        marginTop: 6,
                        marginBottom: 0,
                        color: designTokens.color.neutral[700],
                        fontSize: 13,
                        lineHeight: 1.6,
                      }}
                    >
                      {decisionRailNote}
                    </p>
                  </div>
                  <span style={workbookPanelBadgeStyle}>已治理</span>
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
                  style={{
                    display: "grid",
                    gap: 6,
                    marginBottom: 12,
                    fontSize: 12,
                    color: designTokens.color.neutral[700],
                  }}
                >
                  <span>决策备注（可选，随确认/忽略提交）</span>
                  <textarea
                    value={decisionStatusComment}
                    onChange={(event) => setDecisionStatusComment(event.target.value)}
                    rows={2}
                    style={{
                      width: "100%",
                      borderRadius: 10,
                      border: `1px solid ${designTokens.color.neutral[300]}`,
                      padding: "8px 10px",
                      fontSize: 13,
                      resize: "vertical",
                    }}
                  />
                </label>
                {currentUser ? (
                  <div data-testid="balance-analysis-current-user" style={currentUserCardStyle}>
                    <div>当前操作人: {currentUser.user_id}</div>
                    <div>角色: {currentUser.role}</div>
                    <div>身份来源: {currentUser.identity_source}</div>
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
                  style={workbookPanelStyle}
                >
                  <div style={workbookPanelHeaderStyle}>
                    <div>
                      <div style={{ color: designTokens.color.neutral[900], fontSize: 18, fontWeight: 600 }}>{table.title}</div>
                      <p
                        style={{
                          marginTop: 6,
                          marginBottom: 0,
                          color: designTokens.color.neutral[700],
                          fontSize: 13,
                          lineHeight: 1.6,
                        }}
                      >
                        {workbookRightRailNotes[table.key as RightRailWorkbookKey]}
                      </p>
                    </div>
                    <span style={workbookPanelBadgeStyle}>已治理</span>
                  </div>
                  {table.section_kind === "event_calendar" ? (
                    <>
                      <div style={rightRailFilterRowStyle}>
                        <label>
                          <span style={{ display: "block", marginBottom: 6, color: designTokens.color.neutral[700], fontSize: 12 }}>
                            事件类型
                          </span>
                          <select
                            aria-label="balance-event-type-filter"
                            value={eventTypeFilter}
                            onChange={(event) => setEventTypeFilter(event.target.value)}
                            style={rightRailFilterStyle}
                          >
                            <option value="all">全部</option>
                            {eventTypeOptions.map((eventType) => (
                              <option key={eventType} value={eventType}>
                                {eventType}
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
                      <div style={rightRailFilterRowStyle}>
                        <label>
                          <span style={{ display: "block", marginBottom: 6, color: designTokens.color.neutral[700], fontSize: 12 }}>
                            预警等级
                          </span>
                          <select
                            aria-label="balance-risk-severity-filter"
                            value={riskSeverityFilter}
                            onChange={(event) =>
                              setRiskSeverityFilter(event.target.value as "all" | BalanceAnalysisSeverity)
                            }
                            style={rightRailFilterStyle}
                          >
                            <option value="all">全部</option>
                            <option value="high">high</option>
                            <option value="medium">medium</option>
                            <option value="low">low</option>
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
              <article data-testid="balance-analysis-right-rail-drilldown" style={workbookPanelStyle}>
                <div style={workbookPanelHeaderStyle}>
                  <div>
                    <div style={{ color: designTokens.color.neutral[900], fontSize: 18, fontWeight: 600 }}>详情下钻</div>
                    <p
                      style={{
                        marginTop: 6,
                        marginBottom: 0,
                        color: designTokens.color.neutral[700],
                        fontSize: 13,
                        lineHeight: 1.6,
                      }}
                    >
                      选择一条事件日历或风险预警后，在这里查看完整说明。
                    </p>
                  </div>
                  <span style={workbookPanelBadgeStyle}>下钻</span>
                </div>
                {selectedDecision ? (
                  <div data-testid="balance-analysis-right-rail-drilldown-decision" style={{ display: "grid", gap: 8 }}>
                    <div style={{ color: designTokens.color.neutral[900], fontWeight: 700 }}>{selectedDecision.title}</div>
                    <div style={{ color: designTokens.color.info[600], fontSize: 13 }}>
                      最新状态：{formatBalanceDecisionWorkflowStatusDisplay(selectedDecision.latest_status.status)}
                    </div>
                    <div style={{ color: designTokens.color.neutral[700], fontSize: 13, lineHeight: 1.6 }}>
                      {formatBalanceWorkbookWanTextDisplay(selectedDecision.reason)}
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
                    <div style={{ color: designTokens.color.neutral[900], fontWeight: 700 }}>{selectedEventCalendar.title}</div>
                    <div style={{ color: designTokens.color.info[600], fontSize: 13 }}>{selectedEventCalendar.event_date}</div>
                    <div style={{ color: designTokens.color.neutral[700], fontSize: 13 }}>{selectedEventCalendar.impact_hint}</div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: designTokens.color.neutral[600] }}>
                      <span>{selectedEventCalendar.event_type}</span>
                      <span>{selectedEventCalendar.source}</span>
                      <span>{selectedEventCalendar.source_section}</span>
                    </div>
                  </div>
                ) : selectedRiskAlert ? (
                  <div data-testid="balance-analysis-right-rail-drilldown-risk" style={{ display: "grid", gap: 8 }}>
                    <div style={{ color: designTokens.color.neutral[900], fontWeight: 700 }}>{selectedRiskAlert.title}</div>
                    <div style={{ color: designTokens.color.warning[600], fontSize: 13 }}>{formatBalanceGovernedSeverityDisplay(selectedRiskAlert.severity)}</div>
                    <div style={{ color: designTokens.color.warning[700], fontSize: 13, lineHeight: 1.6 }}>
                      {formatBalanceWorkbookWanTextDisplay(selectedRiskAlert.reason)}
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: designTokens.color.warning[700] }}>
                      <span>{selectedRiskAlert.source_section}</span>
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
                  <div style={{ marginBottom: 8, color: designTokens.color.neutral[900], fontWeight: 600 }}>{table.title}</div>
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
    </section>
  );
}
