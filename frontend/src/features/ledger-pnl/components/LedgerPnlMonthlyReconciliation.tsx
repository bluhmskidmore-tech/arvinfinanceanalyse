import { useMemo } from "react";
import type {
  ApiEnvelope,
  LedgerPnlFormalFinancialIndicatorContractPayload,
  LedgerPnlFormalIndicatorRuleChecksPayload,
  QdbGlMonthlyAnalysisSheet,
  QdbGlMonthlyAnalysisWorkbookPayload,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { monthlyWorkbookAuditState } from "../models/ledgerPnlSourceEvidence";
import { formalContractCollapsedSummary } from "../models/ledgerPnlFormalContractModel";
import { LedgerPnlFormalSourceContractPanel } from "./LedgerPnlFormalSourceContractPanel";
import { LedgerPnlFormalRuleChecksPanel } from "./LedgerPnlFormalRuleChecksPanel";
import { LedgerSectionSkeleton } from "./LedgerPnlSectionPresentation";
import { LedgerPnlWorkbookTables, type LedgerPnlWorkbookTableSpec } from "./LedgerPnlWorkbookTables";
import { buildLedgerPnlWorkbookGroups } from "./ledgerPnlWorkbookTablesSupport";

function formatAnalysisValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
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

export function LedgerPnlMonthlyReconciliation({
  requestedAnalysisMonth,
  selectedAnalysisMonth,
  deferred,
  hasMatchingAnalysisMonth,
  monthlyAnalysisDatesQuery,
  monthlyAnalysisWorkbookQuery,
  formalIndicatorSourceContractQuery,
  formalIndicatorRuleChecksQuery,
}: {
  requestedAnalysisMonth: string;
  selectedAnalysisMonth: string;
  deferred: boolean;
  hasMatchingAnalysisMonth: boolean;
  monthlyAnalysisDatesQuery: { isLoading: boolean; isError: boolean };
  monthlyAnalysisWorkbookQuery: {
    data: ApiEnvelope<QdbGlMonthlyAnalysisWorkbookPayload> | undefined;
    isLoading: boolean;
    isError: boolean;
  };
  formalIndicatorSourceContractQuery: {
    data: ApiEnvelope<LedgerPnlFormalFinancialIndicatorContractPayload> | undefined;
    isLoading: boolean;
    isError: boolean;
  };
  formalIndicatorRuleChecksQuery: {
    data: ApiEnvelope<LedgerPnlFormalIndicatorRuleChecksPayload> | undefined;
    isLoading: boolean;
    isError: boolean;
  };
}) {
  const monthlyAnalysisWorkbook = monthlyAnalysisWorkbookQuery.data?.result;
  const formalIndicatorSourceContract = formalIndicatorSourceContractQuery.data?.result;
  const formalIndicatorRuleChecks = formalIndicatorRuleChecksQuery.data?.result;
  const monthlyWorkbookState = monthlyWorkbookAuditState({
    requestedReportMonth: requestedAnalysisMonth,
    hasMatchingAnalysisMonth,
    isMonthlyAnalysisDatesLoading: monthlyAnalysisDatesQuery.isLoading,
    isMonthlyAnalysisDatesError: monthlyAnalysisDatesQuery.isError,
    isMonthlyAnalysisWorkbookLoading: monthlyAnalysisWorkbookQuery.isLoading,
    isMonthlyAnalysisWorkbookError: monthlyAnalysisWorkbookQuery.isError,
    monthlyAnalysisWorkbook,
    monthlyAnalysisWorkbookMeta: monthlyAnalysisWorkbookQuery.data?.result_meta,
  });
  const trustedMonthlyAnalysisWorkbook = monthlyWorkbookState.isTrusted ? monthlyAnalysisWorkbook : undefined;
  const overviewSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "overview");
  const financialIndicatorStatusSheet = findAnalysisSheet(
    trustedMonthlyAnalysisWorkbook?.sheets,
    "financial_indicator_status",
  );
  const financialIndicatorStatusRows = useMemo(
    () => buildFinancialIndicatorStatusRows(financialIndicatorStatusSheet),
    [financialIndicatorStatusSheet],
  );
  const summary3dSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "summary_3d");
  const assetStructureSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "asset_structure");
  const liabilityStructureSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "liability_structure");
  const loanIndustrySheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "loan_industry");
  const depositDemandIndustrySheet = findAnalysisSheet(
    trustedMonthlyAnalysisWorkbook?.sheets,
    "deposit_demand_industry",
  );
  const depositTermIndustrySheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "deposit_term_industry");
  const top11dSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "top_11d");
  const alertsSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "alerts");
  const foreignCurrencySheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "foreign_currency");
  const segmentBaseScaleSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "segment_base_scale");
  const segmentScaleCompareSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "segment_scale_compare");
  const companyScaleSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "company_scale");
  const companyScaleCompareSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "company_scale_compare");
  const retailScaleSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "retail_scale");
  const retailScaleCompareSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "retail_scale_compare");
  const financialMarketScaleSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "financial_market_scale");
  const financialMarketScaleCompareSheet = findAnalysisSheet(
    trustedMonthlyAnalysisWorkbook?.sheets,
    "financial_market_scale_compare",
  );
  const incomeRateAnalysisSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "income_rate_analysis");
  const incomeRateAttributionSheet = findAnalysisSheet(
    trustedMonthlyAnalysisWorkbook?.sheets,
    "income_rate_attribution",
  );
  const depositInterestSplitSheet = findAnalysisSheet(
    trustedMonthlyAnalysisWorkbook?.sheets,
    "deposit_interest_split",
  );
  const parentCompanyRevenueSheet = findAnalysisSheet(
    trustedMonthlyAnalysisWorkbook?.sheets,
    "parent_company_revenue_components",
  );
  const industryGapSheet = findAnalysisSheet(trustedMonthlyAnalysisWorkbook?.sheets, "industry_gap");
  const monthlyWorkbookGroups = useMemo(() => {
    const specs: LedgerPnlWorkbookTableSpec[] = [
      { title: "财务指标落地状态", sheet: financialIndicatorStatusSheet, testId: "ledger-pnl-monthly-analysis-financial-indicator-status", columnLimit: 5, rowLimit: 20 },
      { title: "3位科目总览", sheet: summary3dSheet, testId: "ledger-pnl-monthly-analysis-summary-3d", columnLimit: 8, rowLimit: 8 },
      { title: "资产结构", sheet: assetStructureSheet, testId: "ledger-pnl-monthly-analysis-asset-structure", columnLimit: 6, rowLimit: 8 },
      { title: "负债结构", sheet: liabilityStructureSheet, testId: "ledger-pnl-monthly-analysis-liability-structure", columnLimit: 6, rowLimit: 8 },
      { title: "贷款行业", sheet: loanIndustrySheet, testId: "ledger-pnl-monthly-analysis-loan-industry", columnLimit: 7, rowLimit: 8 },
      { title: "存款行业_活期", sheet: depositDemandIndustrySheet, testId: "ledger-pnl-monthly-analysis-deposit-demand-industry", columnLimit: 7, rowLimit: 8 },
      { title: "存款行业_定期", sheet: depositTermIndustrySheet, testId: "ledger-pnl-monthly-analysis-deposit-term-industry", columnLimit: 7, rowLimit: 8 },
      { title: "11位偏离TOP", sheet: top11dSheet, testId: "ledger-pnl-monthly-analysis-top-11d", columnLimit: 5 },
      { title: "异动预警", sheet: alertsSheet, testId: "ledger-pnl-monthly-analysis-alerts", columnLimit: 5 },
      { title: "分部基础规模", sheet: segmentBaseScaleSheet, testId: "ledger-pnl-monthly-analysis-segment-base-scale", columnLimit: 5 },
      { title: "分部规模同比环比", sheet: segmentScaleCompareSheet, testId: "ledger-pnl-monthly-analysis-segment-scale-compare", columnLimit: 7 },
      { title: "公司规模", sheet: companyScaleSheet, testId: "ledger-pnl-monthly-analysis-company-scale", columnLimit: 5 },
      { title: "公司规模同比环比", sheet: companyScaleCompareSheet, testId: "ledger-pnl-monthly-analysis-company-scale-compare", columnLimit: 7 },
      { title: "零售规模", sheet: retailScaleSheet, testId: "ledger-pnl-monthly-analysis-retail-scale", columnLimit: 5 },
      { title: "零售规模同比环比", sheet: retailScaleCompareSheet, testId: "ledger-pnl-monthly-analysis-retail-scale-compare", columnLimit: 7 },
      { title: "金融市场规模", sheet: financialMarketScaleSheet, testId: "ledger-pnl-monthly-analysis-financial-market-scale", columnLimit: 5 },
      { title: "金融市场规模同比环比", sheet: financialMarketScaleCompareSheet, testId: "ledger-pnl-monthly-analysis-financial-market-scale-compare", columnLimit: 7 },
      { title: "收益率分析（总账可复算）", sheet: incomeRateAnalysisSheet, testId: "ledger-pnl-monthly-analysis-income-rate", columnLimit: 7 },
      { title: "收益量价归因（年累计同比）", sheet: incomeRateAttributionSheet, testId: "ledger-pnl-monthly-analysis-income-rate-attribution", columnLimit: 9 },
      { title: "存款利息拆分", sheet: depositInterestSplitSheet, testId: "ledger-pnl-monthly-analysis-deposit-interest-split", columnLimit: 11, rowLimit: 9 },
      { title: "母公司营收分项", sheet: parentCompanyRevenueSheet, testId: "ledger-pnl-monthly-analysis-parent-company-revenue", columnLimit: 11, rowLimit: 17 },
      { title: "外币分析", sheet: foreignCurrencySheet, testId: "ledger-pnl-monthly-analysis-foreign-currency", columnLimit: 6, rowLimit: 8 },
      { title: "行业存贷差", sheet: industryGapSheet, testId: "ledger-pnl-monthly-analysis-industry-gap", columnLimit: 5 },
    ];
    return buildLedgerPnlWorkbookGroups(
      Object.fromEntries(specs.map((spec) => [spec.title, spec])),
    );
  }, [
    alertsSheet,
    assetStructureSheet,
    companyScaleCompareSheet,
    companyScaleSheet,
    depositDemandIndustrySheet,
    depositInterestSplitSheet,
    depositTermIndustrySheet,
    financialIndicatorStatusSheet,
    financialMarketScaleCompareSheet,
    financialMarketScaleSheet,
    foreignCurrencySheet,
    incomeRateAnalysisSheet,
    incomeRateAttributionSheet,
    industryGapSheet,
    liabilityStructureSheet,
    loanIndustrySheet,
    parentCompanyRevenueSheet,
    retailScaleCompareSheet,
    retailScaleSheet,
    segmentBaseScaleSheet,
    segmentScaleCompareSheet,
    summary3dSheet,
    top11dSheet,
  ]);
  const overviewLabelColumn = overviewSheet?.columns[0];
  const overviewValueColumn = overviewSheet?.columns[1];
  const overviewRows =
    overviewLabelColumn && overviewValueColumn
      ? overviewSheet.rows.slice(0, 8).map((row) => ({
          label: formatAnalysisValue(row[overviewLabelColumn]),
          value: formatAnalysisValue(row[overviewValueColumn]),
        }))
      : [];

  return (
        <section
          data-testid="ledger-pnl-monthly-analysis-panel"
          className="ledger-pnl-analysis"
        >
        <div className="ledger-pnl-analysis__header">
          <div>
            <h3 className="ledger-pnl-analysis__title">
              总账对账 + 日均分析
            </h3>
          </div>
          <span data-testid="ledger-pnl-monthly-analysis-month" className="ledger-pnl-analysis__month">
            {selectedAnalysisMonth ||
              (monthlyAnalysisDatesQuery.isError
                ? "月份读取失败"
                : requestedAnalysisMonth
                  ? `${requestedAnalysisMonth} 无匹配`
                  : "暂无月份")}
          </span>
        </div>

        {deferred ? (
          <LedgerSectionSkeleton
            testId="ledger-pnl-reconciliation-skeleton"
            title="对账明细与正式契约"
            minHeight={420}
          />
        ) : (
          <>
        {monthlyAnalysisDatesQuery.isError ? (
          <div data-testid="ledger-pnl-monthly-analysis-error" className="ledger-pnl-analysis__empty">
            月度分析月份读取失败
          </div>
        ) : null}

        {!hasMatchingAnalysisMonth &&
        !monthlyAnalysisDatesQuery.isLoading &&
        !monthlyAnalysisDatesQuery.isError ? (
          <div data-testid="ledger-pnl-monthly-analysis-missing-month" className="ledger-pnl-analysis__empty">
            当前报告日没有对应月度分析工作簿
          </div>
        ) : null}

        {monthlyAnalysisWorkbookQuery.isError ? (
          <div data-testid="ledger-pnl-monthly-analysis-error" className="ledger-pnl-analysis__empty">
            月度分析工作簿读取失败
          </div>
        ) : null}

        {monthlyWorkbookState.blockingDetail && hasMatchingAnalysisMonth ? (
          <div data-testid="ledger-pnl-monthly-analysis-trust-warning" className="ledger-pnl-analysis__empty">
            {monthlyWorkbookState.blockingDetail}；月度分析表已隐藏，避免把不可信 QDB 工作簿当作本月分析结果。
          </div>
        ) : null}

        <details className="ledger-pnl-formal-contract-collapse">
          <summary
            data-testid="ledger-pnl-formal-indicator-source-contract-collapse-summary"
            className="ledger-pnl-formal-contract-collapse__summary"
          >
            {formalContractCollapsedSummary(
              formalIndicatorSourceContract,
              formalIndicatorSourceContractQuery.isLoading,
              formalIndicatorSourceContractQuery.isError,
            )}
          </summary>
          <LedgerPnlFormalSourceContractPanel
            contract={formalIndicatorSourceContract}
            requestedReportMonth={requestedAnalysisMonth}
            isLoading={formalIndicatorSourceContractQuery.isLoading}
            isError={formalIndicatorSourceContractQuery.isError}
          />
        </details>

        <LedgerPnlFormalRuleChecksPanel
          ruleChecks={formalIndicatorRuleChecks}
          requestedReportMonth={requestedAnalysisMonth}
          isLoading={formalIndicatorRuleChecksQuery.isLoading}
          isError={formalIndicatorRuleChecksQuery.isError}
        />

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

        <LedgerPnlWorkbookTables groups={monthlyWorkbookGroups} />
          </>
        )}
        </section>
  );
}
