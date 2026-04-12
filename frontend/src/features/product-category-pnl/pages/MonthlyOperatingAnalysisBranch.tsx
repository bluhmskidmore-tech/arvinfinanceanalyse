import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { runPollingTask } from "../../../app/jobs/polling";
import { useApiClient } from "../../../api/client";
import type { QdbGlMonthlyAnalysisSheet } from "../../../api/contracts";

function parseOptionalThreshold(value: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
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
      `${payload.result.scenario_name}: ${Object.keys(payload.result.applied_overrides).join(", ") || "no overrides"}`,
    );
  }

  return (
    <section data-testid="monthly-operating-analysis-branch">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 16,
          padding: 20,
          borderRadius: 18,
          border: "1px solid #d7dfea",
          background: "#fbfcfe",
          marginBottom: 18,
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700 }}>Monthly Operating Analysis</h1>
          <p style={{ marginTop: 8, marginBottom: 0, color: "#5c6b82", fontSize: 14 }}>
            Analytical workbook rebuilt from the QDB GL ledger reconciliation and daily average month pair.
          </p>
        </div>
        <label style={{ display: "grid", gap: 8 }}>
          Report Month
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

      <div
        style={{
          display: "flex",
          gap: 12,
          alignItems: "end",
          marginBottom: 16,
          flexWrap: "wrap",
        }}
      >
        <button
          type="button"
          data-testid="monthly-operating-analysis-refresh-button"
          onClick={() => void handleRefresh()}
        >
          Refresh Analysis
        </button>
        <a
          data-testid="monthly-operating-analysis-audit-link"
          href="/product-category-pnl/audit?branch=monthly_operating_analysis"
        >
          Open Audit
        </a>
        <label style={{ display: "grid", gap: 6 }}>
          Warn
          <input
            data-testid="monthly-operating-analysis-scenario-warn"
            value={scenarioWarn}
            onChange={(event) => setScenarioWarn(event.target.value)}
          />
        </label>
        <label style={{ display: "grid", gap: 6 }}>
          Alert
          <input
            data-testid="monthly-operating-analysis-scenario-alert"
            value={scenarioAlert}
            onChange={(event) => setScenarioAlert(event.target.value)}
          />
        </label>
        <label style={{ display: "grid", gap: 6 }}>
          Critical
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
          Apply Scenario
        </button>
      </div>

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
              <div style={{ color: "#8090a8", fontSize: 13 }}>No data in the current sheet.</div>
            )}
          </section>
        ))}
      </div>
    </section>
  );
}
