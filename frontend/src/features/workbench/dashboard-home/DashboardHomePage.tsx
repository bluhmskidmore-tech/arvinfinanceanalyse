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

  useEffect(() => {
    if (shouldLoad || !snapshotSettled) {
      return undefined;
    }

    let isActive = true;
    const markReady = () => {
      if (isActive) {
        setShouldLoad(true);
      }
    };
    const idleWindow = window as IdleWindow;
    if (idleWindow.requestIdleCallback) {
      const idleHandle = idleWindow.requestIdleCallback(markReady, {
        timeout: 1_200,
      });
      return () => {
        isActive = false;
        idleWindow.cancelIdleCallback?.(idleHandle);
      };
    }

    const timeoutHandle = window.setTimeout(markReady, 250);
    return () => {
      isActive = false;
      window.clearTimeout(timeoutHandle);
    };
  }, [shouldLoad, snapshotSettled]);

  return shouldLoad;
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
  const loadDeferredContent = useDeferredHomeContent(!snapshotQuery.isFetching);
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
