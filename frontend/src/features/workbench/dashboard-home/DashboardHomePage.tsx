import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./dashboardHome.module.css";
import { TerminalHomeFirstScreen } from "./TerminalHomeFirstScreen";
import type {
  DashboardHomeFirstScreenHydration,
  DashboardHomeFirstScreenView,
} from "./dashboardHomeFirstScreenTypes";
import { DashboardHomeToolbar } from "./sections/DashboardHomeToolbar";
import { DecisionRailSection } from "./sections/DecisionRailSection";
import { useDashboardHomeFirstScreenViewModel } from "./useDashboardHomeFirstScreenViewModel";

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  cancelIdleCallback?: (handle: number) => void;
};

const HOME_DEFERRED_CONTENT_REVEAL_KEYS = new Set(["ArrowDown", "PageDown", "End", " ", "Space"]);
const HOME_DEFERRED_CONTENT_IDLE_MIN_DELAY_MS = 800;
const HOME_DEFERRED_CONTENT_IDLE_TIMEOUT_MS = 1_200;
const HOME_DEFERRED_CONTENT_TIMEOUT_FALLBACK_MS = 600;

const DeferredTerminalHomeContent = lazy(() =>
  import("./DeferredTerminalHomeContent").then((module) => ({
    default: module.DeferredTerminalHomeContent,
  })),
);

type HydratedFirstScreenState = {
  signature: string;
  view: DashboardHomeFirstScreenHydration;
};

function firstScreenHydrationSignature(hydration: DashboardHomeFirstScreenHydration): string {
  return JSON.stringify({
    reportDate: hydration.reportDate,
    headerStatus: hydration.headerStatus,
    decisionRail: hydration.decisionRail,
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

function useDeferredHomeContent(snapshotSettled: boolean) {
  const [shouldLoad, setShouldLoad] = useState(false);
  const [userReachedDeferredContent, setUserReachedDeferredContent] = useState(false);

  const markUserReached = useCallback(() => {
    setUserReachedDeferredContent(true);
    if (snapshotSettled) {
      setShouldLoad(true);
    }
  }, [snapshotSettled]);

  useEffect(() => {
    if (shouldLoad || userReachedDeferredContent) {
      return undefined;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (HOME_DEFERRED_CONTENT_REVEAL_KEYS.has(event.key)) {
        markUserReached();
      }
    };
    const removeReachListeners = () => {
      window.removeEventListener("scroll", markUserReached);
      window.removeEventListener("wheel", markUserReached);
      window.removeEventListener("touchmove", markUserReached);
      window.removeEventListener("keydown", handleKeyDown);
    };
    window.addEventListener("scroll", markUserReached, { passive: true });
    window.addEventListener("wheel", markUserReached, { passive: true });
    window.addEventListener("touchmove", markUserReached, { passive: true });
    window.addEventListener("keydown", handleKeyDown);

    return removeReachListeners;
  }, [markUserReached, shouldLoad, userReachedDeferredContent]);

  useEffect(() => {
    if (shouldLoad || !snapshotSettled) {
      return undefined;
    }
    if (userReachedDeferredContent) {
      setShouldLoad(true);
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
  }, [shouldLoad, snapshotSettled, userReachedDeferredContent]);

  return { shouldLoad, userReachedDeferredContent };
}

export default function DashboardHomePage() {
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
    effectiveReportDate,
    snapshotBoundary,
  } = useDashboardHomeFirstScreenViewModel();
  const {
    shouldLoad: loadDeferredContent,
    userReachedDeferredContent,
  } = useDeferredHomeContent(!snapshotQuery.isFetching);
  const [hydratedFirstScreen, setHydratedFirstScreen] =
    useState<HydratedFirstScreenState | null>(null);
  const activeReportDate = view.reportDate;

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
            headerStatus: hydratedFirstScreen.view.headerStatus,
            decisionRail: hydratedFirstScreen.view.decisionRail,
            terminalKpis: hydratedFirstScreen.view.terminalKpis,
            keyRiskStrip: hydratedFirstScreen.view.keyRiskStrip,
          }
        : view,
    [activeReportDate, hydratedFirstScreen, view],
  );

  return (
    <section data-testid="dashboard-home-page" className={styles.dhPage}>
      <DashboardHomeToolbar
        title="经营驾驶舱"
        headerStatus={firstScreenView.headerStatus}
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
          <TerminalHomeFirstScreen view={firstScreenView} />
          {loadDeferredContent ? (
            <Suspense fallback={<div aria-hidden="true" className={styles.dhTerminalDeferredPlaceholder} />}>
              <DeferredTerminalHomeContent
                snapshotBoundary={snapshotBoundary}
                userReachedDeferredContent={userReachedDeferredContent}
                onFirstScreenHydrated={handleFirstScreenHydrated}
              />
            </Suspense>
          ) : (
            <div aria-hidden="true" className={styles.dhTerminalDeferredPlaceholder} />
          )}
        </main>

        <DecisionRailSection
          decisionRail={firstScreenView.decisionRail}
          reportDate={firstScreenView.reportDate}
          dataSyncPrefix={firstScreenView.decisionRail.dataSyncPrefix}
          dataStatusKind={firstScreenView.headerStatus.dataStatusKind}
        />
      </div>
    </section>
  );
}
