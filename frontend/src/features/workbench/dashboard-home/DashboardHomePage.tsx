import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiQueryKeys } from "../../../api/queryKeys";
import { sanitizeMetricCopy } from "../../executive-dashboard/lib/sanitizeMetricCopy";
import { useDashboardData } from "../dashboard/hooks/useDashboardData";
import { useDashboardSnapshotBoundary } from "../pages/useDashboardSnapshotBoundary";
import styles from "./dashboardHome.module.css";
import { mapToHomeView } from "./dashboardHomeView";
import { BottomGridSection } from "./sections/BottomGridSection";
import { DashboardHomeToolbar } from "./sections/DashboardHomeToolbar";
import { DecisionRailSection } from "./sections/DecisionRailSection";
import { HeroSection } from "./sections/HeroSection";
import { MarketTapeSection } from "./sections/MarketTapeSection";
import { ResearchCalendarSection } from "./sections/ResearchCalendarSection";
import { WorkGridSection } from "./sections/WorkGridSection";

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
    decisionItemsQuery,
    researchCalendarQuery,
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
        decisionItems: decisionItemsQuery.data?.result.rows ?? null,
        marketPoints: marketRatesQuery.data?.result.series ?? null,
        productCategoryYtd: snapshotResult?.product_category_ytd ?? null,
        productCategoryMonthly: snapshotResult?.product_category_monthly ?? null,
        assetStructure: assetStructureQuery.data?.result ?? null,
        cockpitWarnings: cockpitWarningsQuery.data?.result ?? null,
        calendarEvents: researchCalendarQuery.data ?? null,
        calendarLoading: researchCalendarQuery.isLoading,
        calendarError: researchCalendarQuery.isError,
        calendarStartDate,
        calendarEndDate,
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
      sanitizedMetrics,
      snapshotMeta,
      assetStructureQuery.data?.result,
      cockpitWarningsQuery.data?.result,
      calendarEndDate,
      calendarStartDate,
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
          <HeroSection
            aiJudge={view.aiJudge}
            coreKpis={view.coreKpis}
            riskMinis={view.riskMinis}
          />
          <MarketTapeSection items={view.marketTape} />
          <WorkGridSection
            portfolioStats={view.portfolioStats}
            assetBars={view.assetBars}
            assetBarsPlaceholder={view.assetBarsPlaceholder}
            centerAum={view.centerAum}
            interbank={view.interbank}
            attributionTabs={view.attributionTabs}
            attributionWaterfall={view.attributionWaterfall}
            attributionInsights={view.attributionInsights}
            attributionNote={view.attributionNote}
            riskCards={view.riskCards}
            riskCardsPlaceholder={view.riskCardsPlaceholder}
            riskRadar={view.riskRadar}
            todos={view.todos}
            watchlist={view.watchlist}
            watchlistPlaceholder={view.watchlistPlaceholder}
            liabilityWatchBasisNote={view.liabilityWatchBasisNote}
          />
          <ResearchCalendarSection calendar={view.researchCalendar} />
          <BottomGridSection
            exposureRows={view.exposureRows}
            balanceMetrics={view.balanceMetrics}
            quickDrilldowns={view.quickDrilldowns}
          />
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
