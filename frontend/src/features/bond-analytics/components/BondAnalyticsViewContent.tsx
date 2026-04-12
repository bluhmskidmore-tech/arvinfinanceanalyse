import { Suspense, lazy, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ActionAttributionResponse, PeriodType } from "../types";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { buildBondAnalyticsOverviewModel } from "../lib/bondAnalyticsOverviewModel";
import { bondAnalyticsQueryKeyRoot } from "../lib/bondAnalyticsQueryKeys";
import { useApiClient } from "../../../api/client";
import { runPollingTask } from "../../../app/jobs/polling";

const BondAnalyticsOverviewPanels = lazy(() => import("./BondAnalyticsOverviewPanels"));

const BondAnalyticsDetailSection = lazy(() =>
  import("./BondAnalyticsDetailSection").then((module) => ({
    default: module.BondAnalyticsDetailSection,
  })),
);

function generateRecentDates(): { value: string; label: string }[] {
  const dates: { value: string; label: string }[] = [];
  const now = new Date();

  for (let i = 1; i <= 12; i += 1) {
    const date = new Date(now.getFullYear(), now.getMonth() - i + 1, 0);
    const value = date.toISOString().slice(0, 10);
    dates.push({
      value,
      label: value,
    });
  }

  return dates;
}

export function BondAnalyticsViewContent() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const dateOptions = useMemo(() => generateRecentDates(), []);
  const [reportDate, setReportDate] = useState(dateOptions[0]?.value ?? "");
  const [periodType, setPeriodType] = useState<PeriodType>("MoM");
  const [activeTab, setActiveTab] =
    useState<BondAnalyticsModuleKey>("return-decomposition");
  const [isBondAnalyticsRefreshing, setIsBondAnalyticsRefreshing] = useState(false);
  const [bondAnalyticsRefreshError, setBondAnalyticsRefreshError] = useState<string | null>(
    null,
  );
  const [lastBondAnalyticsRefreshRunId, setLastBondAnalyticsRefreshRunId] = useState<
    string | null
  >(null);
  const [detailRemountKey, setDetailRemountKey] = useState(0);

  const actionAttributionQuery = useQuery({
    queryKey: [
      ...bondAnalyticsQueryKeyRoot,
      "overview-action-attribution",
      reportDate,
      periodType,
    ],
    queryFn: async (): Promise<ActionAttributionResponse> => {
      const params = new URLSearchParams({
        report_date: reportDate,
        period_type: periodType,
      });
      const response = await fetch(
        `/api/bond-analytics/action-attribution?${params.toString()}`,
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const json = await response.json();
      return json.result as ActionAttributionResponse;
    },
    enabled: Boolean(reportDate),
    retry: false,
  });

  const actionAttributionErrorMessage =
    actionAttributionQuery.error instanceof Error
      ? actionAttributionQuery.error.message
      : null;

  async function handleBondAnalyticsRefresh() {
    if (!reportDate) {
      return;
    }
    setIsBondAnalyticsRefreshing(true);
    setBondAnalyticsRefreshError(null);
    try {
      const payload = await runPollingTask({
        start: () => client.refreshBondAnalytics(reportDate),
        getStatus: (runId) => client.getBondAnalyticsRefreshStatus(runId),
        onUpdate: (nextPayload) => {
          if (nextPayload.run_id) {
            setLastBondAnalyticsRefreshRunId(nextPayload.run_id);
          }
        },
      });
      if (payload.status !== "completed") {
        const hint =
          typeof payload.error_message === "string" && payload.error_message.trim()
            ? payload.error_message
            : `债券分析刷新未完成：${payload.status}`;
        const rid = payload.run_id ? ` run_id: ${payload.run_id}` : "";
        throw new Error(`${hint}${rid}`);
      }
      await queryClient.invalidateQueries({ queryKey: [...bondAnalyticsQueryKeyRoot] });
      setDetailRemountKey((key) => key + 1);
    } catch (error: unknown) {
      setBondAnalyticsRefreshError(
        error instanceof Error ? error.message : "刷新债券分析失败",
      );
    } finally {
      setIsBondAnalyticsRefreshing(false);
    }
  }

  const overviewModel = buildBondAnalyticsOverviewModel({
    reportDate,
    periodType,
    actionAttribution: actionAttributionQuery.data ?? null,
    actionAttributionLoading: actionAttributionQuery.isFetching,
    actionAttributionError: actionAttributionErrorMessage,
  });

  return (
    <div
      style={{ display: "flex", flexDirection: "column", gap: 16 }}
      data-testid="bond-analysis-overview"
    >
      <Suspense
        fallback={
          <div style={{ color: "#8090a8", fontSize: 13 }} data-testid="bond-analysis-overview-loading">
            Loading overview...
          </div>
        }
      >
        <BondAnalyticsOverviewPanels
          dateOptions={dateOptions}
          reportDate={reportDate}
          onReportDateChange={setReportDate}
          periodType={periodType}
          onPeriodTypeChange={setPeriodType}
          overviewModel={overviewModel}
          onOpenModuleDetail={setActiveTab}
          onRefreshAnalytics={() => void handleBondAnalyticsRefresh()}
          isAnalyticsRefreshing={isBondAnalyticsRefreshing}
          analyticsRefreshError={bondAnalyticsRefreshError}
          lastAnalyticsRefreshRunId={lastBondAnalyticsRefreshRunId}
        />
      </Suspense>

      <section
        style={{ display: "flex", flexDirection: "column", gap: 12 }}
      >
        <Suspense
          fallback={
            <div style={{ color: "#8090a8", fontSize: 13 }} data-testid="bond-analysis-detail-loading">
              Loading detail module...
            </div>
          }
        >
          <div key={detailRemountKey}>
            <BondAnalyticsDetailSection
              activeTab={activeTab}
              onActiveTabChange={setActiveTab}
              reportDate={reportDate}
              periodType={periodType}
            />
          </div>
        </Suspense>
      </section>
    </div>
  );
}

export default BondAnalyticsViewContent;
