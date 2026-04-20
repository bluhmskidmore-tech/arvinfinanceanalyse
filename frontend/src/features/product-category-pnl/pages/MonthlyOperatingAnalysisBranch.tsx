import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import type { QdbGlMonthlyAnalysisSheet } from "../../../api/contracts";

const pageHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: 16,
  padding: 20,
  borderRadius: 18,
  border: "1px solid #d7dfea",
  background: "#fbfcfe",
  marginBottom: 18,
} as const;

const modeBadgeStyle = {
  display: "inline-flex",
  alignItems: "center",
  padding: "8px 12px",
  borderRadius: 999,
  background: "#edf3ff",
  color: "#1f5eff",
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
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
  maxWidth: 900,
  color: "#5c6b82",
  fontSize: 13,
  lineHeight: 1.7,
} as const;

function parseOptionalThreshold(value: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
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

export default function MonthlyOperatingAnalysisBranch() {
  const client = useApiClient();
  const [selectedMonth, setSelectedMonth] = useState("");
  const [refreshRunId, setRefreshRunId] = useState<string | null>(null);
  const [scenarioWarn, setScenarioWarn] = useState("6");
  const [scenarioAlert, setScenarioAlert] = useState("12");
  const [scenarioCritical, setScenarioCritical] = useState("18");
  const [scenarioSummary, setScenarioSummary] = useState<string | null>(null);
  const [displayedSheets, setDisplayedSheets] = useState<QdbGlMonthlyAnalysisSheet[]>([]);

  const datesQuery = useQuery({
    queryKey: ["monthly-operating-analysis", "dates", client.mode],
    queryFn: () => client.getQdbGlMonthlyAnalysisDates(),
    retry: false,
  });

  useEffect(() => {
    if (!selectedMonth && datesQuery.data?.result.report_months.length) {
      setSelectedMonth(datesQuery.data.result.report_months[0] ?? "");
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
    if (workbookQuery.data?.result.sheets) {
      setDisplayedSheets(workbookQuery.data.result.sheets);
    }
  }, [workbookQuery.data]);

  async function handleRefresh() {
    const payload = await runPollingTask({
      start: () => client.refreshQdbGlMonthlyAnalysis({ reportMonth: selectedMonth }),
      getStatus: (runId) => client.getQdbGlMonthlyAnalysisRefreshStatus(runId),
    });
    setRefreshRunId(payload.run_id);
    const refreshed = await workbookQuery.refetch();
    if (refreshed.data?.result.sheets) {
      setDisplayedSheets(refreshed.data.result.sheets);
    }
  }

  async function handleApplyScenario() {
    const payload = await client.getQdbGlMonthlyAnalysisScenario({
      reportMonth: selectedMonth,
      scenarioName: "threshold-stress",
      deviationWarn: parseOptionalThreshold(scenarioWarn),
      deviationAlert: parseOptionalThreshold(scenarioAlert),
      deviationCritical: parseOptionalThreshold(scenarioCritical),
    });
    setDisplayedSheets(payload.result.sheets);
    setScenarioSummary(
      `${payload.result.scenario_name}: ${Object.keys(payload.result.applied_overrides).join(", ") || "无情景覆盖项"}`,
    );
  }

  return (
    <section data-testid="monthly-operating-analysis-branch">
      <div style={pageHeaderStyle}>
        <div>
          <h1 data-testid="monthly-operating-analysis-page-title" style={{ margin: 0, fontSize: 28, fontWeight: 700 }}>月度经营分析</h1>
          <p data-testid="monthly-operating-analysis-boundary-copy" style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 14 }}>
            基于总账对账与日均月度配对文件重建月度经营分析工作簿。
          </p>
          <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 12 }}>
            Analytical workbook only: threshold scenario changes preview sheets without replacing formal product-category results.
          </p>
        </div>
        <div style={{ display: "grid", gap: 10, justifyItems: "end" }}>
          <span style={modeBadgeStyle}>
            {client.mode === "real" ? "正式只读链路" : "本地离线契约回放"}
          </span>
          <label style={{ display: "grid", gap: 8 }}>
            报告月份
            <select
              data-testid="monthly-operating-analysis-month-select"
              value={selectedMonth}
              onChange={(event) => setSelectedMonth(event.target.value)}
            >
              {(datesQuery.data?.result.report_months ?? []).map((reportMonth) => (
                <option key={reportMonth} value={reportMonth}>
                  {reportMonth}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <SectionLead
        eyebrow="Controls"
        title="月度工作簿控制"
        description="报告月份驱动 analytical workbook；刷新和审计入口沿用既有任务与 audit 链路。"
        testId="monthly-operating-analysis-controls-lead"
      />
      <FilterBar style={{ marginBottom: 16 }}>
        <button
          type="button"
          data-testid="monthly-operating-analysis-refresh-button"
          onClick={() => void handleRefresh()}
        >
          刷新月度经营分析
        </button>
        <a
          data-testid="monthly-operating-analysis-audit-link"
          href="/product-category-pnl/audit?branch=monthly_operating_analysis"
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
          onClick={() => void handleApplyScenario()}
        >
          应用情景
        </button>
      </FilterBar>

      {refreshRunId ? (
        <div style={{ marginBottom: 12, color: "#5c6b82", fontSize: 12 }}>{refreshRunId}</div>
      ) : null}

      {scenarioSummary ? (
        <div
          data-testid="monthly-operating-analysis-scenario-summary"
          style={{ marginBottom: 12, color: "#162033", fontSize: 13 }}
        >
          {scenarioSummary}
        </div>
      ) : null}

      <SectionLead
        eyebrow="Workbook"
        title="月度经营分析工作表"
        description="下方工作表继续展示后端返回的 sheets；scenario 只替换当前展示的 analytical sheets。"
        testId="monthly-operating-analysis-workbook-lead"
      />
      <div style={{ display: "grid", gap: 12 }}>
        {displayedSheets.map((sheet) => (
          <section
            key={sheet.key}
            data-testid={`monthly-operating-analysis-section-${sheet.key}`}
            style={{
              padding: 16,
              borderRadius: 16,
              border: "1px solid #d7dfea",
              background: "#fbfcfe",
            }}
          >
            <h2 style={{ marginTop: 0 }}>{sheet.title}</h2>
            {sheet.rows.length > 0 ? (
              <div style={{ color: "#5c6b82", fontSize: 13 }}>
                {sheet.columns.map((column) => (
                  <span key={column} style={{ marginRight: 12 }}>
                    {column}
                  </span>
                ))}
              </div>
            ) : (
              <div style={{ color: "#8090a8", fontSize: 13 }}>当前没有可展示数据。</div>
            )}
          </section>
        ))}
      </div>
    </section>
  );
}
