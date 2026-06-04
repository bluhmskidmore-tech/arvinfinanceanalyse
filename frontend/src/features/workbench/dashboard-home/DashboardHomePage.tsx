import { lazy, Suspense, useEffect, useState } from "react";

import styles from "./dashboardHome.module.css";
import { TerminalHomeFirstScreen } from "./TerminalHomeFirstScreen";
import { DashboardHomeToolbar } from "./sections/DashboardHomeToolbar";
import { DecisionRailSection } from "./sections/DecisionRailSection";
import { useDashboardHomeViewModel } from "./useDashboardHomeViewModel";

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  cancelIdleCallback?: (handle: number) => void;
};

const DeferredTerminalHomeContent = lazy(() =>
  import("./TerminalHomeContent").then((module) => ({
    default: module.TerminalHomeContent,
  })),
);

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
  } = useDashboardHomeViewModel();
  const loadDeferredContent = useDeferredHomeContent(!snapshotQuery.isFetching);

  return (
    <section data-testid="dashboard-home-page" className={styles.dhPage}>
      <DashboardHomeToolbar
        title="经营驾驶舱"
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
          <TerminalHomeFirstScreen view={view} />
          {loadDeferredContent ? (
            <Suspense fallback={<div aria-hidden="true" className={styles.dhTerminalDeferredPlaceholder} />}>
              <DeferredTerminalHomeContent view={view} />
            </Suspense>
          ) : (
            <div aria-hidden="true" className={styles.dhTerminalDeferredPlaceholder} />
          )}
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
