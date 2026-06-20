import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import type { QdbGlMonthlyAnalysisSheet, ResultMeta } from "../../../api/contracts";
import type { QdbGlMonthlyAnalysisRefreshPayload } from "../../../api/qdbGlMonthlyAnalysisClient";
import { designTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";

const pageHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: 16,
  padding: 20,
  borderRadius: 18,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.neutral[50],
  marginBottom: 18,
} as const;

const chipTypography = {
  display: "inline-flex",
  alignItems: "center",
  padding: "8px 12px",
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase" as const,
} as const;

const sectionLeadWrapStyle = {
  display: "grid",
  gap: 6,
  marginBottom: 14,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: designTokens.color.neutral[500],
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: designTokens.color.neutral[900],
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 900,
  color: designTokens.color.neutral[600],
  fontSize: 13,
  lineHeight: 1.7,
} as const;

const statusPanelStyle = {
  display: "grid",
  gap: 8,
  marginBottom: 12,
  padding: 12,
  borderRadius: 8,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.neutral[50],
  color: designTokens.color.neutral[700],
  fontSize: 12,
  lineHeight: 1.6,
} as const;

const statusLineWrapStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: 8,
} as const;

const statusLineStyle = {
  padding: "4px 8px",
  borderRadius: 6,
  background: designTokens.color.neutral[100],
} as const;

const workbookTableWrapStyle = {
  overflowX: "auto",
  border: `1px solid ${designTokens.color.neutral[200]}`,
  borderRadius: 8,
  background: designTokens.color.neutral[50],
} as const;

const workbookTableStyle = {
  width: "100%",
  minWidth: 640,
  borderCollapse: "collapse",
  color: designTokens.color.neutral[700],
  fontSize: 13,
} as const;

const workbookHeaderCellStyle = {
  padding: "8px 10px",
  borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.neutral[100],
  color: designTokens.color.neutral[600],
  fontWeight: 600,
  textAlign: "left",
} as const;

const workbookCellStyle = {
  padding: "8px 10px",
  borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
  verticalAlign: "top",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
} as const;

type ComparisonMonthStatus = {
  key: string;
  reportMonth: string;
  status: string;
};

type WorkbookMetaLine = {
  label: string;
  value: string;
};

function parseOptionalThreshold(value: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readComparisonMonthStatuses(filters: Record<string, unknown> | undefined): ComparisonMonthStatus[] {
  const comparisonMonths = filters?.comparison_months;
  if (!isPlainRecord(comparisonMonths)) {
    return [];
  }

  return Object.entries(comparisonMonths).flatMap(([key, value]) => {
    if (!isPlainRecord(value)) {
      return [];
    }
    const reportMonth = typeof value.report_month === "string" ? value.report_month : "";
    const status = typeof value.status === "string" ? value.status : "";
    if (!reportMonth && !status) {
      return [];
    }
    return [
      {
        key,
        reportMonth: reportMonth || "missing",
        status: status || "unknown",
      },
    ];
  });
}

function readLatestReportMonth(reportMonths: string[]) {
  return reportMonths.reduce((latest, reportMonth) => (reportMonth > latest ? reportMonth : latest), "");
}

function readWorkbookMetaLines(meta: ResultMeta | undefined): WorkbookMetaLine[] {
  if (!meta) {
    return [];
  }

  const metaEntries: Array<[string, string | number | boolean | null | undefined]> = [
    ["basis", meta.basis],
    ["formal_use_allowed", meta.formal_use_allowed],
    ["result_kind", meta.result_kind],
    ["scenario_flag", meta.scenario_flag],
    ["quality_flag", meta.quality_flag],
    ["vendor_status", meta.vendor_status],
    ["fallback_mode", meta.fallback_mode],
    ["fallback_date", meta.fallback_date],
    ["as_of_date", meta.as_of_date],
    ["requested_report_date", meta.requested_report_date],
    ["resolved_report_date", meta.resolved_report_date],
    ["date_basis", meta.date_basis],
    ["source_version", meta.source_version],
    ["vendor_version", meta.vendor_version],
    ["rule_version", meta.rule_version],
    ["cache_version", meta.cache_version],
    ["evidence_rows", meta.evidence_rows],
    ["trace_id", meta.trace_id],
    ["generated_at", meta.generated_at],
  ];

  return metaEntries.flatMap(([label, value]) => {
    if (value === undefined || value === null || value === "") {
      return [];
    }
    return [{ label, value: String(value) }];
  });
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}

function formatActionErrorMessage(error: unknown) {
  const message = errorMessage(error);
  const requestFailure = /^Request failed: .+ \((\d{3})\)$/.exec(message);
  if (requestFailure?.[1]) {
    return `请求失败（${requestFailure[1]}），请稍后重试或检查服务状态。`;
  }
  return message;
}

function errorReason(error: unknown) {
  return error instanceof Error ? error.name : "Error";
}

function formatWorkbookCell(value: unknown) {
  if (value === null || value === undefined) {
    return "--";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : "--";
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed || "--";
  }
  if (typeof value === "boolean") {
    return String(value);
  }

  try {
    const serialized = JSON.stringify(value);
    return serialized || "--";
  } catch {
    return String(value);
  }
}

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

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
  testId?: string;
}) {
  return (
    <div data-testid={props.testId} style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
  );
}

function StatusPanel(props: { testId: string; children: ReactNode }) {
  return (
    <div data-testid={props.testId} style={statusPanelStyle}>
      {props.children}
    </div>
  );
}

export default function MonthlyOperatingAnalysisBranch() {
  const client = useApiClient();
  const [selectedMonth, setSelectedMonth] = useState("");
  const [refreshPayload, setRefreshPayload] = useState<QdbGlMonthlyAnalysisRefreshPayload | null>(null);
  const [scenarioWarn, setScenarioWarn] = useState("6");
  const [scenarioAlert, setScenarioAlert] = useState("12");
  const [scenarioCritical, setScenarioCritical] = useState("18");
  const [scenarioSummary, setScenarioSummary] = useState<string | null>(null);
  const [scenarioError, setScenarioError] = useState<string | null>(null);
  const [workbookExportError, setWorkbookExportError] = useState<string | null>(null);
  const [isRefreshingAnalysis, setIsRefreshingAnalysis] = useState(false);
  const [isApplyingScenario, setIsApplyingScenario] = useState(false);
  const [isExportingWorkbook, setIsExportingWorkbook] = useState(false);
  const [displayedSheets, setDisplayedSheets] = useState<QdbGlMonthlyAnalysisSheet[]>([]);
  const [displayedWorkbookMeta, setDisplayedWorkbookMeta] = useState<ResultMeta | undefined>(undefined);
  const [displayedWorkbookMonth, setDisplayedWorkbookMonth] = useState("");
  const selectedMonthRef = useRef("");
  selectedMonthRef.current = selectedMonth;

  const datesQuery = useQuery({
    queryKey: ["monthly-operating-analysis", "dates", client.mode],
    queryFn: () => client.getQdbGlMonthlyAnalysisDates(),
    retry: false,
  });

  useEffect(() => {
    const latestReportMonth = readLatestReportMonth(datesQuery.data?.result.report_months ?? []);
    if (!selectedMonth && latestReportMonth) {
      setSelectedMonth(latestReportMonth);
    }
  }, [datesQuery.data, selectedMonth]);

  const workbookQuery = useQuery({
    queryKey: ["monthly-operating-analysis", "workbook", client.mode, selectedMonth],
    queryFn: () =>
      client.getQdbGlMonthlyAnalysisWorkbook({
        reportMonth: selectedMonth,
      }),
    enabled: Boolean(selectedMonth),
    retry: false,
  });

  useEffect(() => {
    setRefreshPayload(null);
    setScenarioSummary(null);
    setScenarioError(null);
    setWorkbookExportError(null);
    setIsRefreshingAnalysis(false);
    setIsApplyingScenario(false);
    setIsExportingWorkbook(false);
    setDisplayedSheets([]);
    setDisplayedWorkbookMeta(undefined);
    setDisplayedWorkbookMonth("");
  }, [selectedMonth]);

  useEffect(() => {
    if (workbookQuery.data?.result.sheets) {
      setDisplayedWorkbookMonth(workbookQuery.data.result.report_month);
      setDisplayedSheets(workbookQuery.data.result.sheets);
      setDisplayedWorkbookMeta(workbookQuery.data.result_meta);
    }
  }, [workbookQuery.data]);

  const displayedSheetsForSelectedMonth =
    displayedWorkbookMonth === selectedMonth ? displayedSheets : [];
  const displayedWorkbookMetaForSelectedMonth =
    displayedWorkbookMonth === selectedMonth ? displayedWorkbookMeta : undefined;
  const comparisonMonthStatuses = readComparisonMonthStatuses(
    displayedWorkbookMetaForSelectedMonth?.filters_applied,
  );
  const workbookMetaLines = readWorkbookMetaLines(displayedWorkbookMetaForSelectedMonth);
  const refreshComparisonMonthStatuses = readComparisonMonthStatuses(
    refreshPayload?.comparison_months ? { comparison_months: refreshPayload.comparison_months } : undefined,
  );
  const reportMonths = datesQuery.data?.result.report_months ?? [];
  const hasReportMonths = reportMonths.length > 0;
  const showDatesEmpty = datesQuery.isSuccess && !hasReportMonths;
  const showWorkbookError = workbookQuery.isError;
  const showWorkbookLoading =
    Boolean(selectedMonth) && workbookQuery.isPending && displayedSheetsForSelectedMonth.length === 0;
  const showWorkbookEmpty =
    workbookQuery.isSuccess && Boolean(selectedMonth) && displayedSheetsForSelectedMonth.length === 0;
  const showWorkbookSheets = !showWorkbookError && displayedSheetsForSelectedMonth.length > 0;
  const canRunMonthlyOperatingAnalysisAction = Boolean(selectedMonth);
  const auditLinkHref = selectedMonth
    ? `/product-category-pnl/audit?branch=monthly_operating_analysis&report_month=${encodeURIComponent(selectedMonth)}`
    : "/product-category-pnl/audit?branch=monthly_operating_analysis";

  async function handleRefresh() {
    const actionMonth = selectedMonth;
    if (!actionMonth || isRefreshingAnalysis) {
      return;
    }

    setIsRefreshingAnalysis(true);
    try {
      const payload = await runPollingTask({
        start: () => client.refreshQdbGlMonthlyAnalysis({ reportMonth: actionMonth }),
        getStatus: (runId) => client.getQdbGlMonthlyAnalysisRefreshStatus(runId),
      });
      if (selectedMonthRef.current !== actionMonth) {
        return;
      }
      setRefreshPayload(payload);
      if (payload.status === "failed") {
        return;
      }
      const refreshed = await workbookQuery.refetch();
      if (selectedMonthRef.current !== actionMonth) {
        return;
      }
      if (refreshed.data?.result.sheets) {
        setDisplayedWorkbookMonth(refreshed.data.result.report_month);
        setDisplayedSheets(refreshed.data.result.sheets);
        setDisplayedWorkbookMeta(refreshed.data.result_meta);
      }
    } catch (error) {
      if (selectedMonthRef.current !== actionMonth) {
        return;
      }
      setRefreshPayload({
        status: "failed",
        run_id: `qdb_gl_monthly_analysis:${actionMonth}`,
        job_name: "qdb_gl_monthly_analysis",
        trigger_mode: "error",
        report_month: actionMonth,
        failure_category: "qdb_gl_monthly_analysis_refresh",
        failure_reason: errorReason(error),
        error_message: formatActionErrorMessage(error),
      });
    } finally {
      if (selectedMonthRef.current === actionMonth) {
        setIsRefreshingAnalysis(false);
      }
    }
  }

  async function handleWorkbookExport() {
    const actionMonth = selectedMonth;
    if (!actionMonth) {
      return;
    }

    setWorkbookExportError(null);
    setIsExportingWorkbook(true);
    try {
      const payload = await client.exportQdbGlMonthlyAnalysisWorkbookXlsx({ reportMonth: actionMonth });
      if (selectedMonthRef.current !== actionMonth) {
        return;
      }
      downloadBlobFile(payload.filename, payload.content);
    } catch (error) {
      if (selectedMonthRef.current !== actionMonth) {
        return;
      }
      setWorkbookExportError(formatActionErrorMessage(error));
    } finally {
      if (selectedMonthRef.current === actionMonth) {
        setIsExportingWorkbook(false);
      }
    }
  }

  async function handleApplyScenario() {
    const actionMonth = selectedMonth;
    if (!actionMonth || isApplyingScenario) {
      return;
    }

    setIsApplyingScenario(true);
    setScenarioError(null);
    setScenarioSummary(null);
    try {
      const payload = await client.getQdbGlMonthlyAnalysisScenario({
        reportMonth: actionMonth,
        scenarioName: "threshold-stress",
        deviationWarn: parseOptionalThreshold(scenarioWarn),
        deviationAlert: parseOptionalThreshold(scenarioAlert),
        deviationCritical: parseOptionalThreshold(scenarioCritical),
      });
      if (selectedMonthRef.current !== actionMonth) {
        return;
      }
      setDisplayedWorkbookMonth(payload.result.report_month);
      setDisplayedSheets(payload.result.sheets);
      setDisplayedWorkbookMeta(payload.result_meta);
      setScenarioSummary(
        `${payload.result.scenario_name}: ${Object.keys(payload.result.applied_overrides).join(", ") || "无情景覆盖项"}`,
      );
    } catch (error) {
      if (selectedMonthRef.current !== actionMonth) {
        return;
      }
      setScenarioError(formatActionErrorMessage(error));
    } finally {
      if (selectedMonthRef.current === actionMonth) {
        setIsApplyingScenario(false);
      }
    }
  }

  return (
    <section data-testid="monthly-operating-analysis-branch">
      <div style={pageHeaderStyle}>
        <div>
          <h1 data-testid="monthly-operating-analysis-page-title" style={{ margin: 0, fontSize: 28, fontWeight: 700 }}>月度经营分析</h1>
          <p
            data-testid="monthly-operating-analysis-boundary-copy"
            style={{ marginTop: 8, marginBottom: 0, color: designTokens.color.neutral[600], fontSize: 14 }}
          >
            基于总账对账与日均月度配对文件重建月度经营分析工作簿。
          </p>
          <p style={{ marginTop: 8, marginBottom: 0, color: designTokens.color.neutral[600], fontSize: 12 }}>
            仅用于分析口径工作簿：阈值情景只预览工作表，不替换正式产品分类结果。
          </p>
        </div>
        <div style={{ display: "grid", gap: 10, justifyItems: "end" }}>
          <span
            style={{
              ...chipTypography,
              background:
                client.mode === "real" ? designTokens.color.success[50] : designTokens.color.primary[50],
              color:
                client.mode === "real"
                  ? displayTokens.apiMode.realForeground
                  : displayTokens.apiMode.mockForeground,
            }}
          >
            {client.mode === "real" ? "正式只读链路" : "本地离线契约回放"}
          </span>
          <label style={{ display: "grid", gap: 8 }}>
            报告月份
            <select
              data-testid="monthly-operating-analysis-month-select"
              value={selectedMonth}
              onChange={(event) => setSelectedMonth(event.target.value)}
            >
              {reportMonths.map((reportMonth) => (
                <option key={reportMonth} value={reportMonth}>
                  {reportMonth}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <SectionLead
        eyebrow="控制项"
        title="月度工作簿控制"
        description="报告月份驱动分析口径工作簿；刷新和审计入口沿用既有任务与审计链路。"
        testId="monthly-operating-analysis-controls-lead"
      />
      {datesQuery.isError ? (
        <StatusPanel testId="monthly-operating-analysis-dates-error">
          报告月份加载失败：{errorMessage(datesQuery.error)}
        </StatusPanel>
      ) : null}
      {showDatesEmpty ? (
        <StatusPanel testId="monthly-operating-analysis-dates-empty">
          当前没有可用报告月份，无法加载月度经营分析工作表。
        </StatusPanel>
      ) : null}
      <FilterBar style={{ marginBottom: 16 }}>
        <button
          type="button"
          data-testid="monthly-operating-analysis-refresh-button"
          disabled={!canRunMonthlyOperatingAnalysisAction || isRefreshingAnalysis}
          onClick={() => void handleRefresh()}
        >
          {isRefreshingAnalysis ? "正在刷新月度经营分析" : "刷新月度经营分析"}
        </button>
        <button
          type="button"
          data-testid="monthly-operating-analysis-export-workbook"
          disabled={!canRunMonthlyOperatingAnalysisAction || isExportingWorkbook}
          onClick={() => void handleWorkbookExport()}
        >
          {isExportingWorkbook ? "正在导出工作簿" : "导出工作簿"}
        </button>
        <a
          data-testid="monthly-operating-analysis-audit-link"
          href={auditLinkHref}
        >
          查看调整审计
        </a>
        <label style={{ display: "grid", gap: 6 }}>
          偏离预警阈值
          <input
            data-testid="monthly-operating-analysis-scenario-warn"
            value={scenarioWarn}
            onChange={(event) => setScenarioWarn(event.target.value)}
          />
        </label>
        <label style={{ display: "grid", gap: 6 }}>
          偏离告警阈值
          <input
            data-testid="monthly-operating-analysis-scenario-alert"
            value={scenarioAlert}
            onChange={(event) => setScenarioAlert(event.target.value)}
          />
        </label>
        <label style={{ display: "grid", gap: 6 }}>
          偏离严重阈值
          <input
            data-testid="monthly-operating-analysis-scenario-critical"
            value={scenarioCritical}
            onChange={(event) => setScenarioCritical(event.target.value)}
          />
        </label>
        <button
          type="button"
          data-testid="monthly-operating-analysis-apply-scenario"
          disabled={!canRunMonthlyOperatingAnalysisAction || isApplyingScenario}
          onClick={() => void handleApplyScenario()}
        >
          {isApplyingScenario ? "正在应用情景" : "应用情景"}
        </button>
      </FilterBar>

      {refreshPayload ? (
        <StatusPanel testId="monthly-operating-analysis-refresh-status">
          <strong>refresh {refreshPayload.status}</strong>
          <div style={statusLineWrapStyle}>
            <span style={statusLineStyle}>{refreshPayload.run_id}</span>
            {refreshPayload.report_date ? (
              <span style={statusLineStyle}>report_date={refreshPayload.report_date}</span>
            ) : null}
            {refreshPayload.source_version ? (
              <span style={statusLineStyle}>source_version={refreshPayload.source_version}</span>
            ) : null}
            {refreshPayload.sheet_count === undefined ? null : (
              <span style={statusLineStyle}>sheet_count={refreshPayload.sheet_count}</span>
            )}
            {refreshPayload.evidence_rows === undefined ? null : (
              <span style={statusLineStyle}>evidence_rows={refreshPayload.evidence_rows}</span>
            )}
            {refreshPayload.failure_category ? (
              <span style={statusLineStyle}>failure_category={refreshPayload.failure_category}</span>
            ) : null}
            {refreshPayload.failure_reason ? (
              <span style={statusLineStyle}>failure_reason={refreshPayload.failure_reason}</span>
            ) : null}
            {refreshPayload.error_message ? (
              <span style={statusLineStyle}>error_message={refreshPayload.error_message}</span>
            ) : null}
          </div>
          {refreshComparisonMonthStatuses.length > 0 ? (
            <div style={statusLineWrapStyle}>
              {refreshComparisonMonthStatuses.map((item) => (
                <span key={item.key} style={statusLineStyle}>
                  {item.key} {item.reportMonth} {item.status}
                </span>
              ))}
            </div>
          ) : null}
        </StatusPanel>
      ) : null}

      {scenarioSummary ? (
        <div
          data-testid="monthly-operating-analysis-scenario-summary"
          style={{ marginBottom: 12, color: designTokens.color.neutral[900], fontSize: 13 }}
        >
          {scenarioSummary}
        </div>
      ) : null}
      {scenarioError ? (
        <StatusPanel testId="monthly-operating-analysis-scenario-error">
          情景应用失败：{scenarioError}
        </StatusPanel>
      ) : null}
      {workbookExportError ? (
        <StatusPanel testId="monthly-operating-analysis-workbook-export-error">
          工作簿导出失败：{workbookExportError}
        </StatusPanel>
      ) : null}

      <SectionLead
        eyebrow="工作簿"
        title="月度经营分析工作表"
        description="下方工作表继续展示后端返回的工作表；情景只替换当前展示的分析口径工作表。"
        testId="monthly-operating-analysis-workbook-lead"
      />
      {showWorkbookLoading ? (
        <StatusPanel testId="monthly-operating-analysis-workbook-loading">
          正在加载 {selectedMonth} 月度经营分析工作簿。
        </StatusPanel>
      ) : null}
      {showWorkbookError ? (
        <StatusPanel testId="monthly-operating-analysis-workbook-error">
          工作表加载失败：{errorMessage(workbookQuery.error)}
        </StatusPanel>
      ) : null}
      {workbookMetaLines.length > 0 ? (
        <StatusPanel testId="monthly-operating-analysis-workbook-meta">
          <strong>result_meta</strong>
          <div style={statusLineWrapStyle}>
            {workbookMetaLines.map((item) => (
              <span key={item.label} style={statusLineStyle}>
                {item.label}={item.value}
              </span>
            ))}
          </div>
        </StatusPanel>
      ) : null}
      {comparisonMonthStatuses.length > 0 ? (
        <StatusPanel testId="monthly-operating-analysis-comparison-status">
          <strong>comparison_months</strong>
          <div style={statusLineWrapStyle}>
            {comparisonMonthStatuses.map((item) => (
              <span key={item.key} style={statusLineStyle}>
                {item.key} {item.reportMonth} {item.status}
              </span>
            ))}
          </div>
        </StatusPanel>
      ) : null}
      {showWorkbookEmpty ? (
        <StatusPanel testId="monthly-operating-analysis-empty-workbook">
          当前报告月份没有工作表数据。
        </StatusPanel>
      ) : null}

      <div style={{ display: "grid", gap: 12 }}>
        {showWorkbookSheets ? displayedSheetsForSelectedMonth.map((sheet) => (
          <section
            key={sheet.key}
            data-testid={`monthly-operating-analysis-section-${sheet.key}`}
            style={{
              padding: 16,
              borderRadius: 16,
              border: `1px solid ${designTokens.color.neutral[200]}`,
              background: designTokens.color.neutral[50],
            }}
          >
            <h2 style={{ marginTop: 0 }}>{sheet.title}</h2>
            {sheet.rows.length > 0 ? (
              <div style={workbookTableWrapStyle}>
                <table style={workbookTableStyle}>
                  <thead>
                    <tr>
                      {sheet.columns.map((column) => (
                        <th key={column} scope="col" style={workbookHeaderCellStyle}>
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sheet.rows.map((row, rowIndex) => (
                      <tr key={rowIndex}>
                        {sheet.columns.map((column) => (
                          <td key={column} style={workbookCellStyle}>
                            {formatWorkbookCell(row[column])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div
                data-testid={`monthly-operating-analysis-empty-state-${sheet.key}`}
                style={{ color: designTokens.color.neutral[500], fontSize: 13 }}
              >
                当前没有可展示数据。
              </div>
            )}
          </section>
        )) : null}
      </div>
    </section>
  );
}
