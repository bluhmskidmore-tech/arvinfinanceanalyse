import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type {
  BalanceCurrencyBasis,
  BalancePositionScope,
} from "../../../api/contracts";
import { runPollingTask } from "../../../app/jobs/polling";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { PlaceholderCard } from "../../workbench/components/PlaceholderCard";

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
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

const tableStyle = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 13,
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

function downloadCsvFile(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export default function BalanceAnalysisPage() {
  const client = useApiClient();
  const [selectedReportDate, setSelectedReportDate] = useState("");
  const [positionScope, setPositionScope] = useState<BalancePositionScope>("all");
  const [currencyBasis, setCurrencyBasis] = useState<BalanceCurrencyBasis>("CNY");
  const [summaryOffset, setSummaryOffset] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const datesQuery = useQuery({
    queryKey: ["balance-analysis", "dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });

  useEffect(() => {
    const firstDate = datesQuery.data?.result.report_dates?.[0];
    if (!selectedReportDate && firstDate) {
      setSelectedReportDate(firstDate);
    }
  }, [datesQuery.data?.result.report_dates, selectedReportDate]);

  useEffect(() => {
    setSummaryOffset(0);
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

  const overview = overviewQuery.data?.result;
  const overviewMeta = overviewQuery.data?.result_meta;
  const detailMeta = detailQuery.data?.result_meta;
  const workbookMeta = workbookQuery.data?.result_meta;
  const summaryMeta = summaryQuery.data?.result_meta;
  const workbook = workbookQuery.data?.result;
  const summaryTable = summaryQuery.data?.result;
  const resultMetaSections = [
    overviewMeta ? { key: "overview", title: "Overview Result Meta", meta: overviewMeta } : null,
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
        workbookQuery.refetch(),
        detailQuery.refetch(),
        summaryQuery.refetch(),
      ]);
    } catch (error) {
      setRefreshError(error instanceof Error ? error.message : "刷新资产负债分析失败");
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleExport() {
    if (!selectedReportDate) {
      return;
    }
    setIsExporting(true);
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
      setIsExporting(false);
    }
  }

  const totalPages = Math.max(
    1,
    Math.ceil((summaryTable?.total_rows ?? 0) / (summaryTable?.limit ?? PAGE_SIZE)),
  );
  const currentPage = Math.floor(summaryOffset / (summaryTable?.limit ?? PAGE_SIZE)) + 1;

  return (
    <section>
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{
            margin: 0,
            fontSize: 32,
            fontWeight: 600,
            letterSpacing: "-0.03em",
          }}
        >
          资产负债分析
        </h1>
        <p
          style={{
            marginTop: 10,
            marginBottom: 0,
            maxWidth: 860,
            color: "#5c6b82",
            fontSize: 15,
            lineHeight: 1.75,
          }}
        >
          第一张 governed balance-analysis consumer。页面只消费 formal facts，不读取 preview 或 snapshot。
        </p>
      </div>

      <div style={controlBarStyle}>
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
          disabled={!selectedReportDate || isExporting}
          style={actionButtonStyle}
        >
          {isExporting ? "导出中..." : "导出 CSV"}
        </button>
      </div>

      <div data-testid="balance-analysis-overview-cards" style={summaryGridStyle}>
        <PlaceholderCard
          title="明细行数"
          value={String(overview?.detail_row_count ?? 0)}
          detail="当前筛选条件下的 formal detail 行数。"
        />
        <PlaceholderCard
          title="汇总分组"
          value={String(overview?.summary_row_count ?? 0)}
          detail="按 source_family / position_scope / currency_basis 聚合后的组数。"
        />
        <PlaceholderCard
          title="总规模"
          value={String(overview?.total_market_value_amount ?? "0.00")}
          detail="当前 summary.market_value_amount 求和。"
        />
        <PlaceholderCard
          title="摊余成本"
          value={String(overview?.total_amortized_cost_amount ?? "0.00")}
          detail="当前 formal 摊余成本总额。"
        />
        <PlaceholderCard
          title="应计利息"
          value={String(overview?.total_accrued_interest_amount ?? "0.00")}
          detail="当前 formal 应计利息总额。"
        />
      </div>

      <div data-testid="balance-analysis-summary" style={{ display: "none" }}>
        {String(overview?.detail_row_count ?? 0)} {String(overview?.summary_row_count ?? 0)}{" "}
        {String(overview?.total_market_value_amount ?? "0.00")}
      </div>

      {resultMetaSections.length > 0 && (
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
      )}

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

      <div style={{ marginTop: 24 }}>
        <AsyncSection
          title="债券/组合汇总表现"
          isLoading={
            datesQuery.isLoading ||
            overviewQuery.isLoading ||
            detailQuery.isLoading ||
            summaryQuery.isLoading
          }
          isError={
            datesQuery.isError ||
            overviewQuery.isError ||
            detailQuery.isError ||
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
          <div style={tableShellStyle}>
            <table data-testid="balance-analysis-summary-table" style={tableStyle}>
              <thead>
                <tr>
                  {[
                    "来源",
                    "组合名称",
                    "分类",
                    "规模(亿)",
                    "摊余成本",
                    "应计利息",
                    "明细行数",
                    "会计口径",
                  ].map((label) => (
                    <th
                      key={label}
                      style={{
                        textAlign: "left",
                        padding: "10px 12px",
                        borderBottom: "1px solid #e4ebf5",
                        color: "#5c6b82",
                        fontSize: 13,
                      }}
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(summaryTable?.rows ?? []).map((row) => (
                  <tr key={row.row_key}>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.source_family.toUpperCase()}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.owner_name}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.category_name}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.market_value_amount}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.amortized_cost_amount}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.accrued_interest_amount}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.detail_row_count}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.invest_type_std} / {row.accounting_basis}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
            <table data-testid="balance-analysis-table" style={tableStyle}>
              <thead>
                <tr>
                  {["来源", "标识", "范围", "会计口径", "规模", "应计利息"].map((label) => (
                    <th
                      key={label}
                      style={{
                        textAlign: "left",
                        padding: "10px 12px",
                        borderBottom: "1px solid #e4ebf5",
                        color: "#5c6b82",
                        fontSize: 13,
                      }}
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(detailQuery.data?.result.details ?? []).map((row) => (
                  <tr key={row.row_key}>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.source_family.toUpperCase()}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.display_name}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.position_scope}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.invest_type_std} / {row.accounting_basis}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.market_value_amount}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}>
                      {row.accrued_interest_amount}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AsyncSection>
      </div>

      <div style={{ marginTop: 24 }}>
        <AsyncSection
          title="Excel 分析视图"
          isLoading={
            datesQuery.isLoading ||
            workbookQuery.isLoading
          }
          isError={datesQuery.isError || workbookQuery.isError}
          isEmpty={!workbookQuery.isLoading && (workbook?.tables.length ?? 0) === 0}
          onRetry={() => {
            void Promise.all([datesQuery.refetch(), workbookQuery.refetch()]);
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

          <div style={{ marginTop: 18, display: "grid", gap: 18 }}>
            {(workbook?.tables ?? []).map((table) => (
              <div key={table.key} data-testid={`balance-analysis-workbook-table-${table.key}`}>
                <div style={{ marginBottom: 8, color: "#162033", fontWeight: 600 }}>{table.title}</div>
                <div style={tableShellStyle}>
                  <table style={tableStyle}>
                    <thead>
                      <tr>
                        {table.columns.map((column) => (
                          <th
                            key={column.key}
                            style={{
                              textAlign: "left",
                              padding: "10px 12px",
                              borderBottom: "1px solid #e4ebf5",
                              color: "#5c6b82",
                              fontSize: 13,
                            }}
                          >
                            {column.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {table.rows.map((row, index) => (
                        <tr key={`${table.key}-${index}`}>
                          {table.columns.map((column) => (
                            <td
                              key={column.key}
                              style={{ padding: "12px", borderBottom: "1px solid #eef2f7" }}
                            >
                              {String(row[column.key] ?? "")}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </AsyncSection>
      </div>
    </section>
  );
}
