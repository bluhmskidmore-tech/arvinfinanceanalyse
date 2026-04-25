import { AgGridReact } from "ag-grid-react";
import type { ColDef, ValueFormatterParams } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import type {
  BalanceAnalysisBasisBreakdownRow,
  BalanceAnalysisDetailRow,
  BalanceAnalysisSummaryRow,
  BalanceAnalysisTableRow,
} from "../../../api/contracts";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { SectionCard } from "../../../components/SectionCard";
import { PageSectionLead } from "../../../components/page/PagePrimitives";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { tableShellStyle, actionButtonStyle } from "../pages/BalanceAnalysisPage.styles";
import AdbAnalyticalPreview from "../components/AdbAnalyticalPreview";
import {
  formatBalanceAmountToYiFromYuan,
  formatBalanceGridThousandsValue,
} from "../pages/balanceAnalysisPageModel";

function thousandsValueFormatter(params: ValueFormatterParams) {
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

interface Props {
  datesQuery: ReturnType<typeof import("../hooks/useBalanceAnalysisData").useBalanceAnalysisData>["datesQuery"];
  overviewQuery: ReturnType<typeof import("../hooks/useBalanceAnalysisData").useBalanceAnalysisData>["overviewQuery"];
  summaryQuery: ReturnType<typeof import("../hooks/useBalanceAnalysisData").useBalanceAnalysisData>["summaryQuery"];
  detailQuery: ReturnType<typeof import("../hooks/useBalanceAnalysisData").useBalanceAnalysisData>["detailQuery"];
  workbookQuery: ReturnType<typeof import("../hooks/useBalanceAnalysisData").useBalanceAnalysisData>["workbookQuery"];
  basisBreakdownQuery: ReturnType<typeof import("../hooks/useBalanceAnalysisData").useBalanceAnalysisData>["basisBreakdownQuery"];
  adbComparisonQuery: ReturnType<typeof import("../hooks/useBalanceAnalysisData").useBalanceAnalysisData>["adbComparisonQuery"];
  advancedAttributionQuery: ReturnType<typeof import("../hooks/useBalanceAnalysisData").useBalanceAnalysisData>["advancedAttributionQuery"];
  summaryTable: ReturnType<typeof import("../hooks/useBalanceAnalysisData").useBalanceAnalysisData>["summaryTable"];
  summaryOffset: number;
  setSummaryOffset: (offset: number | ((prev: number) => number)) => void;
  totalPages: number;
  currentPage: number;
  PAGE_SIZE: number;
  adbHref: string;
  overview: ReturnType<typeof import("../hooks/useBalanceAnalysisData").useBalanceAnalysisData>["overview"];
}

export function BalanceAnalysisTableSection({
  datesQuery,
  overviewQuery,
  summaryQuery,
  detailQuery,
  workbookQuery,
  basisBreakdownQuery,
  adbComparisonQuery,
  advancedAttributionQuery,
  summaryTable,
  summaryOffset,
  setSummaryOffset,
  totalPages,
  currentPage,
  PAGE_SIZE,
  adbHref,
  overview,
}: Props) {
  return (
    <>
      <div
        data-testid="balance-analysis-supplemental-panels"
        style={{ marginTop: designTokens.space[5], display: "grid", gap: designTokens.space[4] }}
      >
        <PageSectionLead
          eyebrow="Analytical"
          title="Supporting Analytical"
          description="ADB 预览、会计口径拆解和高阶归因继续作为 supporting analytical 区域，帮助解释 formal 结果，但不替代正式结论。"
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
            <div
              style={{
                display: "grid",
                gap: designTokens.space[3],
                fontSize: designTokens.fontSize[13],
                color: designTokens.color.neutral[800],
              }}
            >
              <div>
                <strong>状态</strong>：{advancedAttributionQuery.data.result.status} ·{" "}
                {advancedAttributionQuery.data.result.mode}
              </div>
              <div>
                <strong>缺失输入</strong>（节选）：
                <ul style={{ margin: `${designTokens.space[2] - designTokens.space[1]}px 0 0`, paddingLeft: designTokens.space[5] - designTokens.space[1] }}>
                  {advancedAttributionQuery.data.result.missing_inputs.slice(0, 5).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <strong>提示</strong>：
                <ul style={{ margin: `${designTokens.space[2] - designTokens.space[1]}px 0 0`, paddingLeft: designTokens.space[5] - designTokens.space[1] }}>
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
        {formatBalanceAmountToYiFromYuan(overview?.total_market_value_amount)}{" "}
        {formatBalanceAmountToYiFromYuan(overview?.total_amortized_cost_amount)}{" "}
        {formatBalanceAmountToYiFromYuan(overview?.total_accrued_interest_amount)}
      </div>

      <div style={{ marginTop: designTokens.space[6] }}>
        <PageSectionLead
          eyebrow="Summary"
          title="正式汇总驾驶舱"
          description="先阅读分页汇总表，再进入下方 detail summary 和明细下钻，保持 summary / detail 查询分层不变。"
        />
        <AsyncSection
          title="资产负债汇总"
          isLoading={datesQuery.isLoading || overviewQuery.isLoading || summaryQuery.isLoading}
          isError={datesQuery.isError || overviewQuery.isError || summaryQuery.isError}
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
              gap: designTokens.space[3],
              marginTop: designTokens.space[3],
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
            <span style={{ ...tabularNumsStyle }}>{`第 ${currentPage} / ${totalPages} 页`}</span>
            <button
              type="button"
              onClick={() => setSummaryOffset((current) => current + PAGE_SIZE)}
              disabled={summaryOffset + PAGE_SIZE >= (summaryTable?.total_rows ?? 0)}
              style={actionButtonStyle}
            >
              下一页
            </button>
          </div>
          <div style={{ marginTop: designTokens.space[5] }}>
            <div
              style={{
                color: designTokens.color.neutral[600],
                fontSize: designTokens.fontSize[12],
                marginBottom: designTokens.space[2],
              }}
            >
              明细下钻预留
            </div>
            {!detailQuery.isLoading &&
            !detailQuery.isError &&
            (detailQuery.data?.result.summary?.length ?? 0) > 0 ? (
              <div style={{ marginBottom: designTokens.space[3] + designTokens.space[1] }}>
                <div
                  style={{
                    color: designTokens.color.neutral[600],
                    fontSize: designTokens.fontSize[12],
                    marginBottom: designTokens.space[2],
                  }}
                >
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
                  borderRadius: designTokens.space[3] + designTokens.space[1],
                  border: `1px solid ${designTokens.color.warning[200]}`,
                  background: designTokens.color.warning[50],
                  color: designTokens.color.warning[700],
                  padding: designTokens.space[3] + designTokens.space[1],
                  fontSize: designTokens.fontSize[13],
                }}
              >
                明细下钻暂时不可用，汇总驾驶舱仍可继续使用。
              </div>
            ) : detailQuery.isLoading ? (
              <div style={{ color: designTokens.color.neutral[600], fontSize: designTokens.fontSize[13] }}>
                明细下钻加载中…
              </div>
            ) : (
              <div
                className="ag-theme-alpine"
                data-testid="balance-analysis-table"
                style={{
                  ...tableShellStyle,
                  height: 320,
                  width: "100%",
                  padding: 0,
                  marginTop: designTokens.space[2],
                }}
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
    </>
  );
}
