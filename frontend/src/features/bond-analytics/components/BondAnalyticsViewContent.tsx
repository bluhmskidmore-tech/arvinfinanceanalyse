import { Suspense, lazy, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ApiEnvelope } from "../../../api/contracts";
import type {
  ActionAttributionResponse,
  BondAnalyticsAccountingClassFilter,
  BondAnalyticsAssetClassFilter,
  BondAnalyticsScenarioSetFilter,
  PeriodType,
} from "../types";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { buildBondAnalyticsOverviewModel } from "../lib/bondAnalyticsOverviewModel";
import { bondAnalyticsQueryKeyRoot } from "../lib/bondAnalyticsQueryKeys";
import { useApiClient } from "../../../api/client";
import { runPollingTask } from "../../../app/jobs/polling";
import { useSearchParams } from "react-router-dom";
import { designTokens } from "../../../theme/designSystem";
import { mapResearchCalendarEventToCalendarItem } from "../../../lib/researchCalendarToCalendarItem";

const BondAnalyticsOverviewPanels = lazy(() => import("./BondAnalyticsOverviewPanels"));

const BondAnalyticsDetailSection = lazy(() =>
  import("./BondAnalyticsDetailSection").then((module) => ({
    default: module.BondAnalyticsDetailSection,
  })),
);

export function BondAnalyticsViewContent() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const explicitReportDate = searchParams.get("report_date")?.trim() || "";
  const datesQuery = useQuery({
    queryKey: [...bondAnalyticsQueryKeyRoot, "dates", client.mode],
    queryFn: () => client.getBondAnalyticsDates(),
    retry: false,
  });
  const dateOptions = useMemo(() => {
    const reportDates = datesQuery.data?.result.report_dates ?? [];
    const options = reportDates.map((value) => ({ value, label: value }));
    if (
      explicitReportDate &&
      !options.some((option) => option.value === explicitReportDate)
    ) {
      return [{ value: explicitReportDate, label: explicitReportDate }, ...options];
    }
    return options;
  }, [datesQuery.data?.result.report_dates, explicitReportDate]);
  const [reportDate, setReportDate] = useState("");
  const [periodType, setPeriodType] = useState<PeriodType>("MoM");
  const [assetClass, setAssetClass] = useState<BondAnalyticsAssetClassFilter>("all");
  const [accountingClass, setAccountingClass] = useState<BondAnalyticsAccountingClassFilter>("all");
  const [scenarioSet, setScenarioSet] = useState<BondAnalyticsScenarioSetFilter>("standard");
  const [spreadScenarios, setSpreadScenarios] = useState("10,25,50");
  const [activeTab, setActiveTab] =
    useState<BondAnalyticsModuleKey>("action-attribution");
  const [isBondAnalyticsRefreshing, setIsBondAnalyticsRefreshing] = useState(false);
  const [bondAnalyticsRefreshError, setBondAnalyticsRefreshError] = useState<string | null>(
    null,
  );
  const [lastBondAnalyticsRefreshRunId, setLastBondAnalyticsRefreshRunId] = useState<
    string | null
  >(null);
  const [detailRemountKey, setDetailRemountKey] = useState(0);

  const resolvedReportDate = useMemo(() => {
    if (explicitReportDate) {
      return explicitReportDate;
    }
    return datesQuery.data?.result.report_dates[0] ?? "";
  }, [datesQuery.data?.result.report_dates, explicitReportDate]);

  const effectiveReportDate = reportDate || resolvedReportDate;
  const datesEmpty =
    !explicitReportDate &&
    !datesQuery.isLoading &&
    !datesQuery.isError &&
    (datesQuery.data?.result.report_dates.length ?? 0) === 0;
  const showDatesErrorState = datesQuery.isError && !effectiveReportDate;

  const actionAttributionQuery = useQuery({
    queryKey: [
      ...bondAnalyticsQueryKeyRoot,
      "overview-action-attribution",
      effectiveReportDate,
      periodType,
    ],
    queryFn: async (): Promise<ApiEnvelope<ActionAttributionResponse>> =>
      client.getBondAnalyticsActionAttribution(effectiveReportDate, periodType),
    enabled: Boolean(effectiveReportDate),
    retry: false,
  });

  const researchCalendarQuery = useQuery({
    queryKey: [
      ...bondAnalyticsQueryKeyRoot,
      "research-calendar",
      effectiveReportDate,
    ],
    queryFn: () => client.getResearchCalendarEvents({ reportDate: effectiveReportDate }),
    enabled: Boolean(effectiveReportDate),
    retry: false,
  });

  const actionAttributionErrorMessage =
    actionAttributionQuery.error instanceof Error
      ? actionAttributionQuery.error.message
      : null;

  async function handleBondAnalyticsRefresh() {
    if (!effectiveReportDate) {
      return;
    }
    setIsBondAnalyticsRefreshing(true);
    setBondAnalyticsRefreshError(null);
    try {
      const payload = await runPollingTask({
        start: () => client.refreshBondAnalytics(effectiveReportDate),
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
    reportDate: effectiveReportDate,
    periodType,
    activeModuleKey: activeTab,
    actionAttributionEnvelope: actionAttributionQuery.data ?? null,
    actionAttributionLoading: actionAttributionQuery.isFetching,
    actionAttributionError: actionAttributionErrorMessage,
  });

  const calendarItems = useMemo(
    () =>
      (researchCalendarQuery.data ?? [])
        .map(mapResearchCalendarEventToCalendarItem)
        .slice(0, 4),
    [researchCalendarQuery.data],
  );

  if (showDatesErrorState) {
    return (
      <section
        style={{
          padding: designTokens.space[6],
          borderRadius: designTokens.radius.lg,
          background: designTokens.color.primary[50],
          border: `1px solid ${designTokens.color.neutral[200]}`,
          boxShadow: designTokens.shadow.card,
          display: "grid",
          gap: designTokens.space[3],
        }}
      >
        <div style={{ fontSize: designTokens.fontSize[18], fontWeight: 700, color: designTokens.color.neutral[900] }}>
          债券分析日期载入失败。
        </div>
        <div style={{ color: designTokens.color.neutral[700], lineHeight: designTokens.lineHeight.relaxed }}>
          无法确定可用报告日，当前不启动债券分析默认首屏查询。请重试或通过地址栏报告日参数显式传入。
        </div>
        <button
          type="button"
          onClick={() => void datesQuery.refetch()}
          style={{
            width: "fit-content",
            border: `1px solid ${designTokens.color.neutral[300]}`,
            background: designTokens.color.neutral[50],
            borderRadius: designTokens.radius.md,
            padding: `${designTokens.space[2] + 2}px ${designTokens.space[4]}px`,
            color: designTokens.color.neutral[900],
            cursor: "pointer",
          }}
        >
          重试日期载入
        </button>
      </section>
    );
  }

  if (datesEmpty && !effectiveReportDate) {
    return (
      <section
        style={{
          padding: designTokens.space[6],
          borderRadius: designTokens.radius.lg,
          background: designTokens.color.primary[50],
          border: `1px solid ${designTokens.color.neutral[200]}`,
          boxShadow: designTokens.shadow.card,
          display: "grid",
          gap: designTokens.space[3],
        }}
      >
        <div style={{ fontSize: designTokens.fontSize[18], fontWeight: 700, color: designTokens.color.neutral[900] }}>
          债券分析暂无可用报告日。
        </div>
        <div style={{ color: designTokens.color.neutral[700], lineHeight: designTokens.lineHeight.relaxed }}>
          后端尚未返回可消费的债券分析报告日，因此默认首屏保持等待状态，不在前端自行推导日期。
        </div>
        <button
          type="button"
          onClick={() => void datesQuery.refetch()}
          style={{
            width: "fit-content",
            border: `1px solid ${designTokens.color.neutral[300]}`,
            background: designTokens.color.neutral[50],
            borderRadius: designTokens.radius.md,
            padding: `${designTokens.space[2] + 2}px ${designTokens.space[4]}px`,
            color: designTokens.color.neutral[900],
            cursor: "pointer",
          }}
        >
          重试日期载入
        </button>
      </section>
    );
  }

  return (
    <div
      style={{ display: "flex", flexDirection: "column", gap: designTokens.space[4] }}
      data-testid="bond-analysis-overview"
    >
      <Suspense
        fallback={
          <div
            style={{ color: designTokens.color.neutral[600], fontSize: designTokens.fontSize[13] }}
            data-testid="bond-analysis-overview-loading"
          >
            正在加载总览...
          </div>
        }
      >
        <BondAnalyticsOverviewPanels
          dateOptions={dateOptions}
          reportDate={effectiveReportDate}
          onReportDateChange={setReportDate}
          periodType={periodType}
          onPeriodTypeChange={setPeriodType}
          assetClass={assetClass}
          onAssetClassChange={setAssetClass}
          accountingClass={accountingClass}
          onAccountingClassChange={setAccountingClass}
          scenarioSet={scenarioSet}
          onScenarioSetChange={setScenarioSet}
          spreadScenarios={spreadScenarios}
          onSpreadScenariosChange={setSpreadScenarios}
          actionAttributionResult={actionAttributionQuery.data?.result ?? null}
          overviewModel={overviewModel}
          onOpenModuleDetail={setActiveTab}
          onRefreshAnalytics={() => void handleBondAnalyticsRefresh()}
          isAnalyticsRefreshing={isBondAnalyticsRefreshing}
          analyticsRefreshError={bondAnalyticsRefreshError}
          lastAnalyticsRefreshRunId={lastBondAnalyticsRefreshRunId}
          calendarItems={calendarItems}
        />
      </Suspense>
      <section
        style={{ display: "flex", flexDirection: "column", gap: designTokens.space[3] }}
      >
        <Suspense
          fallback={
            <div
              style={{ color: designTokens.color.neutral[600], fontSize: designTokens.fontSize[13] }}
              data-testid="bond-analysis-detail-loading"
            >
              正在加载明细模块...
            </div>
          }
        >
          <div key={detailRemountKey}>
            <BondAnalyticsDetailSection
              activeTab={activeTab}
              onActiveTabChange={setActiveTab}
              reportDate={effectiveReportDate}
              periodType={periodType}
              assetClass={assetClass}
              accountingClass={accountingClass}
              scenarioSet={scenarioSet}
              spreadScenarios={spreadScenarios}
            />
          </div>
        </Suspense>
      </section>

    </div>
  );
}

export default BondAnalyticsViewContent;
