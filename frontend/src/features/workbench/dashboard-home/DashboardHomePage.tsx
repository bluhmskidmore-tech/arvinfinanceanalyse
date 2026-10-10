import {
  lazy,
  Suspense,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { SystemReadInteractionContext } from "../../../router/systemReadInteractionContext";
import optionTwoStyles from "./dashboardHomeOptionTwo.module.css";
import { DashboardHomeOptionTwoOverview } from "./DashboardHomeOptionTwoOverview";
import { DeferredEvidenceIndexPreview } from "./DeferredEvidenceIndexPreview";
import { buildDashboardHomeAvailability } from "./dashboardHomeAvailability";
import type {
  DashboardHomeFirstScreenHydration,
  DashboardHomeFirstScreenView,
} from "./dashboardHomeFirstScreenTypes";
import { DashboardHomeToolbar } from "./sections/DashboardHomeToolbar";
import { useDashboardHomeFirstScreenViewModel } from "./useDashboardHomeFirstScreenViewModel";
import { useDeferredHomeContent } from "./useDeferredHomeContent";

const DeferredTerminalHomeContent = lazy(() =>
  import("./DeferredTerminalHomeContent").then((module) => ({
    default: module.DeferredTerminalHomeContent,
  })),
);

const LazyDashboardHomeAgentDrawer = lazy(() =>
  import("./DashboardHomeAgentDrawer").then((module) => ({
    default: module.DashboardHomeAgentDrawer,
  })),
);

type HydratedFirstScreenState = {
  signature: string;
  view: DashboardHomeFirstScreenHydration;
};

function firstScreenHydrationSignature(hydration: DashboardHomeFirstScreenHydration): string {
  return JSON.stringify({
    reportDate: hydration.reportDate,
    keyRiskStrip: hydration.keyRiskStrip,
  });
}

export default function DashboardHomePage() {
  const layoutScrollRootRef = useRef<HTMLDivElement | null>(null);
  const systemReadInteraction = useContext(SystemReadInteractionContext);
  const {
    view,
    reportDate,
    setReportDate,
    toolbarSearch,
    setToolbarSearch,
    allowPartial,
    setAllowPartial,
    refreshSnapshot,
    snapshotQuery,
    snapshotBoundary,
  } = useDashboardHomeFirstScreenViewModel();
  const {
    deferredContentSentinelRef,
    shouldLoad: loadDeferredContent,
    userReachedDeferredContent,
  } = useDeferredHomeContent(
    Boolean(snapshotBoundary.supplementalReportDate) || !snapshotQuery.isFetching,
    layoutScrollRootRef,
  );
  const [hydratedFirstScreen, setHydratedFirstScreen] =
    useState<HydratedFirstScreenState | null>(null);
  const lastSnapshotErrorDetailRef = useRef<string | null>(null);
  const [agentPanelOpen, setAgentPanelOpen] = useState(false);
  const [agentPanelMounted, setAgentPanelMounted] = useState(false);
  const [refreshNotice, setRefreshNotice] = useState<string | null>(null);
  const refreshNoticeTimerRef = useRef<number | null>(null);
  const activeReportDate = view.reportDate;

  const openAgentPanel = useCallback(() => {
    setAgentPanelMounted(true);
    setAgentPanelOpen(true);
  }, []);

  // 手动刷新完成后的轻量反馈（交接包 Interactions；测试环境静默）。
  // 直接消费 refetch 的 Promise 结果，不依赖 isFetching/isSuccess 边沿推断。
  const handleToolbarRefresh = useCallback(() => {
    if (systemReadInteraction?.generation) {
      systemReadInteraction.refresh();
      return;
    }
    void (async () => {
      let succeeded = true;
      try {
        const result = (await refreshSnapshot()) as
          | { isSuccess?: boolean; status?: string }
          | null
          | undefined;
        if (result && (result.isSuccess === false || result.status === "error")) {
          succeeded = false;
        }
      } catch {
        succeeded = false;
      }
      if (
        !succeeded ||
        import.meta.env.MODE === "test" ||
        (import.meta.env as Record<string, unknown>).VITEST != null
      ) {
        return;
      }
      setRefreshNotice("首页数据已刷新");
      if (refreshNoticeTimerRef.current != null) {
        window.clearTimeout(refreshNoticeTimerRef.current);
      }
      refreshNoticeTimerRef.current = window.setTimeout(() => {
        setRefreshNotice(null);
        refreshNoticeTimerRef.current = null;
      }, 2300);
    })();
  }, [refreshSnapshot, systemReadInteraction]);

  useEffect(
    () => () => {
      if (refreshNoticeTimerRef.current != null) {
        window.clearTimeout(refreshNoticeTimerRef.current);
      }
    },
    [],
  );

  useEffect(() => {
    // A cached new-date child can emit before this parent effect runs.
    setHydratedFirstScreen((current) =>
      current?.view.reportDate === activeReportDate ? current : null,
    );
  }, [activeReportDate]);

  const handleFirstScreenHydrated = useCallback(
    (hydration: DashboardHomeFirstScreenHydration) => {
      if (hydration.reportDate !== activeReportDate) {
        return;
      }
      setHydratedFirstScreen((current) => {
        const signature = firstScreenHydrationSignature(hydration);
        if (current?.signature === signature) {
          return current;
        }
        return { signature, view: hydration };
      });
    },
    [activeReportDate],
  );
  const firstScreenView = useMemo<DashboardHomeFirstScreenView>(
    () =>
      hydratedFirstScreen && hydratedFirstScreen.view.reportDate === activeReportDate
        ? {
            ...view,
            // Supplemental endpoints may enrich context below the fold, but never
            // replace the four governed snapshot KPI contracts on the first screen.
            keyRiskStrip: hydratedFirstScreen.view.keyRiskStrip,
          }
        : view,
    [activeReportDate, hydratedFirstScreen, view],
  );
  const snapshotErrorDetail =
    snapshotQuery.error instanceof Error ? snapshotQuery.error.message : null;
  useEffect(() => {
    if (snapshotErrorDetail) {
      lastSnapshotErrorDetailRef.current = snapshotErrorDetail;
    } else if (snapshotQuery.isSuccess) {
      lastSnapshotErrorDetailRef.current = null;
    }
  }, [snapshotErrorDetail, snapshotQuery.isSuccess]);
  const retryingUnresolvedSnapshot =
    snapshotQuery.isFetching &&
    !snapshotBoundary.snapshotResult &&
    Boolean(lastSnapshotErrorDetailRef.current);
  const retainedSnapshotErrorDetail =
    snapshotErrorDetail ||
    (retryingUnresolvedSnapshot
      ? lastSnapshotErrorDetailRef.current
      : null);
  const homeAvailability = useMemo(
    () =>
      buildDashboardHomeAvailability({
        dataStatusKind: firstScreenView.headerStatus.dataStatusKind,
        dataSyncPrefix: firstScreenView.headerStatus.dataSyncPrefix,
        reportDateContext: firstScreenView.reportDateContext,
        snapshotMeta: snapshotBoundary.snapshotMeta,
        snapshotErrorDetail: retainedSnapshotErrorDetail,
        snapshotRetryingAfterError: retryingUnresolvedSnapshot,
        missingDomainLabels: firstScreenView.missingDomains.map(
          (domain) => domain.label,
        ),
      }),
    [
      firstScreenView.headerStatus.dataStatusKind,
      firstScreenView.headerStatus.dataSyncPrefix,
      firstScreenView.missingDomains,
      firstScreenView.reportDateContext,
      snapshotBoundary.snapshotMeta,
      retainedSnapshotErrorDetail,
      retryingUnresolvedSnapshot,
    ],
  );
  const homeAvailabilityKind =
    homeAvailability.kind === "error" ? "serviceUnavailable" : "normal";
  const handleViewLatestReport = useCallback(() => {
    setReportDate("");
  }, [setReportDate]);
  const agentPanelFilters = useMemo(
    () => ({
      allow_partial: allowPartial,
      data_status: firstScreenView.headerStatus.dataStatusKind,
    }),
    [allowPartial, firstScreenView.headerStatus.dataStatusKind],
  );
  const deferredHomeContent = loadDeferredContent ? (
    <Suspense fallback={<DeferredEvidenceIndexPreview />}>
      <DeferredTerminalHomeContent
        snapshotBoundary={snapshotBoundary}
        firstScreenView={firstScreenView}
        userReachedDeferredContent={userReachedDeferredContent}
        homeAvailability={homeAvailability}
        homeAvailabilityKind={homeAvailabilityKind}
        snapshotRefreshing={snapshotQuery.isFetching}
        onViewLatestReport={handleViewLatestReport}
        onFirstScreenHydrated={handleFirstScreenHydrated}
      />
    </Suspense>
  ) : (
    <DeferredEvidenceIndexPreview />
  );

  return (
    <div className="dark text-foreground bg-background min-h-screen">
      <section
        data-testid="dashboard-home-page"
        data-moss-theme="dark"
        data-moss-theme-scope="dashboard-home"
        className={`theme-dh-api ${optionTwoStyles.page}`}
      >
        <DashboardHomeToolbar
          title="组合经营日报"
          headerStatus={firstScreenView.headerStatus}
          reportDateInput={reportDate || firstScreenView.reportDateContext.actualDataDate}
          onReportDateChange={setReportDate}
          reportDateContext={firstScreenView.reportDateContext}
          toolbarSearch={toolbarSearch}
          onSearchChange={setToolbarSearch}
          terminalKpis={firstScreenView.terminalKpis}
          decisionActions={firstScreenView.decisionRail.actions}
          allowPartial={allowPartial}
          onAllowPartialChange={setAllowPartial}
          onRefresh={handleToolbarRefresh}
          refreshLabel={snapshotQuery.isFetching ? "刷新中…" : "刷新"}
          refreshAriaLabel="刷新首页数据"
          refreshing={snapshotQuery.isFetching}
          onOpenAgentPanel={openAgentPanel}
        />

        <div
          ref={layoutScrollRootRef}
          data-testid="dashboard-home-scroll-root"
          className={optionTwoStyles.layout}
          role="region"
          aria-label="组合经营日报内容"
        >
          <DashboardHomeOptionTwoOverview view={firstScreenView} />

          <div
            data-testid="dashboard-home-deferred-content"
            className={optionTwoStyles.deferred}
            aria-busy={!loadDeferredContent}
          >
            {deferredHomeContent}
            <div
              ref={deferredContentSentinelRef}
              data-testid="dashboard-home-deferred-sentinel"
              className={optionTwoStyles.deferredSentinel}
              aria-hidden="true"
            />
          </div>
        </div>

        {agentPanelMounted ? (
          <Suspense fallback={null}>
            <LazyDashboardHomeAgentDrawer
              open={agentPanelOpen}
              reportDate={firstScreenView.reportDate}
              currentFilters={agentPanelFilters}
              onClose={() => setAgentPanelOpen(false)}
            />
          </Suspense>
        ) : null}

        {refreshNotice ? (
          <div className={optionTwoStyles.refreshToast} role="status">
            {refreshNotice}
          </div>
        ) : null}
      </section>
    </div>
  );
}
