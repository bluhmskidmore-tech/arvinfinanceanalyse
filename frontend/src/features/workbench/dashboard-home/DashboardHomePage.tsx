import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiQueryKeys } from "../../../api/queryKeys";
import { sanitizeMetricCopy } from "../../executive-dashboard/lib/sanitizeMetricCopy";
import { useDashboardData } from "../dashboard/hooks/useDashboardData";
import { todayIsoDate } from "../pages/dashboardPageHelpers";
import { useDashboardSnapshotBoundary } from "../pages/useDashboardSnapshotBoundary";
import styles from "./dashboardHome.module.css";
import { mapToHomeView } from "./dashboardHomeView";
import { DashboardHomeToolbar } from "./sections/DashboardHomeToolbar";
import { DecisionRailSection } from "./sections/DecisionRailSection";
import { TerminalHomeContent } from "./TerminalHomeContent";

export default function DashboardHomePage() {
  const [reportDate, setReportDate] = useState("");
  const [toolbarSearch, setToolbarSearch] = useState("");
  const [allowPartial, setAllowPartial] = useState(false);

  const {
    dataClient,
    snapshotQuery,
    isLiveDataFallback,
    adapterOutput,
    snapshotResult,
    snapshotMeta,
    initialEffectiveReportDate,
    supplementalReportDate,
    reportDateDataWarning,
    refreshSnapshot,
  } = useDashboardSnapshotBoundary({
    reportDate,
    allowPartial,
  });

  const useMockFallback = dataClient.mode !== "real" || isLiveDataFallback;

  const {
    coreMetricsQuery,
    dailyChangesQuery,
    marketRatesQuery,
    bondHeadlineQuery,
    portfolioHeadlinesQuery,
    portfolioComparisonQuery,
    creditSpreadMigrationQuery,
    returnDecompositionQuery,
    campisiFourEffectsQuery,
    yieldCurveTermStructureQuery,
    decisionItemsQuery,
    researchCalendarQuery,
    macroNewsQueries,
    calendarStartDate,
    calendarEndDate,
  } = useDashboardData({
    dataClient,
    supplementalReportDate,
    effectiveReportDate: initialEffectiveReportDate,
    loadCalendarData: true,
    loadBondBucketYieldData: false,
    loadBondBucketMonthlyData: false,
    loadPortfolioSupplementData: true,
    loadDecisionItemsData: Boolean(initialEffectiveReportDate),
  });

  const hasSupplementalReportDate = Boolean(supplementalReportDate);

  const assetStructureQuery = useQuery({
    queryKey: apiQueryKeys.bondDashboardAssetStructure(
      dataClient.mode,
      supplementalReportDate,
      "bond_type",
    ),
    queryFn: () => dataClient.getBondDashboardAssetStructure(supplementalReportDate ?? "", "bond_type"),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate,
  });

  const ratingStructureQuery = useQuery({
    queryKey: apiQueryKeys.bondDashboardAssetStructure(
      dataClient.mode,
      supplementalReportDate,
      "rating",
    ),
    queryFn: () => dataClient.getBondDashboardAssetStructure(supplementalReportDate ?? "", "rating"),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate,
  });

  const maturityStructureQuery = useQuery({
    queryKey: apiQueryKeys.bondDashboardMaturityStructure(dataClient.mode, supplementalReportDate),
    queryFn: () => dataClient.getBondDashboardMaturityStructure(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate,
  });

  const industryDistributionQuery = useQuery({
    queryKey: apiQueryKeys.bondDashboardIndustryDistribution(dataClient.mode, supplementalReportDate),
    queryFn: () => dataClient.getBondDashboardIndustryDistribution(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate,
  });

  const riskIndicatorsQuery = useQuery({
    queryKey: apiQueryKeys.bondDashboardRiskIndicators(dataClient.mode, supplementalReportDate),
    queryFn: () => dataClient.getBondDashboardRiskIndicators(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate,
  });

  const topHoldingsQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsTopHoldings(dataClient.mode, supplementalReportDate, 8),
    queryFn: () => dataClient.getBondAnalyticsTopHoldings(supplementalReportDate ?? "", 8),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate,
  });

  const positionChangesQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsPositionChanges(dataClient.mode, supplementalReportDate, 5),
    queryFn: () => dataClient.getBondAnalyticsPositionChanges(supplementalReportDate ?? "", 5),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate,
  });

  const researchReportsQuery = useQuery({
    queryKey: apiQueryKeys.homeResearchReports(dataClient.mode, supplementalReportDate, 5),
    queryFn: () => dataClient.getHomeResearchReports(supplementalReportDate ?? "", 5),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate,
  });

  const incomeTrendQuery = useQuery({
    queryKey: apiQueryKeys.homeIncomeTrend(dataClient.mode, supplementalReportDate, 7),
    queryFn: () => dataClient.getHomeIncomeTrend(supplementalReportDate ?? "", 7),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate,
  });

  const cockpitWarningsQuery = useQuery({
    queryKey: ["dashboard-home", "cockpit-warnings", dataClient.mode, supplementalReportDate ?? "pending-snapshot"],
    queryFn: () => dataClient.getCockpitWarnings(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate && dataClient.mode === "real",
  });

  const sanitizedMetrics = useMemo(
    () =>
      (adapterOutput.overview.vm?.metrics ?? []).map((metric) => sanitizeMetricCopy(metric)),
    [adapterOutput.overview.vm?.metrics],
  );
  const dashboardTodayIsoDate = useMemo(() => todayIsoDate(), []);
  const macroNewsEvents = useMemo(
    () => macroNewsQueries.flatMap((query) => query.data?.result.events ?? []),
    [macroNewsQueries],
  );
  const macroNewsLoading = macroNewsQueries.some((query) => query.isLoading);
  const macroNewsError = macroNewsQueries.length > 0 && macroNewsQueries.every((query) => query.isError);

  const effectiveReportDate =
    snapshotResult?.report_date?.trim() || initialEffectiveReportDate || reportDate.trim();
  const snapshotUnavailable =
    dataClient.mode === "real" && snapshotQuery.isError && !snapshotResult;
  const snapshotStale =
    dataClient.mode === "real" && Boolean(reportDateDataWarning) && Boolean(snapshotResult);

  const alertCount = useMemo(() => {
    if (useMockFallback) {
      return 3;
    }
    const missing = snapshotResult?.domains_missing?.length ?? 0;
    return missing > 0 ? missing : adapterOutput.verdict?.tone === "warning" ? 1 : 0;
  }, [adapterOutput.verdict?.tone, snapshotResult?.domains_missing?.length, useMockFallback]);

  const view = useMemo(
    () =>
      mapToHomeView({
        reportDate: effectiveReportDate,
        useMockFallback,
        verdict: adapterOutput.verdict,
        metrics: sanitizedMetrics,
        attribution: adapterOutput.attribution.vm,
        coreMetrics: coreMetricsQuery.data?.result ?? null,
        dailyChanges: dailyChangesQuery.data?.result ?? null,
        bondHeadline: bondHeadlineQuery.data?.result ?? null,
        portfolio: portfolioHeadlinesQuery.data?.result ?? null,
        portfolioComparison: portfolioComparisonQuery.data?.result ?? null,
        creditSpreadMigration: creditSpreadMigrationQuery.data?.result ?? null,
        returnDecomposition: returnDecompositionQuery.data?.result ?? null,
        campisiFourEffects: campisiFourEffectsQuery.data?.result ?? null,
        yieldCurveTermStructure: yieldCurveTermStructureQuery.data?.result ?? null,
        decisionItems: decisionItemsQuery.data?.result.rows ?? null,
        marketPoints: marketRatesQuery.data?.result.series ?? null,
        productCategoryYtd: snapshotResult?.product_category_ytd ?? null,
        productCategoryMonthly: snapshotResult?.product_category_monthly ?? null,
        assetStructure: assetStructureQuery.data?.result ?? null,
        ratingStructure: ratingStructureQuery.data?.result ?? null,
        maturityStructure: maturityStructureQuery.data?.result ?? null,
        industryDistribution: industryDistributionQuery.data?.result ?? null,
        riskIndicators: riskIndicatorsQuery.data?.result ?? null,
        topHoldings: topHoldingsQuery.data?.result ?? null,
        topHoldingsLoading: topHoldingsQuery.isLoading,
        topHoldingsError: topHoldingsQuery.isError,
        positionChanges: positionChangesQuery.data?.result ?? null,
        positionChangesLoading: positionChangesQuery.isLoading,
        positionChangesError: positionChangesQuery.isError,
        researchReports: researchReportsQuery.data?.result ?? null,
        researchReportsLoading: researchReportsQuery.isLoading,
        researchReportsError: researchReportsQuery.isError,
        incomeTrend: incomeTrendQuery.data?.result ?? null,
        incomeTrendLoading: incomeTrendQuery.isLoading,
        incomeTrendError: incomeTrendQuery.isError,
        cockpitWarnings: cockpitWarningsQuery.data?.result ?? null,
        calendarEvents: researchCalendarQuery.data ?? null,
        calendarLoading: researchCalendarQuery.isLoading,
        calendarError: researchCalendarQuery.isError,
        calendarStartDate,
        calendarEndDate,
        todayIsoDate: dashboardTodayIsoDate,
        macroNewsEvents,
        macroNewsLoading,
        macroNewsError,
        snapshotMeta,
        marketMeta: marketRatesQuery.data?.result_meta ?? null,
        alertCount,
        snapshotUnavailable,
        snapshotStale,
      }),
    [
      adapterOutput.attribution.vm,
      adapterOutput.verdict,
      alertCount,
      bondHeadlineQuery.data?.result,
      coreMetricsQuery.data?.result,
      creditSpreadMigrationQuery.data?.result,
      dailyChangesQuery.data?.result,
      decisionItemsQuery.data?.result.rows,
      effectiveReportDate,
      marketRatesQuery.data?.result.series,
      marketRatesQuery.data?.result_meta,
      portfolioComparisonQuery.data?.result,
      portfolioHeadlinesQuery.data?.result,
      returnDecompositionQuery.data?.result,
      campisiFourEffectsQuery.data?.result,
      sanitizedMetrics,
      snapshotMeta,
      assetStructureQuery.data?.result,
      ratingStructureQuery.data?.result,
      maturityStructureQuery.data?.result,
      industryDistributionQuery.data?.result,
      riskIndicatorsQuery.data?.result,
      topHoldingsQuery.data?.result,
      topHoldingsQuery.isLoading,
      topHoldingsQuery.isError,
      positionChangesQuery.data?.result,
      positionChangesQuery.isLoading,
      positionChangesQuery.isError,
      researchReportsQuery.data?.result,
      researchReportsQuery.isLoading,
      researchReportsQuery.isError,
      incomeTrendQuery.data?.result,
      incomeTrendQuery.isLoading,
      incomeTrendQuery.isError,
      yieldCurveTermStructureQuery.data?.result,
      cockpitWarningsQuery.data?.result,
      calendarEndDate,
      calendarStartDate,
      dashboardTodayIsoDate,
      macroNewsError,
      macroNewsEvents,
      macroNewsLoading,
      researchCalendarQuery.data,
      researchCalendarQuery.isError,
      researchCalendarQuery.isLoading,
      snapshotResult?.product_category_monthly,
      snapshotResult?.product_category_ytd,
      snapshotStale,
      snapshotUnavailable,
      useMockFallback,
    ],
  );

  return (
    <section
      data-testid="dashboard-home-page"
      className={styles.dhPage}
    >
      <DashboardHomeToolbar
        headerStatus={view.headerStatus}
        reportDateInput={reportDate || effectiveReportDate}
        onReportDateChange={setReportDate}
        toolbarSearch={toolbarSearch}
        onSearchChange={setToolbarSearch}
        allowPartial={allowPartial}
        onAllowPartialChange={setAllowPartial}
        onRefresh={() => void refreshSnapshot()}
        refreshLabel={snapshotQuery.isFetching ? "刷新中…" : "刷新"}
      />

      <div className={styles.dhLayout}>
        <main className={styles.dhMain}>
          <TerminalHomeContent view={view} />
        </main>

        <DecisionRailSection
          decisionRail={view.decisionRail}
          reportDate={view.reportDate}
          dataSyncPrefix={view.decisionRail.dataSyncPrefix}
          dataStatusKind={view.headerStatus.dataStatusKind}
        />
      </div>
    </section>
  );
}
