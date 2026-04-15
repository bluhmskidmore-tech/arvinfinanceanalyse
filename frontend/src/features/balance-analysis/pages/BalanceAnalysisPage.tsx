import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Collapse } from "antd";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, ValueFormatterParams } from "ag-grid-community";
import { useSearchParams } from "react-router-dom";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";

import { useApiClient } from "../../../api/client";
import type {
  BalanceAnalysisBasisBreakdownRow,
  BalanceAnalysisDecisionItemStatusRow,
  BalanceAnalysisDetailRow,
  BalanceAnalysisEventCalendarRow,
  BalanceAnalysisRiskAlertRow,
  BalanceAnalysisSeverity,
  BalanceAnalysisSummaryRow,
  BalanceAnalysisTableRow,
  BalanceAnalysisWorkbookColumn,
  BalanceAnalysisWorkbookOperationalSection,
  BalanceAnalysisWorkbookTable,
  BalanceCurrencyBasis,
  BalancePositionScope,
} from "../../../api/contracts";
import { runPollingTask } from "../../../app/jobs/polling";
import { FilterBar } from "../../../components/FilterBar";
import { SectionCard } from "../../../components/SectionCard";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../../workbench/components/KpiCard";
import { PlaceholderCard } from "../../workbench/components/PlaceholderCard";
import AdbAnalyticalPreview from "../components/AdbAnalyticalPreview";
import { BalanceBottomRow } from "../components/BalanceBottomRow";
import { BalanceContributionRow } from "../components/BalanceContributionRow";
import { BalanceSummaryRow } from "../components/BalanceSummaryRow";

const BALANCE_MOCK_KPI = {
  marketAssetsYi: 3525.0,
  marketLiabilitiesYi: 1817.9,
  assetYieldPct: 2.07,
  liabilityCostPct: 1.77,
  staticSpreadBp: 29.5,
  oneYearGapYi: -373.0,
  bondFloatingGainYi: 68.48,
  alertCount: 4,
};

function formatYiAmount(value: number) {
  return value.toLocaleString("zh-CN", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
  gap: 16,
} as const;

const pageHeaderStyle = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: 16,
  marginBottom: 24,
} as const;

const pageSubtitleStyle = {
  marginTop: 8,
  marginBottom: 0,
  maxWidth: 960,
  color: "#5c6b82",
  fontSize: 14,
  lineHeight: 1.7,
} as const;

const modeBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "8px 12px",
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
} as const;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: 6,
  marginTop: 28,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#8090a8",
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: "#162033",
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 920,
  color: "#5c6b82",
  fontSize: 13,
  lineHeight: 1.7,
} as const;

const controlBarStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: 12,
  alignItems: "center",
  marginBottom: 20,
} as const;

const controlStyle = {
  minWidth: 180,
  padding: "10px 12px",
  borderRadius: 12,
  border: "1px solid #d7dfea",
  background: "#ffffff",
  color: "#162033",
} as const;

const actionButtonStyle = {
  padding: "10px 14px",
  borderRadius: 12,
  border: "1px solid #cddcff",
  background: "#edf3ff",
  color: "#1f5eff",
  fontWeight: 600,
  cursor: "pointer",
} as const;

const PAGE_SIZE = 2;

const tableShellStyle = {
  overflowX: "auto",
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
} as const;

const resultMetaGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
  gap: 16,
  marginTop: 20,
} as const;

const resultMetaCardStyle = {
  padding: 16,
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#f7f9fc",
} as const;

const resultMetaListStyle = {
  margin: 0,
  display: "grid",
  gridTemplateColumns: "minmax(110px, 140px) minmax(0, 1fr)",
  gap: "8px 12px",
  fontSize: 13,
} as const;

const workbookPrimaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  gap: 18,
  marginTop: 18,
} as const;

const workbookPanelStyle = {
  borderRadius: 20,
  border: "1px solid #dfe7f2",
  background: "linear-gradient(180deg, #ffffff 0%, #f6f9fc 100%)",
  padding: 18,
  boxShadow: "0 12px 28px rgba(19, 37, 70, 0.06)",
} as const;

const workbookPanelHeaderStyle = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: 12,
  marginBottom: 14,
} as const;

const workbookPanelBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "4px 8px",
  borderRadius: 999,
  background: "#edf3ff",
  color: "#1f5eff",
  fontSize: 12,
  fontWeight: 600,
} as const;

const workbookSecondaryGridStyle = {
  display: "grid",
  gap: 18,
  marginTop: 18,
} as const;

const workbookSecondaryPanelGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  gap: 18,
  marginTop: 18,
} as const;

const workbookCockpitLayoutStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 2fr) minmax(300px, 1fr)",
  gap: 18,
  marginTop: 18,
  alignItems: "start",
} as const;

const workbookMainRailStyle = {
  display: "grid",
  gap: 18,
} as const;

const workbookRightRailStyle = {
  display: "grid",
  gap: 18,
  alignContent: "start",
} as const;

const rightRailFilterRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: 10,
  marginBottom: 12,
} as const;

const rightRailFilterStyle = {
  minWidth: 120,
  padding: "8px 10px",
  borderRadius: 12,
  border: "1px solid #d7dfea",
  background: "#ffffff",
  color: "#162033",
} as const;

const rightRailItemButtonStyle = {
  width: "100%",
  textAlign: "left",
  border: "none",
  background: "transparent",
  padding: 0,
  cursor: "pointer",
} as const;

const decisionActionRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: 8,
} as const;

const decisionActionButtonStyle = {
  padding: "8px 12px",
  borderRadius: 10,
  border: "1px solid #d7dfea",
  background: "#ffffff",
  color: "#162033",
  fontSize: 12,
  fontWeight: 600,
  cursor: "pointer",
} as const;

const currentUserCardStyle = {
  marginBottom: 12,
  borderRadius: 12,
  border: "1px solid #d7dfea",
  background: "#f7f9fc",
  color: "#334155",
  padding: 12,
  fontSize: 12,
  lineHeight: 1.6,
} as const;

const barTrackStyle = {
  width: "100%",
  height: 8,
  borderRadius: 999,
  background: "#e9eef6",
  overflow: "hidden",
} as const;

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

const rightRailWorkbookKeys = [
  "event_calendar",
  "risk_alerts",
] as const;

const workbookPanelNotes: Record<(typeof primaryWorkbookTableKeys)[number], string> = {
  bond_business_types: "对应 Excel 的债券业务种类页，先看资产端主分布和规模占比。",
  rating_analysis: "按评级拆开当前债券资产的规模，保留驾驶舱式强弱对比。",
  maturity_gap: "用期限桶直接看资产负债缺口，不再只给纯表格。",
  issuance_business_types: "发行类单独成块，避免和资产端视图混在一起。",
};

const workbookSecondaryPanelNotes: Record<(typeof secondaryWorkbookPanelKeys)[number], string> = {
  industry_distribution: "把债券资产按行业集中度展开，先看规模最重的方向。",
  rate_distribution: "同一利率桶里并排看债券、同业资产和同业负债。",
  counterparty_types: "按对手方类型看资产、负债和净头寸。",
};

const workbookRightRailNotes: Record<(typeof rightRailWorkbookKeys)[number], string> = {
  event_calendar: "内部治理事件日历，只展示由现有 formal/workbook 输入派生的事件。",
  risk_alerts: "阈值型风险预警，不在前端补正式金融判断。",
};

const decisionRailNote = "规则驱动的运营建议项通过治理状态流确认、忽略和跟踪，不把状态写回 formal facts。";

const ratingBlockPalette = ["#2fbf93", "#5792ff", "#ff9c43", "#8f7cf7", "#ff6b6b", "#7cc4fa"];

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

function parseWorkbookNumber(value: unknown) {
  const text = String(value ?? "").replace(/,/g, "").trim();
  const parsed = Number.parseFloat(text);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatWorkbookValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

function thousandsValueFormatter(params: ValueFormatterParams) {
  const v = params.value;
  if (v === null || v === undefined || v === "") {
    return "—";
  }
  const raw = String(v).replace(/,/g, "");
  const n = Number(raw);
  if (!Number.isFinite(n)) {
    return String(v);
  }
  return n.toLocaleString("zh-CN");
}

function workbookCellFormatter(params: ValueFormatterParams): string {
  const v = params.value;
  if (v === null || v === undefined || v === "") {
    return "—";
  }
  const raw = String(v).replace(/,/g, "");
  const n = Number(raw);
  if (!Number.isFinite(n)) {
    return String(v);
  }
  return n.toLocaleString("zh-CN");
}

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
  );
}

const balanceAnalysisGridDefaultColDef: ColDef = {
  sortable: true,
  filter: true,
  resizable: true,
  flex: 1,
  minWidth: 100,
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
    headerName: "规模(亿)",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    field: "amortized_cost_amount",
    headerName: "摊余成本",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    field: "accrued_interest_amount",
    headerName: "应计利息",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
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

const balanceDetailColDefs: ColDef<BalanceAnalysisDetailRow>[] = [
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
    headerName: "规模",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    field: "amortized_cost_amount",
    headerName: "摊余成本",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    field: "accrued_interest_amount",
    headerName: "应计利息",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    field: "is_issuance_like",
    headerName: "发行类",
    valueFormatter: (p) =>
      p.value === null || p.value === undefined ? "—" : p.value ? "是" : "否",
  },
];

const balanceDetailSummaryColDefs: ColDef<BalanceAnalysisSummaryRow>[] = [
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
    headerName: "市值",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    field: "amortized_cost_amount",
    headerName: "摊余成本",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    field: "accrued_interest_amount",
    headerName: "应计利息",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
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
    headerName: "市值",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    field: "amortized_cost_amount",
    headerName: "摊余成本",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
  {
    field: "accrued_interest_amount",
    headerName: "应计利息",
    headerClass: "ag-right-aligned-header",
    cellClass: "ag-right-aligned-cell",
    valueFormatter: thousandsValueFormatter,
  },
];

function buildWorkbookGridColumnDefs(columns: BalanceAnalysisWorkbookColumn[]): ColDef[] {
  return columns.map((col) => ({
    field: col.key,
    headerName: col.label,
    valueFormatter: workbookCellFormatter,
  }));
}

function renderWorkbookContractMismatch(
  table: Pick<BalanceAnalysisWorkbookTable, "key"> | Pick<BalanceAnalysisWorkbookOperationalSection, "key">,
  message: string,
) {
  return (
    <div
      data-testid={`balance-analysis-workbook-table-${table.key}`}
      style={{
        borderRadius: 16,
        border: "1px solid #ffd8bf",
        background: "#fff7f0",
        color: "#a14a14",
        padding: 14,
        fontSize: 13,
        lineHeight: 1.6,
      }}
    >
      {message}
    </div>
  );
}

function renderWorkbookEmptyState(message: string) {
  return (
    <div
      style={{
        borderRadius: 16,
        border: "1px dashed #d7dfea",
        background: "#f7f9fc",
        color: "#8090a8",
        padding: 14,
        fontSize: 13,
      }}
    >
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
  const maxValue = Math.max(...rows.map((row) => parseWorkbookNumber(row[valueKey])), 1);
  return (
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} style={{ display: "grid", gap: 12 }}>
      {rows.map((row, index) => {
        const value = parseWorkbookNumber(row[valueKey]);
        const width = `${Math.max(14, (value / maxValue) * 100)}%`;
        return (
          <div key={`${table.key}-${index}`} style={{ display: "grid", gap: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <span style={{ color: "#162033", fontWeight: 600 }}>
                {formatWorkbookValue(row[labelKey])}
              </span>
              <span style={{ color: "#5c6b82", fontVariantNumeric: "tabular-nums" }}>
                {formatWorkbookValue(row[valueKey])}
              </span>
            </div>
            <div style={barTrackStyle}>
              <div
                style={{
                  width,
                  height: "100%",
                  borderRadius: 999,
                  background: color,
                }}
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
  const maxValue = Math.max(...rows.map((row) => parseWorkbookNumber(row.balance_amount)), 1);
  return (
    <div
      data-testid={`balance-analysis-workbook-table-${table.key}`}
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
        gap: 10,
      }}
    >
      {rows.map((row, index) => {
        const value = parseWorkbookNumber(row.balance_amount);
        const ratio = Math.max(0.35, value / maxValue);
        return (
          <article
            key={`${table.key}-${index}`}
            style={{
              borderRadius: 16,
              padding: 14,
              background: ratingBlockPalette[index % ratingBlockPalette.length],
              color: "#ffffff",
              minHeight: 88,
              opacity: 0.55 + ratio * 0.45,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
            }}
          >
            <div style={{ fontSize: 18, fontWeight: 700 }}>{formatWorkbookValue(row.rating)}</div>
            <div style={{ fontSize: 13, opacity: 0.92 }}>{formatWorkbookValue(row.balance_amount)}</div>
          </article>
        );
      })}
    </div>
  );
}

function renderMaturityGapPanel(table: BalanceAnalysisWorkbookTable) {
  const rows = table.rows.slice(0, 6);
  if (!hasWorkbookFields(rows, ["bucket", "gap_amount"])) {
    return renderWorkbookContractMismatch(table, "Workbook contract mismatch：期限缺口字段不完整。");
  }
  const maxValue = Math.max(...rows.map((row) => Math.abs(parseWorkbookNumber(row.gap_amount))), 1);
  return (
    <div
      data-testid={`balance-analysis-workbook-table-${table.key}`}
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${Math.max(rows.length, 1)}, minmax(0, 1fr))`,
        gap: 12,
        alignItems: "end",
        minHeight: 220,
      }}
    >
      {rows.map((row, index) => {
        const value = parseWorkbookNumber(row.gap_amount);
        const height = Math.max(18, (Math.abs(value) / maxValue) * 148);
        const positive = value >= 0;
        return (
          <div
            key={`${table.key}-${index}`}
            style={{
              display: "flex",
              flexDirection: "column",
              justifyContent: "flex-end",
              gap: 10,
              minHeight: 220,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "flex-end",
                justifyContent: "center",
                minHeight: 160,
              }}
            >
              <div
                style={{
                  width: "100%",
                  maxWidth: 48,
                  height,
                  borderRadius: "14px 14px 6px 6px",
                  background: positive
                    ? "linear-gradient(180deg, #6aa8ff 0%, #1f5eff 100%)"
                    : "linear-gradient(180deg, #ffbe76 0%, #ff7a45 100%)",
                  boxShadow: positive
                    ? "0 12px 24px rgba(31, 94, 255, 0.18)"
                    : "0 12px 24px rgba(255, 122, 69, 0.18)",
                }}
              />
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ color: "#162033", fontWeight: 600, fontSize: 13 }}>
                {formatWorkbookValue(row.bucket)}
              </div>
              <div style={{ color: positive ? "#1f5eff" : "#d9622b", fontSize: 12, marginTop: 4 }}>
                {formatWorkbookValue(row.gap_amount)}
              </div>
            </div>
          </div>
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
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} style={{ display: "grid", gap: 12 }}>
      {rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          style={{
            borderRadius: 16,
            border: "1px solid #e4ebf5",
            background: "#ffffff",
            padding: 14,
            display: "grid",
            gap: 8,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <div style={{ color: "#162033", fontWeight: 700 }}>{formatWorkbookValue(row.bond_type)}</div>
            <div style={{ color: "#1f5eff", fontWeight: 700 }}>{formatWorkbookValue(row.balance_amount)}</div>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, color: "#5c6b82", fontSize: 12 }}>
            <span>笔数 {formatWorkbookValue(row.count)}</span>
            <span>利率 {formatWorkbookValue(row.weighted_rate_pct)}</span>
            <span>期限 {formatWorkbookValue(row.weighted_term_years)}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function renderWorkbookPrimaryPanel(table: BalanceAnalysisWorkbookTable) {
  if (table.key === "bond_business_types") {
    return renderDistributionPanel(table, {
      labelKey: "bond_type",
      valueKey: "balance_amount",
      color: "linear-gradient(90deg, #91c4ff 0%, #1f5eff 100%)",
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
    color: "linear-gradient(90deg, #8ad7b0 0%, #2fbf93 100%)",
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
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} style={{ display: "grid", gap: 12 }}>
      {rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          style={{
            borderRadius: 16,
            border: "1px solid #e4ebf5",
            background: "#ffffff",
            padding: 14,
            display: "grid",
            gap: 8,
          }}
        >
          <div style={{ color: "#162033", fontWeight: 700 }}>{formatWorkbookValue(row.bucket)}</div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
              gap: 10,
              fontSize: 12,
            }}
          >
            <div>
              <div style={{ color: "#8090a8" }}>债券</div>
              <div style={{ color: "#1f5eff", fontWeight: 700 }}>{formatWorkbookValue(row.bond_amount)}</div>
            </div>
            <div>
              <div style={{ color: "#8090a8" }}>同业资产</div>
              <div style={{ color: "#2fbf93", fontWeight: 700 }}>
                {formatWorkbookValue(row.interbank_asset_amount)}
              </div>
            </div>
            <div>
              <div style={{ color: "#8090a8" }}>同业负债</div>
              <div style={{ color: "#ff7a45", fontWeight: 700 }}>
                {formatWorkbookValue(row.interbank_liability_amount)}
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
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} style={{ display: "grid", gap: 12 }}>
      {rows.map((row, index) => (
        <article
          key={`${table.key}-${index}`}
          style={{
            borderRadius: 16,
            border: "1px solid #e4ebf5",
            background: "#ffffff",
            padding: 14,
            display: "grid",
            gap: 8,
          }}
        >
          <div style={{ color: "#162033", fontWeight: 700 }}>{formatWorkbookValue(row.counterparty_type)}</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12 }}>
            <span style={{ color: "#1f5eff" }}>资产 {formatWorkbookValue(row.asset_amount)}</span>
            <span style={{ color: "#ff7a45" }}>负债 {formatWorkbookValue(row.liability_amount)}</span>
            <span style={{ color: "#162033" }}>净头寸 {formatWorkbookValue(row.net_position_amount)}</span>
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
    return renderWorkbookEmptyState("No governed items.");
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
    <div data-testid="balance-analysis-workbook-table-decision_items" style={{ display: "grid", gap: 12 }}>
      {rows.map((row, index) => (
        <article
          key={row.decision_key}
          style={{
            borderRadius: 16,
            border:
              selectedKey === row.decision_key ? "1px solid #1f5eff" : "1px solid #e4ebf5",
            background: selectedKey === row.decision_key ? "#edf3ff" : "#ffffff",
            padding: 14,
            display: "grid",
            gap: 10,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <div style={{ color: "#162033", fontWeight: 700 }}>{formatWorkbookValue(row.title)}</div>
            <span style={workbookPanelBadgeStyle}>{formatWorkbookValue(row.severity)}</span>
          </div>
          <div style={{ color: "#5c6b82", fontSize: 13, lineHeight: 1.6 }}>
            {formatWorkbookValue(row.reason)}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: "#8090a8" }}>
            <span>{formatWorkbookValue(row.action_label)}</span>
            <span>{formatWorkbookValue(row.source_section)}</span>
            <span>{formatWorkbookValue(row.rule_id)}</span>
            <span>{formatWorkbookValue(row.rule_version)}</span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: "#5c6b82" }}>
            <span>Status: {row.latest_status.status}</span>
            <span>
              Updated by: {row.latest_status.updated_by ? row.latest_status.updated_by : "Not updated"}
            </span>
          </div>
          <div style={decisionActionRowStyle}>
            <button
              data-testid={`balance-analysis-decision-confirm-${index}`}
              type="button"
              disabled={updatingKey === row.decision_key}
              style={decisionActionButtonStyle}
              onClick={() => onUpdateStatus(row, "confirmed")}
            >
              确认
            </button>
            <button
              data-testid={`balance-analysis-decision-dismiss-${index}`}
              type="button"
              disabled={updatingKey === row.decision_key}
              style={decisionActionButtonStyle}
              onClick={() => onUpdateStatus(row, "dismissed")}
            >
              忽略
            </button>
            <button
              data-testid={`balance-analysis-decision-view-status-${index}`}
              type="button"
              style={decisionActionButtonStyle}
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
    return renderWorkbookEmptyState("No governed items.");
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
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} style={{ display: "grid", gap: 12 }}>
      {table.rows.map((row, index) => (
        <button
          key={`${table.key}-${index}`}
          type="button"
          onClick={() => onSelect(row)}
          style={rightRailItemButtonStyle}
        >
          <article
            style={{
              borderRadius: 16,
              border:
                selectedKey === `${row.event_date}:${row.title}` ? "1px solid #1f5eff" : "1px solid #e4ebf5",
              background: selectedKey === `${row.event_date}:${row.title}` ? "#edf3ff" : "#ffffff",
              padding: 14,
              display: "grid",
              gap: 8,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <div style={{ color: "#162033", fontWeight: 700 }}>{formatWorkbookValue(row.title)}</div>
              <div style={{ color: "#1f5eff", fontSize: 12 }}>{formatWorkbookValue(row.event_date)}</div>
            </div>
            <div style={{ color: "#5c6b82", fontSize: 13 }}>{formatWorkbookValue(row.impact_hint)}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: "#8090a8" }}>
              <span>{formatWorkbookValue(row.event_type)}</span>
              <span>{formatWorkbookValue(row.source)}</span>
              <span>{formatWorkbookValue(row.source_section)}</span>
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
    return renderWorkbookEmptyState("No governed items.");
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
    <div data-testid={`balance-analysis-workbook-table-${table.key}`} style={{ display: "grid", gap: 12 }}>
      {table.rows.map((row, index) => (
        <button
          key={`${table.key}-${index}`}
          type="button"
          onClick={() => onSelect(row)}
          style={rightRailItemButtonStyle}
        >
          <article
            style={{
              borderRadius: 16,
              border:
                selectedKey === `${row.severity}:${row.title}` ? "1px solid #d9622b" : "1px solid #ffd8bf",
              background: selectedKey === `${row.severity}:${row.title}` ? "#fff0e4" : "#fff7f0",
              padding: 14,
              display: "grid",
              gap: 8,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <div style={{ color: "#162033", fontWeight: 700 }}>{formatWorkbookValue(row.title)}</div>
              <span style={{ ...workbookPanelBadgeStyle, background: "#ffe7d6", color: "#d9622b" }}>
                {formatWorkbookValue(row.severity)}
              </span>
            </div>
            <div style={{ color: "#a14a14", fontSize: 13, lineHeight: 1.6 }}>
              {formatWorkbookValue(row.reason)}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: "#b46a3c" }}>
              <span>{formatWorkbookValue(row.source_section)}</span>
              <span>{formatWorkbookValue(row.rule_id)}</span>
              <span>{formatWorkbookValue(row.rule_version)}</span>
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

function normalizePositionScopeParam(value: string | null): BalancePositionScope {
  return value === "asset" || value === "liability" || value === "all" ? value : "all";
}

function normalizeCurrencyBasisParam(value: string | null): BalanceCurrencyBasis {
  return value === "native" || value === "CNY" ? value : "CNY";
}

export default function BalanceAnalysisPage() {
  const client = useApiClient();
  const [searchParams] = useSearchParams();
  const queryReportDate = searchParams.get("report_date")?.trim() || "";
  const queryPositionScope = searchParams.get("position_scope");
  const queryCurrencyBasis = searchParams.get("currency_basis");
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [positionScope, setPositionScope] = useState<BalancePositionScope>(
    normalizePositionScopeParam(queryPositionScope),
  );
  const [currencyBasis, setCurrencyBasis] = useState<BalanceCurrencyBasis>(
    normalizeCurrencyBasisParam(queryCurrencyBasis),
  );
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
  const adbStartDate = selectedReportDate ? `${selectedReportDate.slice(0, 4)}-01-01` : "";
  const adbHref = selectedReportDate ? `/average-balance?report_date=${selectedReportDate}` : "/average-balance";

  const datesQuery = useQuery({
    queryKey: ["balance-analysis", "dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });

  useEffect(() => {
    const reportDates = datesQuery.data?.result.report_dates ?? [];
    const firstDate = reportDates[0];
    if (!reportDates.length) {
      return;
    }
    if (queryReportDate && reportDates.includes(queryReportDate)) {
      if (selectedReportDate !== queryReportDate) {
        setSelectedReportDate(queryReportDate);
      }
      return;
    }
    if ((!selectedReportDate || !reportDates.includes(selectedReportDate)) && firstDate) {
      setSelectedReportDate(firstDate);
    }
  }, [datesQuery.data?.result.report_dates, queryReportDate, selectedReportDate]);

  useEffect(() => {
    if (queryPositionScope !== null) {
      const nextPositionScope = normalizePositionScopeParam(queryPositionScope);
      if (positionScope !== nextPositionScope) {
        setPositionScope(nextPositionScope);
      }
    }
    if (queryCurrencyBasis !== null) {
      const nextCurrencyBasis = normalizeCurrencyBasisParam(queryCurrencyBasis);
      if (currencyBasis !== nextCurrencyBasis) {
        setCurrencyBasis(nextCurrencyBasis);
      }
    }
  }, [queryPositionScope, queryCurrencyBasis, positionScope, currencyBasis]);

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

  const overviewQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "overview",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisOverview({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      }),
    retry: false,
  });

  const detailQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "detail",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisDetail({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      }),
    retry: false,
  });

  const workbookQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "workbook",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisWorkbook({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      }),
    retry: false,
  });

  const currentUserQuery = useQuery({
    queryKey: ["balance-analysis", "current-user", client.mode],
    queryFn: () => client.getBalanceAnalysisCurrentUser(),
    retry: false,
  });

  const decisionItemsQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "decision-items",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisDecisionItems({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      }),
    retry: false,
  });

  const summaryQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "summary-table",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
      summaryOffset,
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisSummary({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
        limit: PAGE_SIZE,
        offset: summaryOffset,
      }),
    retry: false,
  });

  const basisBreakdownQuery = useQuery({
    queryKey: [
      "balance-analysis",
      "summary-by-basis",
      client.mode,
      selectedReportDate,
      positionScope,
      currencyBasis,
    ],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisSummaryByBasis({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      }),
    retry: false,
  });

  const adbComparisonQuery = useQuery({
    queryKey: ["balance-analysis", "adb-preview", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getAdbComparison(adbStartDate, selectedReportDate),
    retry: false,
  });

  const advancedAttributionQuery = useQuery({
    queryKey: ["balance-analysis", "advanced-attribution", client.mode, selectedReportDate],
    enabled: Boolean(selectedReportDate),
    queryFn: () =>
      client.getBalanceAnalysisAdvancedAttribution({
        reportDate: selectedReportDate,
      }),
    retry: false,
  });

  const overview = overviewQuery.data?.result;
  const overviewMeta = overviewQuery.data?.result_meta;
  const detailMeta = detailQuery.data?.result_meta;
  const decisionItemsMeta = decisionItemsQuery.data?.result_meta;
  const workbookMeta = workbookQuery.data?.result_meta;
  const summaryMeta = summaryQuery.data?.result_meta;
  const currentUser = currentUserQuery.data;
  const decisionItems = decisionItemsQuery.data?.result;
  const workbook = workbookQuery.data?.result;
  const summaryTable = summaryQuery.data?.result;
  const decisionRows = decisionItems?.rows ?? [];
  const workbookTables = workbook?.tables ?? [];
  const workbookOperationalSections = workbook?.operational_sections ?? [];
  const primaryWorkbookTables = primaryWorkbookTableKeys
    .map((tableKey) => workbookTables.find((table) => table.key === tableKey))
    .filter((table): table is BalanceAnalysisWorkbookTable => table !== undefined);
  const secondaryWorkbookPanelTables = secondaryWorkbookPanelKeys
    .map((tableKey) => workbookTables.find((table) => table.key === tableKey))
    .filter((table): table is BalanceAnalysisWorkbookTable => table !== undefined);
  const rightRailWorkbookTables = workbookOperationalSections.filter((table) =>
    rightRailWorkbookKeys.includes(table.section_kind as (typeof rightRailWorkbookKeys)[number]),
  );
  const eventTypeOptions = Array.from(
    new Set(
      rightRailWorkbookTables
        .filter(
          (table): table is Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "event_calendar" }> =>
            table.section_kind === "event_calendar",
        )
        .flatMap((table) => table.rows.map((row) => row.event_type)),
    ),
  );
  const filteredRightRailWorkbookTables = rightRailWorkbookTables.map((table) => {
    if (table.section_kind === "event_calendar") {
      return {
        ...table,
        rows:
          eventTypeFilter === "all"
            ? table.rows
            : table.rows.filter((row) => row.event_type === eventTypeFilter),
      };
    }
    if (table.section_kind === "risk_alerts") {
      return {
        ...table,
        rows:
          riskSeverityFilter === "all"
            ? table.rows
            : table.rows.filter((row) => row.severity === riskSeverityFilter),
      };
    }
    return table;
  });
  const selectedDecision = decisionRows.find((row) => row.decision_key === selectedDecisionKey);
  const selectedEventCalendar = rightRailWorkbookTables
    .filter(
      (table): table is Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "event_calendar" }> =>
        table.section_kind === "event_calendar",
    )
    .flatMap((table) => table.rows)
    .find((row) => `${row.event_date}:${row.title}` === selectedEventCalendarKey);
  const selectedRiskAlert = rightRailWorkbookTables
    .filter(
      (table): table is Extract<BalanceAnalysisWorkbookOperationalSection, { section_kind: "risk_alerts" }> =>
        table.section_kind === "risk_alerts",
    )
    .flatMap((table) => table.rows)
    .find((row) => `${row.severity}:${row.title}` === selectedRiskAlertKey);
  const secondaryWorkbookTables = workbookTables.filter(
    (table) =>
      !primaryWorkbookTableKeys.includes(table.key as (typeof primaryWorkbookTableKeys)[number]) &&
      !secondaryWorkbookPanelKeys.includes(table.key as (typeof secondaryWorkbookPanelKeys)[number]),
  );
  const resultMetaSections = [
    overviewMeta ? { key: "overview", title: "Overview Result Meta", meta: overviewMeta } : null,
    decisionItemsMeta
      ? { key: "decision-items", title: "Decision Result Meta", meta: decisionItemsMeta }
      : null,
    workbookMeta ? { key: "workbook", title: "Workbook Result Meta", meta: workbookMeta } : null,
    summaryMeta ? { key: "summary", title: "Summary Result Meta", meta: summaryMeta } : null,
    detailMeta ? { key: "detail", title: "Detail Result Meta", meta: detailMeta } : null,
  ].filter(
    (
      section,
    ): section is { key: string; title: string; meta: NonNullable<typeof overviewMeta> } =>
      section !== null,
  );

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
      setDecisionActionError(error instanceof Error ? error.message : "Decision status update failed.");
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
      setRefreshError(error instanceof Error ? error.message : "Balance-analysis workbook export failed.");
    } finally {
      setIsExportingWorkbook(false);
    }
  }

  const totalPages = Math.max(
    1,
    Math.ceil((summaryTable?.total_rows ?? 0) / (summaryTable?.limit ?? PAGE_SIZE)),
  );
  const currentPage = Math.floor(summaryOffset / (summaryTable?.limit ?? PAGE_SIZE)) + 1;

   return (
    <section data-testid="balance-analysis-page">
      <div style={pageHeaderStyle}>
        <div>
          <h1
            data-testid="balance-analysis-page-title"
            style={{ margin: 0, fontSize: 24, fontWeight: 600 }}
          >
            资产负债分析
          </h1>
          <p data-testid="balance-analysis-page-subtitle" style={pageSubtitleStyle}>
            以报告日、头寸范围和币种口径为统一页首筛选，先读正式汇总驾驶舱，再进入工作簿主栏与治理右侧栏。
            保留现有 API 合约、result_meta 和 formal / analytical 边界，不在前端补算正式指标。
          </p>
        </div>
        <span
          style={{
            ...modeBadgeStyle,
            background: client.mode === "real" ? "#e8f6ee" : "#edf3ff",
            color: client.mode === "real" ? "#2f8f63" : "#1f5eff",
          }}
        >
          {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
        </span>
      </div>

      <FilterBar style={controlBarStyle}>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: "#5c6b82" }}>报告日</span>
          <select
            aria-label="balance-report-date"
            value={selectedReportDate}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            style={controlStyle}
          >
            {(datesQuery.data?.result.report_dates ?? []).map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {reportDate}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span style={{ display: "block", marginBottom: 6, color: "#5c6b82" }}>头寸范围</span>
          <select
            aria-label="balance-position-scope"
            value={positionScope}
            onChange={(event) => setPositionScope(event.target.value as BalancePositionScope)}
            style={controlStyle}
          >
            <option value="all">all</option>
            <option value="asset">asset</option>
            <option value="liability">liability</option>
          </select>
        </label>

        <label>
          <span style={{ display: "block", marginBottom: 6, color: "#5c6b82" }}>币种口径</span>
          <select
            aria-label="balance-currency-basis"
            value={currencyBasis}
            onChange={(event) => setCurrencyBasis(event.target.value as BalanceCurrencyBasis)}
            style={controlStyle}
          >
            <option value="CNY">CNY</option>
            <option value="native">native</option>
          </select>
        </label>

        <button
          data-testid="balance-analysis-refresh-button"
          type="button"
          onClick={() => void handleRefresh()}
          disabled={!selectedReportDate || isRefreshing}
          style={actionButtonStyle}
        >
          {isRefreshing ? "刷新中..." : "刷新正式结果"}
        </button>
        <button
          data-testid="balance-analysis-export-button"
          type="button"
          onClick={() => void handleExport()}
          disabled={!selectedReportDate || isExportingCsv}
          style={actionButtonStyle}
        >
          {isExportingCsv ? "导出中..." : "导出 CSV"}
        </button>
        <button
          data-testid="balance-analysis-workbook-export-button"
          type="button"
          onClick={() => void handleWorkbookExport()}
          disabled={!selectedReportDate || isExportingWorkbook}
          style={actionButtonStyle}
        >
          {isExportingWorkbook ? "导出中..." : "导出 Excel"}
        </button>
      </FilterBar>

      {(refreshStatus || refreshError) && (
        <div
          style={{
            marginTop: 16,
            padding: 14,
            borderRadius: 14,
            border: "1px solid #e4ebf5",
            background: refreshError ? "#fff2f0" : "#f7f9fc",
            color: refreshError ? "#c83b3b" : "#5c6b82",
          }}
        >
          {refreshError ?? refreshStatus}
        </div>
      )}

      <SectionLead
        eyebrow="Overview"
        title="页首概览"
        description="顶部卡片只重排现有正式读模型和既有业务摘要，用于先判断资产负债规模、静态利差、缺口和预警，再决定是否下钻。"
      />
      <div data-testid="balance-analysis-overview-cards" style={summaryGridStyle}>
        <KpiCard label="市场资产" value={formatYiAmount(BALANCE_MOCK_KPI.marketAssetsYi)} unit="亿" detail="债券+买入" />
        <KpiCard
          label="市场负债"
          value={formatYiAmount(BALANCE_MOCK_KPI.marketLiabilitiesYi)}
          unit="亿"
          detail="发行+买入"
        />
        <KpiCard label="静态资产收益率" value={`${BALANCE_MOCK_KPI.assetYieldPct}%`} detail="加权到期" />
        <KpiCard label="静态负债成本" value={`${BALANCE_MOCK_KPI.liabilityCostPct}%`} detail="当期加权" />
        <KpiCard
          label="静态利差"
          value={String(BALANCE_MOCK_KPI.staticSpreadBp)}
          unit="bp"
          detail="资产收益-负债成本"
        />
        <KpiCard
          label="1年内净缺口"
          value={formatYiAmount(BALANCE_MOCK_KPI.oneYearGapYi)}
          unit="亿"
          tone="negative"
          detail="短端缺口"
        />
        <KpiCard
          label="债券资产浮盈"
          value={`+${formatYiAmount(BALANCE_MOCK_KPI.bondFloatingGainYi)}`}
          unit="亿"
          tone="positive"
          detail="公允-摊余"
        />
        <KpiCard
          label="异常预警"
          value={String(BALANCE_MOCK_KPI.alertCount)}
          unit="项"
          status="warning"
          detail="缺口/滚续/集中度"
        />
      </div>

      <BalanceSummaryRow />
      <BalanceContributionRow />
      <BalanceBottomRow />

      <div
        data-testid="balance-analysis-supplemental-panels"
        style={{ marginTop: 20, display: "grid", gap: 16 }}
      >
        <SectionLead
          eyebrow="Analytical"
          title="补充分析与口径辅助"
          description="ADB 预览、会计口径拆解和高阶归因继续作为支持性分析区，保持现有只读查询和正式口径边界。"
        />
        <SectionCard
          title="ADB Analytical Preview"
          loading={adbComparisonQuery.isLoading}
          error={adbComparisonQuery.isError}
          onRetry={() => void adbComparisonQuery.refetch()}
        >
          {adbComparisonQuery.data ? <AdbAnalyticalPreview comparison={adbComparisonQuery.data} href={adbHref} /> : null}
        </SectionCard>
        <SectionCard
          title="按会计口径分解"
          loading={basisBreakdownQuery.isLoading}
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
          loading={advancedAttributionQuery.isLoading}
          error={advancedAttributionQuery.isError}
          onRetry={() => void advancedAttributionQuery.refetch()}
        >
          {advancedAttributionQuery.data?.result ? (
            <div style={{ display: "grid", gap: 10, fontSize: 13, color: "#31425b" }}>
              <div>
                <strong>状态</strong>：{advancedAttributionQuery.data.result.status} ·{" "}
                {advancedAttributionQuery.data.result.mode}
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

      <div data-testid="balance-analysis-summary" style={{ display: "none" }}>
        {String(overview?.detail_row_count ?? 0)} {String(overview?.summary_row_count ?? 0)}{" "}
        {String(overview?.total_market_value_amount ?? "0.00")}{" "}
        {String(overview?.total_amortized_cost_amount ?? "0.00")}{" "}
        {String(overview?.total_accrued_interest_amount ?? "0.00")}
      </div>

      <div style={{ marginTop: 24 }}>
        <SectionLead
          eyebrow="Summary"
          title="正式汇总驾驶舱"
          description="先阅读分页汇总表，再进入下方 detail summary 和明细下钻，保持 summary / detail 查询分层不变。"
        />
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
              rowData={summaryTable?.rows ?? []}
              columnDefs={balanceSummaryColDefs}
              defaultColDef={balanceAnalysisGridDefaultColDef}
              getRowId={(p) => String(p.data.row_key)}
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
              onClick={() => setSummaryOffset((current) => Math.max(0, current - PAGE_SIZE))}
              disabled={summaryOffset === 0}
              style={actionButtonStyle}
            >
              上一页
            </button>
            <span>{`第 ${currentPage} / ${totalPages} 页`}</span>
            <button
              type="button"
              onClick={() => setSummaryOffset((current) => current + PAGE_SIZE)}
              disabled={summaryOffset + PAGE_SIZE >= (summaryTable?.total_rows ?? 0)}
              style={actionButtonStyle}
            >
              下一页
            </button>
          </div>
          <div style={{ marginTop: 18 }}>
            <div style={{ color: "#8090a8", fontSize: 12, marginBottom: 8 }}>明细下钻预留</div>
            {!detailQuery.isLoading &&
            !detailQuery.isError &&
            (detailQuery.data?.result.summary?.length ?? 0) > 0 ? (
              <div style={{ marginBottom: 14 }}>
                <div style={{ color: "#8090a8", fontSize: 12, marginBottom: 8 }}>
                  明细接口返回的汇总切片（summary[]）
                </div>
                <div
                  className="ag-theme-alpine"
                  data-testid="balance-analysis-detail-summary-grid"
                  style={{ ...tableShellStyle, height: 200, width: "100%" }}
                >
                  <AgGridReact<BalanceAnalysisSummaryRow>
                    rowData={detailQuery.data?.result.summary ?? []}
                    columnDefs={balanceDetailSummaryColDefs}
                    defaultColDef={balanceAnalysisGridDefaultColDef}
                    getRowId={(p) =>
                      `${p.data.source_family}-${p.data.position_scope}-${p.data.currency_basis}`
                    }
                  />
                </div>
              </div>
            ) : null}
            {detailQuery.isError ? (
              <div
                style={{
                  borderRadius: 14,
                  border: "1px solid #ffd8bf",
                  background: "#fff7f0",
                  color: "#a14a14",
                  padding: 14,
                  fontSize: 13,
                }}
              >
                明细下钻暂时不可用，汇总驾驶舱仍可继续使用。
              </div>
            ) : detailQuery.isLoading ? (
              <div style={{ color: "#8090a8", fontSize: 13 }}>明细下钻加载中…</div>
            ) : (
              <div
                className="ag-theme-alpine"
                data-testid="balance-analysis-table"
                style={{ ...tableShellStyle, height: 320, width: "100%", padding: 0, marginTop: 8 }}
              >
                <AgGridReact<BalanceAnalysisDetailRow>
                  rowData={detailQuery.data?.result.details ?? []}
                  columnDefs={balanceDetailColDefs}
                  defaultColDef={balanceAnalysisGridDefaultColDef}
                  getRowId={(p) => String(p.data.row_key)}
                />
              </div>
            )}
          </div>
        </AsyncSection>
      </div>

      <div style={{ marginTop: 24 }}>
        <SectionLead
          eyebrow="Workbench"
          title="工作簿与治理侧栏"
          description="工作簿主栏承载正式 workbook 面板，右侧栏承载治理事项、事件日历、风险预警和详情下钻，保持现有契约和阅读顺序。"
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
          <div data-testid="balance-analysis-workbook-cards" style={summaryGridStyle}>
            {(workbook?.cards ?? []).map((card) => (
              <PlaceholderCard
                key={card.key}
                title={card.label}
                value={String(card.value)}
                detail={card.note ?? ""}
              />
            ))}
          </div>

          <div style={workbookCockpitLayoutStyle}>
            <div style={workbookMainRailStyle}>
              <div data-testid="balance-analysis-workbook-primary-grid" style={workbookPrimaryGridStyle}>
                {primaryWorkbookTables.map((table) => (
                  <article
                    key={table.key}
                    data-testid={`balance-analysis-workbook-panel-${table.key}`}
                    style={workbookPanelStyle}
                  >
                    <div style={workbookPanelHeaderStyle}>
                      <div>
                        <div style={{ color: "#162033", fontSize: 18, fontWeight: 600 }}>{table.title}</div>
                        <p
                          style={{
                            marginTop: 6,
                            marginBottom: 0,
                            color: "#5c6b82",
                            fontSize: 13,
                            lineHeight: 1.6,
                          }}
                        >
                          {workbookPanelNotes[table.key as (typeof primaryWorkbookTableKeys)[number]]}
                        </p>
                      </div>
                      <span style={workbookPanelBadgeStyle}>数据来源</span>
                    </div>
                    {renderWorkbookPrimaryPanel(table)}
                  </article>
                ))}
              </div>

              <div
                data-testid="balance-analysis-workbook-secondary-panels"
                style={workbookSecondaryPanelGridStyle}
              >
                {secondaryWorkbookPanelTables.map((table) => (
                  <article
                    key={table.key}
                    data-testid={`balance-analysis-workbook-panel-${table.key}`}
                    style={workbookPanelStyle}
                  >
                    <div style={workbookPanelHeaderStyle}>
                      <div>
                        <div style={{ color: "#162033", fontSize: 18, fontWeight: 600 }}>{table.title}</div>
                        <p
                          style={{
                            marginTop: 6,
                            marginBottom: 0,
                            color: "#5c6b82",
                            fontSize: 13,
                            lineHeight: 1.6,
                          }}
                        >
                          {workbookSecondaryPanelNotes[table.key as (typeof secondaryWorkbookPanelKeys)[number]]}
                        </p>
                      </div>
                      <span style={workbookPanelBadgeStyle}>分析视图</span>
                    </div>
                    {renderWorkbookSecondaryPanel(table)}
                  </article>
                ))}
              </div>
            </div>

            <aside data-testid="balance-analysis-right-rail" style={workbookRightRailStyle}>
              <div style={rightRailFilterRowStyle}>
                <label>
                  <span style={{ display: "block", marginBottom: 6, color: "#5c6b82", fontSize: 12 }}>
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
                <label>
                  <span style={{ display: "block", marginBottom: 6, color: "#5c6b82", fontSize: 12 }}>
                    预警等级
                  </span>
                  <select
                    aria-label="balance-risk-severity-filter"
                    value={riskSeverityFilter}
                    onChange={(event) => setRiskSeverityFilter(event.target.value as "all" | BalanceAnalysisSeverity)}
                    style={rightRailFilterStyle}
                  >
                    <option value="all">全部</option>
                    <option value="high">high</option>
                    <option value="medium">medium</option>
                    <option value="low">low</option>
                  </select>
                </label>
              </div>
              <article
                data-testid="balance-analysis-right-rail-panel-decision_items"
                style={workbookPanelStyle}
              >
                <div style={workbookPanelHeaderStyle}>
                  <div>
                    <div style={{ color: "#162033", fontSize: 18, fontWeight: 600 }}>决策事项</div>
                    <p
                      style={{
                        marginTop: 6,
                        marginBottom: 0,
                        color: "#5c6b82",
                        fontSize: 13,
                        lineHeight: 1.6,
                      }}
                    >
                      {decisionRailNote}
                    </p>
                  </div>
                  <span style={workbookPanelBadgeStyle}>治理事项</span>
                </div>
                {decisionActionError ? (
                  <div
                    data-testid="balance-analysis-decision-error"
                    style={{
                      marginBottom: 12,
                      borderRadius: 12,
                      border: "1px solid #ffd8bf",
                      background: "#fff7f0",
                      color: "#a14a14",
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
                    color: "#5c6b82",
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
                      border: "1px solid #d7dfea",
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
                      <div style={{ color: "#162033", fontSize: 18, fontWeight: 600 }}>{table.title}</div>
                      <p
                        style={{
                          marginTop: 6,
                          marginBottom: 0,
                          color: "#5c6b82",
                          fontSize: 13,
                          lineHeight: 1.6,
                        }}
                      >
                        {workbookRightRailNotes[table.key as (typeof rightRailWorkbookKeys)[number]]}
                      </p>
                    </div>
                    <span style={workbookPanelBadgeStyle}>治理事项</span>
                  </div>
                  {table.section_kind === "event_calendar"
                    ? renderEventCalendarPanel(table, {
                        onSelect: (row) => {
                          setSelectedDecisionKey(null);
                          setSelectedRiskAlertKey(null);
                          setSelectedEventCalendarKey(`${row.event_date}:${row.title}`);
                        },
                        selectedKey: selectedEventCalendarKey,
                      })
                    : table.section_kind === "risk_alerts"
                      ? renderRiskAlertsPanel(table, {
                          onSelect: (row) => {
                            setSelectedDecisionKey(null);
                            setSelectedEventCalendarKey(null);
                            setSelectedRiskAlertKey(`${row.severity}:${row.title}`);
                          },
                          selectedKey: selectedRiskAlertKey,
                        })
                      : renderWorkbookRightRailPanel(table)}
                </article>
              ))}
              <article data-testid="balance-analysis-right-rail-drilldown" style={workbookPanelStyle}>
                <div style={workbookPanelHeaderStyle}>
                  <div>
                    <div style={{ color: "#162033", fontSize: 18, fontWeight: 600 }}>详情下钻</div>
                    <p
                      style={{
                        marginTop: 6,
                        marginBottom: 0,
                        color: "#5c6b82",
                        fontSize: 13,
                        lineHeight: 1.6,
                      }}
                    >
                      选择一条事件日历或风险预警后，在这里查看完整说明。
                    </p>
                  </div>
                  <span style={workbookPanelBadgeStyle}>Drill-down</span>
                </div>
                {selectedDecision ? (
                  <div data-testid="balance-analysis-right-rail-drilldown-decision" style={{ display: "grid", gap: 8 }}>
                    <div style={{ color: "#162033", fontWeight: 700 }}>{selectedDecision.title}</div>
                    <div style={{ color: "#1f5eff", fontSize: 13 }}>
                      Latest status: {selectedDecision.latest_status.status}
                    </div>
                    <div style={{ color: "#5c6b82", fontSize: 13, lineHeight: 1.6 }}>
                      {selectedDecision.reason}
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: "#8090a8" }}>
                      <span>{selectedDecision.source_section}</span>
                      <span>{selectedDecision.rule_id}</span>
                      <span>{selectedDecision.rule_version}</span>
                    </div>
                    <div style={{ display: "grid", gap: 4, fontSize: 12, color: "#5c6b82" }}>
                      <span>
                        Updated by:{" "}
                        {selectedDecision.latest_status.updated_by
                          ? selectedDecision.latest_status.updated_by
                          : "Not updated"}
                      </span>
                      <span>
                        Updated at:{" "}
                        {selectedDecision.latest_status.updated_at
                          ? selectedDecision.latest_status.updated_at
                          : "Not updated"}
                      </span>
                      {selectedDecision.latest_status.comment ? (
                        <span>{selectedDecision.latest_status.comment}</span>
                      ) : null}
                    </div>
                  </div>
                ) : selectedEventCalendar ? (
                  <div data-testid="balance-analysis-right-rail-drilldown-event" style={{ display: "grid", gap: 8 }}>
                    <div style={{ color: "#162033", fontWeight: 700 }}>{selectedEventCalendar.title}</div>
                    <div style={{ color: "#1f5eff", fontSize: 13 }}>{selectedEventCalendar.event_date}</div>
                    <div style={{ color: "#5c6b82", fontSize: 13 }}>{selectedEventCalendar.impact_hint}</div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: "#8090a8" }}>
                      <span>{selectedEventCalendar.event_type}</span>
                      <span>{selectedEventCalendar.source}</span>
                      <span>{selectedEventCalendar.source_section}</span>
                    </div>
                  </div>
                ) : selectedRiskAlert ? (
                  <div data-testid="balance-analysis-right-rail-drilldown-risk" style={{ display: "grid", gap: 8 }}>
                    <div style={{ color: "#162033", fontWeight: 700 }}>{selectedRiskAlert.title}</div>
                    <div style={{ color: "#d9622b", fontSize: 13 }}>{selectedRiskAlert.severity}</div>
                    <div style={{ color: "#a14a14", fontSize: 13, lineHeight: 1.6 }}>
                      {selectedRiskAlert.reason}
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: "#b46a3c" }}>
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

          <div data-testid="balance-analysis-workbook-secondary-grid" style={workbookSecondaryGridStyle}>
            {secondaryWorkbookTables.map((table) => (
              <div key={table.key} data-testid={`balance-analysis-workbook-table-${table.key}`}>
                <div style={{ marginBottom: 8, color: "#162033", fontWeight: 600 }}>{table.title}</div>
                <div
                  className="ag-theme-alpine"
                  style={{ ...tableShellStyle, height: 280, width: "100%", padding: 0 }}
                >
                  <AgGridReact
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
        </AsyncSection>
      </div>

      {resultMetaSections.length > 0 && (
        <Collapse
          data-testid="balance-analysis-result-meta-collapse"
          defaultActiveKey={[]}
          items={[
            {
              key: "result-meta",
              label: "开发调试: Result Meta",
              forceRender: true,
              children: (
                <section data-testid="balance-analysis-result-meta" style={resultMetaGridStyle}>
                  {resultMetaSections.map((section) => (
                    <article
                      key={section.key}
                      data-testid={`balance-analysis-result-meta-${section.key}`}
                      style={resultMetaCardStyle}
                    >
                      <h2
                        style={{
                          margin: 0,
                          fontSize: 16,
                          fontWeight: 600,
                          color: "#162033",
                        }}
                      >
                        {section.title}
                      </h2>
                      <p style={{ marginTop: 8, marginBottom: 14, color: "#5c6b82", fontSize: 13 }}>
                        Inspect the governed formal provenance returned by the active query.
                      </p>
                      <dl style={resultMetaListStyle}>
                        <dt style={{ color: "#5c6b82" }}>basis</dt>
                        <dd style={{ margin: 0, color: "#162033" }}>{section.meta.basis}</dd>
                        <dt style={{ color: "#5c6b82" }}>result_kind</dt>
                        <dd style={{ margin: 0, color: "#162033" }}>{section.meta.result_kind}</dd>
                        <dt style={{ color: "#5c6b82" }}>source_version</dt>
                        <dd style={{ margin: 0, color: "#162033" }}>{section.meta.source_version}</dd>
                        <dt style={{ color: "#5c6b82" }}>rule_version</dt>
                        <dd style={{ margin: 0, color: "#162033" }}>{section.meta.rule_version}</dd>
                        <dt style={{ color: "#5c6b82" }}>cache_version</dt>
                        <dd style={{ margin: 0, color: "#162033" }}>{section.meta.cache_version}</dd>
                        <dt style={{ color: "#5c6b82" }}>quality_flag</dt>
                        <dd style={{ margin: 0, color: "#162033" }}>{section.meta.quality_flag}</dd>
                        <dt style={{ color: "#5c6b82" }}>generated_at</dt>
                        <dd style={{ margin: 0, color: "#162033" }}>{section.meta.generated_at}</dd>
                        <dt style={{ color: "#5c6b82" }}>trace_id</dt>
                        <dd style={{ margin: 0, color: "#162033" }}>{section.meta.trace_id}</dd>
                      </dl>
                    </article>
                  ))}
                </section>
              ),
            },
          ]}
          style={{ marginTop: 20 }}
        />
      )}
    </section>
  );
}
