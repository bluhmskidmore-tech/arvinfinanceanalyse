import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { modeBadgeStyle, summaryGridStyle, tableStyle } from "../../../components/page/pageStyles";
import { designTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import { shellTokens } from "../../../theme/tokens";
import { FilterBar } from "../../../components/FilterBar";
import type { LedgerMoneyValue, QdbGlMonthlyAnalysisSheet } from "../../../api/contracts";
import "./LedgerPnlPage.css";

const pageHeaderStyle = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: 16,
  marginBottom: 24,
} as const;

const pageSubtitleStyle = {
  marginTop: 10,
  marginBottom: 0,
  maxWidth: 860,
  color: designTokens.color.neutral[600],
  fontSize: 15,
  lineHeight: 1.75,
} as const;

const summaryGridStyleWithBottom = { ...summaryGridStyle, marginBottom: designTokens.space[5] } as const;

const summaryCardStyle = {
  border: `1px solid ${designTokens.color.neutral[200]}`,
  borderRadius: designTokens.radius.lg,
  padding: designTokens.space[4],
  background: shellTokens.colorBgSurface,
} as const;

const tableWrapStyle = {
  border: `1px solid ${designTokens.color.neutral[200]}`,
  borderRadius: designTokens.radius.lg,
  background: shellTokens.colorBgSurface,
  overflow: "auto",
} as const;

function formatMoney(value: LedgerMoneyValue | null | undefined) {
  if (value?.yi) {
    return `${value.yi} 亿元`;
  }
  const yuan = Number(value?.yuan);
  return `${Number.isFinite(yuan) ? (yuan / 100_000_000).toFixed(2) : "0.00"} 亿元`;
}

function reportDateToMonth(reportDate: string) {
  const match = /^(\d{4})-(\d{2})/.exec(reportDate.trim());
  return match ? `${match[1]}${match[2]}` : "";
}

function formatAnalysisValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "number") {
    return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
  }
  return String(value);
}

function findAnalysisSheet(
  sheets: QdbGlMonthlyAnalysisSheet[] | undefined,
  key: string,
) {
  return sheets?.find((sheet) => sheet.key === key);
}

function pickDisplayColumns(sheet: QdbGlMonthlyAnalysisSheet | undefined, limit = 4) {
  return (sheet?.columns ?? []).slice(0, limit);
}

type FinancialIndicatorStatusRow = {
  name: string;
  value: unknown;
  unit: string;
  status: string;
  source: string;
};

function textCell(row: Record<string, unknown>, column: string | undefined) {
  return column ? String(row[column] ?? "").trim() : "";
}

function buildFinancialIndicatorStatusRows(sheet: QdbGlMonthlyAnalysisSheet | undefined) {
  const columns = sheet?.columns ?? [];
  const nameColumn = columns.find((column) => column === "指标") ?? columns[0];
  const valueColumn = columns.find((column) => column === "当前值") ?? columns[1];
  const unitColumn = columns.find((column) => column === "单位") ?? columns[2];
  const statusColumn = columns.find((column) => column === "口径状态") ?? columns[3];
  const sourceColumn = columns.find((column) => column === "口径来源") ?? columns[4];

  return (sheet?.rows ?? [])
    .map((row): FinancialIndicatorStatusRow => ({
      name: textCell(row, nameColumn),
      value: valueColumn ? row[valueColumn] : undefined,
      unit: textCell(row, unitColumn),
      status: textCell(row, statusColumn),
      source: textCell(row, sourceColumn),
    }))
    .filter((row) => row.name);
}

function financialIndicatorTone(row: FinancialIndicatorStatusRow) {
  if (row.status.includes("QDB")) {
    return "analytical";
  }
  if (row.status.includes("待接入") || row.source.startsWith("formal_pending:")) {
    return "pending";
  }
  return "warning";
}

function formatFinancialIndicatorValue(row: FinancialIndicatorStatusRow) {
  if (row.value === null || row.value === undefined || row.value === "") {
    return "未接入";
  }
  const formatted = formatAnalysisValue(row.value);
  return row.unit && row.unit !== "待确认" ? `${formatted} ${row.unit}` : formatted;
}

function FinancialIndicatorStatusPanel(props: { rows: FinancialIndicatorStatusRow[] }) {
  const qdbCount = props.rows.filter((row) => financialIndicatorTone(row) === "analytical").length;
  const pendingCount = props.rows.filter((row) => financialIndicatorTone(row) === "pending").length;
  const sourceGapCount = props.rows.filter((row) => row.source.includes("source_missing") || row.source.includes("formal_pending")).length;

  return (
    <section data-testid="ledger-pnl-formal-indicator-status-panel" className="ledger-pnl-analysis__status-panel">
      <div className="ledger-pnl-analysis__status-header">
        <div>
          <h3 className="ledger-pnl-analysis__status-title">正式财务指标状态</h3>
          <div className="ledger-pnl-analysis__status-subtitle">
            展示后端月度工作簿返回的指标值、口径状态和来源缺口。
          </div>
        </div>
        <div className="ledger-pnl-analysis__status-summary">
          <span>QDB 可复算 {qdbCount}</span>
          <span>正式待接入 {pendingCount}</span>
          <span>缺口说明 {sourceGapCount}</span>
        </div>
      </div>
      {props.rows.length > 0 ? (
        <div className="ledger-pnl-analysis__status-list">
          {props.rows.map((row) => {
            const tone = financialIndicatorTone(row);
            return (
              <article
                key={row.name}
                className={`ledger-pnl-analysis__status-row ledger-pnl-analysis__status-row--${tone}`}
              >
                <div className="ledger-pnl-analysis__status-main">
                  <span className="ledger-pnl-analysis__status-name">{row.name}</span>
                  <span className="ledger-pnl-analysis__status-badge">{row.status || "口径待确认"}</span>
                </div>
                <div className="ledger-pnl-analysis__status-value">
                  {formatFinancialIndicatorValue(row)}
                </div>
                <div className="ledger-pnl-analysis__status-source">{row.source || "来源待确认"}</div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="ledger-pnl-analysis__empty">暂无财务指标状态数据</div>
      )}
    </section>
  );
}

function AnalysisTable(props: {
  title: string;
  sheet: QdbGlMonthlyAnalysisSheet | undefined;
  testId: string;
  columnLimit?: number;
  rowLimit?: number;
}) {
  const columns = pickDisplayColumns(props.sheet, props.columnLimit ?? 4);
  const rows = props.sheet?.rows.slice(0, props.rowLimit ?? 5) ?? [];
  return (
    <section data-testid={props.testId} className="ledger-pnl-analysis__table">
      <div className="ledger-pnl-analysis__table-title">
        {props.title}
      </div>
      {columns.length > 0 && rows.length > 0 ? (
        <table style={tableStyle}>
          <thead>
            <tr className="ledger-pnl-analysis__table-head-row">
              {columns.map((column) => (
                <th key={column} className="ledger-pnl-analysis__th">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={`${props.testId}-${rowIndex}`} className="ledger-pnl-analysis__tr">
                {columns.map((column) => (
                  <td key={column} className="ledger-pnl-analysis__td">
                    {formatAnalysisValue(row[column])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="ledger-pnl-analysis__empty">暂无可展示数据</div>
      )}
    </section>
  );
}

export default function LedgerPnlPage() {
  const client = useApiClient();
  const [searchParams] = useSearchParams();
  const reportDateFromQuery = searchParams.get("report_date")?.trim() ?? "";
  const currencyFromQuery = searchParams.get("currency")?.trim() ?? "";
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [currency, setCurrency] = useState("ALL");

  const datesQuery = useQuery({
    queryKey: ["ledger-pnl", "dates", client.mode],
    queryFn: () => client.getLedgerPnlDates(),
    retry: false,
  });

  const reportDates = useMemo(() => datesQuery.data?.result.dates ?? [], [datesQuery.data?.result.dates]);

  useEffect(() => {
    const firstDate = reportDates[0];
    if (!firstDate) {
      return;
    }
    if (reportDateFromQuery && reportDates.includes(reportDateFromQuery)) {
      setSelectedReportDate((current) => (current === reportDateFromQuery ? current : reportDateFromQuery));
      return;
    }
    if (!selectedReportDate || !reportDates.includes(selectedReportDate)) {
      setSelectedReportDate(firstDate);
    }
  }, [reportDateFromQuery, reportDates, selectedReportDate]);

  const effectiveCurrency = currency === "ALL" ? undefined : currency;

  const summaryQuery = useQuery({
    queryKey: ["ledger-pnl", "summary", client.mode, selectedReportDate, effectiveCurrency],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getLedgerPnlSummary(selectedReportDate, effectiveCurrency),
    retry: false,
  });

  const dataQuery = useQuery({
    queryKey: ["ledger-pnl", "data", client.mode, selectedReportDate, effectiveCurrency],
    enabled: Boolean(selectedReportDate),
    queryFn: () => client.getLedgerPnlData(selectedReportDate, effectiveCurrency),
    retry: false,
  });

  const monthlyAnalysisDatesQuery = useQuery({
    queryKey: ["ledger-pnl", "monthly-analysis", "dates", client.mode],
    queryFn: () => client.getQdbGlMonthlyAnalysisDates(),
    retry: false,
  });

  const summary = summaryQuery.data?.result;
  const data = dataQuery.data?.result;
  const monthlyAnalysisMonths = monthlyAnalysisDatesQuery.data?.result.report_months ?? [];
  const requestedAnalysisMonth = reportDateToMonth(selectedReportDate) || reportDateToMonth(reportDateFromQuery);
  const hasMatchingAnalysisMonth =
    Boolean(requestedAnalysisMonth) && monthlyAnalysisMonths.includes(requestedAnalysisMonth);
  const selectedAnalysisMonth = hasMatchingAnalysisMonth ? requestedAnalysisMonth : "";

  const monthlyAnalysisWorkbookQuery = useQuery({
    queryKey: ["ledger-pnl", "monthly-analysis", "workbook", client.mode, selectedAnalysisMonth],
    enabled: hasMatchingAnalysisMonth,
    queryFn: () => client.getQdbGlMonthlyAnalysisWorkbook({ reportMonth: selectedAnalysisMonth }),
    retry: false,
  });

  const monthlyAnalysisWorkbook = monthlyAnalysisWorkbookQuery.data?.result;
  const overviewSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "overview");
  const financialIndicatorStatusSheet = findAnalysisSheet(
    monthlyAnalysisWorkbook?.sheets,
    "financial_indicator_status",
  );
  const financialIndicatorStatusRows = useMemo(
    () => buildFinancialIndicatorStatusRows(financialIndicatorStatusSheet),
    [financialIndicatorStatusSheet],
  );
  const summary3dSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "summary_3d");
  const assetStructureSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "asset_structure");
  const liabilityStructureSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "liability_structure");
  const loanIndustrySheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "loan_industry");
  const depositDemandIndustrySheet = findAnalysisSheet(
    monthlyAnalysisWorkbook?.sheets,
    "deposit_demand_industry",
  );
  const depositTermIndustrySheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "deposit_term_industry");
  const top11dSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "top_11d");
  const alertsSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "alerts");
  const foreignCurrencySheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "foreign_currency");
  const segmentBaseScaleSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "segment_base_scale");
  const segmentScaleCompareSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "segment_scale_compare");
  const companyScaleSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "company_scale");
  const companyScaleCompareSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "company_scale_compare");
  const retailScaleSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "retail_scale");
  const retailScaleCompareSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "retail_scale_compare");
  const financialMarketScaleSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "financial_market_scale");
  const financialMarketScaleCompareSheet = findAnalysisSheet(
    monthlyAnalysisWorkbook?.sheets,
    "financial_market_scale_compare",
  );
  const incomeRateAnalysisSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "income_rate_analysis");
  const incomeRateAttributionSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "income_rate_attribution");
  const depositInterestSplitSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "deposit_interest_split");
  const parentCompanyRevenueSheet = findAnalysisSheet(
    monthlyAnalysisWorkbook?.sheets,
    "parent_company_revenue_components",
  );
  const industryGapSheet = findAnalysisSheet(monthlyAnalysisWorkbook?.sheets, "industry_gap");
  const overviewLabelColumn = overviewSheet?.columns[0];
  const overviewValueColumn = overviewSheet?.columns[1];
  const overviewRows =
    overviewLabelColumn && overviewValueColumn
      ? overviewSheet.rows.slice(0, 8).map((row) => ({
          label: formatAnalysisValue(row[overviewLabelColumn]),
          value: formatAnalysisValue(row[overviewValueColumn]),
        }))
      : [];

  const currencyOptions = useMemo(() => {
    const seen = new Set(["ALL"]);
    for (const item of summary?.by_currency ?? []) {
      if (item.currency) {
        seen.add(item.currency);
      }
    }
    for (const item of data?.items ?? []) {
      if (item.currency) {
        seen.add(item.currency);
      }
    }
    return Array.from(seen);
  }, [data?.items, summary?.by_currency]);

  useEffect(() => {
    if (!currencyFromQuery) {
      return;
    }
    if (!currencyOptions.includes(currencyFromQuery)) {
      return;
    }
    setCurrency((current) => (current === currencyFromQuery ? current : currencyFromQuery));
  }, [currencyFromQuery, currencyOptions]);

  useEffect(() => {
    const nextParams = new URLSearchParams(searchParams);
    if (selectedReportDate) {
      nextParams.set("report_date", selectedReportDate);
    } else {
      nextParams.delete("report_date");
    }
    if (currency !== "ALL") {
      nextParams.set("currency", currency);
    } else {
      nextParams.delete("currency");
    }

    if (typeof window === "undefined") {
      return;
    }
    if (nextParams.toString() !== window.location.search.replace(/^\?/, "")) {
      const nextUrl = new URL(window.location.href);
      nextUrl.search = nextParams.toString();
      window.history.replaceState({}, "", nextUrl);
    }
  }, [currency, searchParams, selectedReportDate]);

  return (
    <section data-testid="ledger-pnl-page">
      <div style={pageHeaderStyle}>
        <div>
          <h1
            data-testid="ledger-pnl-page-title"
            style={{ margin: 0, fontSize: 32, fontWeight: 600, letterSpacing: 0 }}
          >
            总账损益
          </h1>
          <p data-testid="ledger-pnl-page-subtitle" style={pageSubtitleStyle}>
            科目口径损益总览、币种汇总与账户明细。页面直接消费后端总账口径读模型，
            不在前端补算会计科目聚合。
          </p>
        </div>
        <span
          style={{
            ...modeBadgeStyle,
            background:
              client.mode === "real" ? designTokens.color.success[50] : designTokens.color.primary[50],
            color:
              client.mode === "real"
                ? displayTokens.apiMode.realForeground
                : displayTokens.apiMode.mockForeground,
          }}
        >
          {client.mode === "real" ? "正式只读链路" : "本地演示数据"}
        </span>
      </div>

      <FilterBar style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 20 }}>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: designTokens.color.neutral[600] }}>报告日</span>
          <select
            aria-label="ledger-pnl-report-date"
            value={selectedReportDate}
            onChange={(event) => setSelectedReportDate(event.target.value)}
            disabled={reportDates.length === 0}
            style={{
              minWidth: 180,
              padding: "10px 12px",
              borderRadius: designTokens.radius.md,
              border: `1px solid ${designTokens.color.neutral[200]}`,
            }}
          >
            {reportDates.length === 0 ? <option value="">暂无可选报告日</option> : null}
            {reportDates.map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {reportDate}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span style={{ display: "block", marginBottom: 6, color: designTokens.color.neutral[600] }}>币种</span>
          <select
            aria-label="ledger-pnl-currency"
            value={currency}
            onChange={(event) => setCurrency(event.target.value)}
            style={{
              minWidth: 140,
              padding: "10px 12px",
              borderRadius: designTokens.radius.md,
              border: `1px solid ${designTokens.color.neutral[200]}`,
            }}
          >
            {currencyOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </FilterBar>

      <section data-testid="ledger-pnl-monthly-analysis-panel" className="ledger-pnl-analysis">
        <div className="ledger-pnl-analysis__header">
          <div>
            <h2 className="ledger-pnl-analysis__title">
              总账对账 + 日均分析
            </h2>
            <div className="ledger-pnl-analysis__subtitle">
              月度工作簿口径，直接展示后端已重建的分析结果。
            </div>
          </div>
          <span data-testid="ledger-pnl-monthly-analysis-month" className="ledger-pnl-analysis__month">
            {selectedAnalysisMonth || (requestedAnalysisMonth ? `${requestedAnalysisMonth} 无匹配` : "暂无月份")}
          </span>
        </div>

        {!hasMatchingAnalysisMonth && !monthlyAnalysisDatesQuery.isLoading ? (
          <div data-testid="ledger-pnl-monthly-analysis-missing-month" className="ledger-pnl-analysis__empty">
            当前报告日没有对应月度分析工作簿
          </div>
        ) : null}

        {monthlyAnalysisDatesQuery.isError ? (
          <div data-testid="ledger-pnl-monthly-analysis-error" className="ledger-pnl-analysis__empty">
            月度分析月份读取失败
          </div>
        ) : null}

        {monthlyAnalysisWorkbookQuery.isError ? (
          <div data-testid="ledger-pnl-monthly-analysis-error" className="ledger-pnl-analysis__empty">
            月度分析工作簿读取失败
          </div>
        ) : null}

        <FinancialIndicatorStatusPanel rows={financialIndicatorStatusRows} />

        {overviewRows.length > 0 ? (
          <div data-testid="ledger-pnl-monthly-analysis-overview" className="ledger-pnl-analysis__kpis">
            {overviewRows.map((row) => (
              <div key={row.label} className="ledger-pnl-analysis__kpi">
                <div className="ledger-pnl-analysis__kpi-label">
                  {row.label}
                </div>
                <div className="ledger-pnl-analysis__kpi-value">
                  {row.value}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div data-testid="ledger-pnl-monthly-analysis-overview" className="ledger-pnl-analysis__empty">
            暂无经营概览数据
          </div>
        )}

        <div className="ledger-pnl-analysis__tables">
          <AnalysisTable
            title="财务指标落地状态"
            sheet={financialIndicatorStatusSheet}
            testId="ledger-pnl-monthly-analysis-financial-indicator-status"
            columnLimit={5}
            rowLimit={20}
          />
          <AnalysisTable
            title="3位科目总览"
            sheet={summary3dSheet}
            testId="ledger-pnl-monthly-analysis-summary-3d"
            columnLimit={8}
            rowLimit={8}
          />
          <AnalysisTable
            title="资产结构"
            sheet={assetStructureSheet}
            testId="ledger-pnl-monthly-analysis-asset-structure"
            columnLimit={6}
            rowLimit={8}
          />
          <AnalysisTable
            title="负债结构"
            sheet={liabilityStructureSheet}
            testId="ledger-pnl-monthly-analysis-liability-structure"
            columnLimit={6}
            rowLimit={8}
          />
          <AnalysisTable
            title="贷款行业"
            sheet={loanIndustrySheet}
            testId="ledger-pnl-monthly-analysis-loan-industry"
            columnLimit={7}
            rowLimit={8}
          />
          <AnalysisTable
            title="存款行业_活期"
            sheet={depositDemandIndustrySheet}
            testId="ledger-pnl-monthly-analysis-deposit-demand-industry"
            columnLimit={7}
            rowLimit={8}
          />
          <AnalysisTable
            title="存款行业_定期"
            sheet={depositTermIndustrySheet}
            testId="ledger-pnl-monthly-analysis-deposit-term-industry"
            columnLimit={7}
            rowLimit={8}
          />
          <AnalysisTable
            title="11位偏离TOP"
            sheet={top11dSheet}
            testId="ledger-pnl-monthly-analysis-top-11d"
            columnLimit={5}
          />
          <AnalysisTable
            title="异动预警"
            sheet={alertsSheet}
            testId="ledger-pnl-monthly-analysis-alerts"
            columnLimit={5}
          />
          <AnalysisTable
            title="分部基础规模"
            sheet={segmentBaseScaleSheet}
            testId="ledger-pnl-monthly-analysis-segment-base-scale"
            columnLimit={5}
          />
          <AnalysisTable
            title="分部规模同比环比"
            sheet={segmentScaleCompareSheet}
            testId="ledger-pnl-monthly-analysis-segment-scale-compare"
            columnLimit={7}
          />
          <AnalysisTable
            title="公司规模"
            sheet={companyScaleSheet}
            testId="ledger-pnl-monthly-analysis-company-scale"
            columnLimit={5}
          />
          <AnalysisTable
            title="公司规模同比环比"
            sheet={companyScaleCompareSheet}
            testId="ledger-pnl-monthly-analysis-company-scale-compare"
            columnLimit={7}
          />
          <AnalysisTable
            title="零售规模"
            sheet={retailScaleSheet}
            testId="ledger-pnl-monthly-analysis-retail-scale"
            columnLimit={5}
          />
          <AnalysisTable
            title="零售规模同比环比"
            sheet={retailScaleCompareSheet}
            testId="ledger-pnl-monthly-analysis-retail-scale-compare"
            columnLimit={7}
          />
          <AnalysisTable
            title="金融市场规模"
            sheet={financialMarketScaleSheet}
            testId="ledger-pnl-monthly-analysis-financial-market-scale"
            columnLimit={5}
          />
          <AnalysisTable
            title="金融市场规模同比环比"
            sheet={financialMarketScaleCompareSheet}
            testId="ledger-pnl-monthly-analysis-financial-market-scale-compare"
            columnLimit={7}
          />
          <AnalysisTable
            title="收益率分析（总账可复算）"
            sheet={incomeRateAnalysisSheet}
            testId="ledger-pnl-monthly-analysis-income-rate"
            columnLimit={7}
          />
          <AnalysisTable
            title="收益量价归因（年累计同比）"
            sheet={incomeRateAttributionSheet}
            testId="ledger-pnl-monthly-analysis-income-rate-attribution"
            columnLimit={9}
          />
          <AnalysisTable
            title="存款利息拆分"
            sheet={depositInterestSplitSheet}
            testId="ledger-pnl-monthly-analysis-deposit-interest-split"
            columnLimit={11}
            rowLimit={9}
          />
          <AnalysisTable
            title="母公司营收分项"
            sheet={parentCompanyRevenueSheet}
            testId="ledger-pnl-monthly-analysis-parent-company-revenue"
            columnLimit={11}
            rowLimit={17}
          />
          <AnalysisTable
            title="外币分析"
            sheet={foreignCurrencySheet}
            testId="ledger-pnl-monthly-analysis-foreign-currency"
            columnLimit={6}
            rowLimit={8}
          />
          <AnalysisTable
            title="行业存贷差"
            sheet={industryGapSheet}
            testId="ledger-pnl-monthly-analysis-industry-gap"
            columnLimit={5}
          />
        </div>
      </section>

      <div data-testid="ledger-pnl-summary-cards" style={summaryGridStyleWithBottom}>
        {[
          ["核心损益", formatMoney(summary?.ledger_monthly_pnl_core)],
          ["全量损益", formatMoney(summary?.ledger_monthly_pnl_all)],
          ["总资产", formatMoney(summary?.ledger_total_assets)],
          ["总负债", formatMoney(summary?.ledger_total_liabilities)],
          ["净资产", formatMoney(summary?.ledger_net_assets)],
        ].map(([title, value]) => (
          <div key={title} style={summaryCardStyle}>
            <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[600] }}>{title}</div>
            <div
              style={{
                fontSize: 22,
                fontWeight: 700,
                color: designTokens.color.neutral[900],
                marginTop: 10,
              }}
            >
              {value}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
        <div style={tableWrapStyle}>
          <div
            style={{
              padding: designTokens.space[4],
              fontWeight: 600,
              borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
            }}
          >
            币种汇总
          </div>
          <table style={tableStyle}>
            <thead>
              <tr style={{ background: designTokens.color.neutral[50] }}>
                <th style={{ textAlign: "left", padding: designTokens.space[3] }}>币种</th>
                <th style={{ textAlign: "right", padding: designTokens.space[3] }}>损益</th>
              </tr>
            </thead>
            <tbody>
              {(summary?.by_currency ?? []).map((item) => (
                <tr key={item.currency} style={{ borderTop: `1px solid ${designTokens.color.neutral[100]}` }}>
                  <td style={{ padding: designTokens.space[3] }}>{item.currency}</td>
                  <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.total_pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={tableWrapStyle}>
          <div
            style={{
              padding: designTokens.space[4],
              fontWeight: 600,
              borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
            }}
          >
            科目汇总
          </div>
          <table style={tableStyle}>
            <thead>
              <tr style={{ background: designTokens.color.neutral[50] }}>
                <th style={{ textAlign: "left", padding: designTokens.space[3] }}>科目</th>
                <th style={{ textAlign: "right", padding: designTokens.space[3] }}>损益</th>
                <th style={{ textAlign: "right", padding: designTokens.space[3] }}>笔数</th>
              </tr>
            </thead>
            <tbody>
              {(summary?.by_account ?? []).map((item) => (
                <tr key={item.account_code} style={{ borderTop: `1px solid ${designTokens.color.neutral[100]}` }}>
                  <td style={{ padding: designTokens.space[3] }}>
                    <div>{item.account_code}</div>
                    <div style={{ color: designTokens.color.neutral[600], fontSize: designTokens.fontSize[12] }}>
                      {item.account_name}
                    </div>
                  </td>
                  <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.total_pnl)}</td>
                  <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{item.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div data-testid="ledger-pnl-detail-table" style={tableWrapStyle}>
        <div
          style={{
            padding: designTokens.space[4],
            fontWeight: 600,
            borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
          }}
        >
          科目明细
        </div>
        <table style={tableStyle}>
          <thead>
            <tr style={{ background: designTokens.color.neutral[50] }}>
              <th style={{ textAlign: "left", padding: designTokens.space[3] }}>科目代码</th>
              <th style={{ textAlign: "left", padding: designTokens.space[3] }}>科目名称</th>
              <th style={{ textAlign: "left", padding: designTokens.space[3] }}>币种</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>期初</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>期末</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>月损益</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>月日均</th>
              <th style={{ textAlign: "right", padding: designTokens.space[3] }}>天数</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items ?? []).map((item) => (
              <tr key={`${item.account_code}-${item.currency}`} style={{ borderTop: `1px solid ${designTokens.color.neutral[100]}` }}>
                <td style={{ padding: designTokens.space[3] }}>{item.account_code}</td>
                <td style={{ padding: designTokens.space[3] }}>{item.account_name}</td>
                <td style={{ padding: designTokens.space[3] }}>{item.currency}</td>
                <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.beginning_balance)}</td>
                <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.ending_balance)}</td>
                <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.monthly_pnl)}</td>
                <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{formatMoney(item.daily_avg_balance)}</td>
                <td style={{ padding: designTokens.space[3], textAlign: "right" }}>{item.days_in_period}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <FormalResultMetaPanel
        testId="ledger-pnl-result-meta-panel"
        sections={[
          { key: "dates", title: "Ledger 报告日", meta: datesQuery.data?.result_meta },
          { key: "summary", title: "Ledger 汇总", meta: summaryQuery.data?.result_meta },
          { key: "data", title: "Ledger 明细", meta: dataQuery.data?.result_meta },
          { key: "monthly-analysis-dates", title: "月度分析月份", meta: monthlyAnalysisDatesQuery.data?.result_meta },
          {
            key: "monthly-analysis-workbook",
            title: "月度分析工作簿",
            meta: monthlyAnalysisWorkbookQuery.data?.result_meta,
          },
        ]}
      />
    </section>
  );
}
