import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useLocation } from "react-router-dom";

import styles from "./dashboardHomeShell.module.css";
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

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  cancelIdleCallback?: (handle: number) => void;
};

const HOME_DEFERRED_CONTENT_REVEAL_KEYS = new Set(["ArrowDown", "PageDown", "End", " ", "Space"]);
const HOME_DEFERRED_CONTENT_IDLE_MIN_DELAY_MS = 800;
const HOME_DEFERRED_CONTENT_IDLE_TIMEOUT_MS = 1_200;
const HOME_DEFERRED_CONTENT_TIMEOUT_FALLBACK_MS = 600;
const POLICY_FUNDING_DEEP_LINK_PATH = "/政策与资金面";

function resolveHomeScrollRoot(node: HTMLElement | null): HTMLElement | null {
  if (!node) {
    return null;
  }
  return /^(auto|scroll|overlay)$/.test(window.getComputedStyle(node).overflowY)
    ? node
    : null;
}

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
    terminalKpis: hydration.terminalKpis.map((kpi) => ({
      id: kpi.id,
      value: kpi.value,
      unit: kpi.unit,
      delta: kpi.delta,
      deltaTone: kpi.deltaTone,
      state: kpi.state,
    })),
    keyRiskStrip: hydration.keyRiskStrip.map((item) => ({
      id: item.id,
      value: item.value,
      delta: item.delta,
      deltaTone: item.deltaTone,
    })),
  });
}

function isPolicyFundingDeepLink(pathname: string): boolean {
  try {
    return decodeURIComponent(pathname) === POLICY_FUNDING_DEEP_LINK_PATH;
  } catch {
    return pathname === POLICY_FUNDING_DEEP_LINK_PATH;
  }
}

function useDeferredHomeContent(
  snapshotSettled: boolean,
  eagerLoad: boolean,
  layoutScrollRootRef: { current: HTMLElement | null },
) {
  const deferredContentSentinelRef = useRef<HTMLDivElement | null>(null);
  const [shouldLoad, setShouldLoad] = useState(false);
  const [userReachedDeferredContent, setUserReachedDeferredContent] = useState(false);

  const markUserReached = useCallback(() => {
    setUserReachedDeferredContent(true);
    if (snapshotSettled) {
      setShouldLoad(true);
    }
  }, [snapshotSettled]);

  useEffect(() => {
    if (eagerLoad && snapshotSettled) {
      setUserReachedDeferredContent(true);
      setShouldLoad(true);
      return undefined;
    }

    if (shouldLoad || userReachedDeferredContent) {
      return undefined;
    }

    const layoutScrollRoot = resolveHomeScrollRoot(layoutScrollRootRef.current);
    const handleKeyDown = (event: KeyboardEvent) => {
      if (HOME_DEFERRED_CONTENT_REVEAL_KEYS.has(event.key)) {
        markUserReached();
      }
    };
    const scrollTarget: Window | HTMLElement = layoutScrollRoot ?? window;
    const addPassiveListener = (
      eventName: "scroll" | "wheel" | "touchmove",
      listener: () => void,
    ) => {
      scrollTarget.addEventListener(eventName, listener, { passive: true });
    };
    const removeReachListeners = () => {
      scrollTarget.removeEventListener("scroll", markUserReached);
      scrollTarget.removeEventListener("wheel", markUserReached);
      scrollTarget.removeEventListener("touchmove", markUserReached);
      window.removeEventListener("keydown", handleKeyDown);
    };

    addPassiveListener("scroll", markUserReached);
    addPassiveListener("wheel", markUserReached);
    addPassiveListener("touchmove", markUserReached);
    window.addEventListener("keydown", handleKeyDown);

    return removeReachListeners;
  }, [
    eagerLoad,
    layoutScrollRootRef,
    markUserReached,
    shouldLoad,
    snapshotSettled,
    userReachedDeferredContent,
  ]);

  useEffect(() => {
    if (eagerLoad && snapshotSettled) {
      setUserReachedDeferredContent(true);
      setShouldLoad(true);
      return undefined;
    }

    if (shouldLoad || userReachedDeferredContent) {
      return undefined;
    }

    const deferredContentNode = deferredContentSentinelRef.current;
    if (typeof window.IntersectionObserver === "undefined" || !deferredContentNode) {
      return undefined;
    }
    const intersectionRoot = resolveHomeScrollRoot(layoutScrollRootRef.current);

    const observer = new window.IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting || entry.intersectionRatio > 0)) {
          markUserReached();
          observer.disconnect();
        }
      },
      { root: intersectionRoot },
    );
    let isActive = true;
    const observeHandle = window.setTimeout(() => {
      if (isActive) {
        observer.observe(deferredContentNode);
      }
    }, HOME_DEFERRED_CONTENT_IDLE_MIN_DELAY_MS);
    return () => {
      isActive = false;
      window.clearTimeout(observeHandle);
      observer.disconnect();
    };
  }, [
    eagerLoad,
    layoutScrollRootRef,
    markUserReached,
    shouldLoad,
    snapshotSettled,
    userReachedDeferredContent,
  ]);

  useEffect(() => {
    if (eagerLoad && snapshotSettled) {
      setShouldLoad(true);
      return undefined;
    }

    if (shouldLoad || !snapshotSettled) {
      return undefined;
    }
    if (userReachedDeferredContent) {
      setShouldLoad(true);
      return undefined;
    }
    if (typeof window.IntersectionObserver !== "undefined") {
      return undefined;
    }

    let isActive = true;
    const idleWindow = window as IdleWindow;
    let idleHandle: number | null = null;
    let timeoutHandle: number | null = null;
    let delayHandle: number | null = null;
    const cancelScheduledWork = () => {
      if (idleHandle != null) {
        idleWindow.cancelIdleCallback?.(idleHandle);
        idleHandle = null;
      }
      if (timeoutHandle != null) {
        window.clearTimeout(timeoutHandle);
        timeoutHandle = null;
      }
      if (delayHandle != null) {
        window.clearTimeout(delayHandle);
        delayHandle = null;
      }
    };
    const markReady = () => {
      if (isActive) {
        cancelScheduledWork();
        setUserReachedDeferredContent(true);
        setShouldLoad(true);
      }
    };

    const scheduleDeferredContent = () => {
      if (!isActive) {
        return;
      }
      if (idleWindow.requestIdleCallback) {
        idleHandle = idleWindow.requestIdleCallback(markReady, {
          timeout: HOME_DEFERRED_CONTENT_IDLE_TIMEOUT_MS,
        });
        return;
      }
      timeoutHandle = window.setTimeout(markReady, HOME_DEFERRED_CONTENT_TIMEOUT_FALLBACK_MS);
    };
    delayHandle = window.setTimeout(scheduleDeferredContent, HOME_DEFERRED_CONTENT_IDLE_MIN_DELAY_MS);

    return () => {
      isActive = false;
      cancelScheduledWork();
    };
  }, [eagerLoad, shouldLoad, snapshotSettled, userReachedDeferredContent]);

  return { deferredContentSentinelRef, shouldLoad, userReachedDeferredContent };
}

export default function DashboardHomePage() {
  const location = useLocation();
  const layoutScrollRootRef = useRef<HTMLDivElement | null>(null);
  const shouldFocusPolicyFunding = isPolicyFundingDeepLink(location.pathname);
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
    !snapshotQuery.isFetching,
    shouldFocusPolicyFunding,
    layoutScrollRootRef,
  );
  const [hydratedFirstScreen, setHydratedFirstScreen] =
    useState<HydratedFirstScreenState | null>(null);
  const lastSnapshotErrorDetailRef = useRef<string | null>(null);
  const [agentPanelOpen, setAgentPanelOpen] = useState(false);
  const [agentPanelMounted, setAgentPanelMounted] = useState(false);
  const activeReportDate = view.reportDate;

  const openAgentPanel = useCallback(() => {
    setAgentPanelMounted(true);
    setAgentPanelOpen(true);
  }, []);

  useEffect(() => {
    setHydratedFirstScreen(null);
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
        focusPolicyFunding={shouldFocusPolicyFunding}
        homeAvailability={homeAvailability}
        homeAvailabilityKind={homeAvailabilityKind}
        snapshotRefreshing={snapshotQuery.isFetching}
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
        className={`theme-dh-api ${styles.dhPage} ${styles.dhApiBackedHome} ${optionTwoStyles.page}`}
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
          onRefresh={() => void refreshSnapshot()}
          refreshLabel={snapshotQuery.isFetching ? "刷新中…" : "刷新"}
          refreshAriaLabel="刷新首页数据"
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
      </section>
    </div>
  );
}
