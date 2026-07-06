import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import styles from "./dashboardHomeShell.module.css";
import { DeferredEvidenceIndexPreview } from "./DeferredEvidenceIndexPreview";
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
const POLICY_FUNDING_DEEP_LINK_PATH = "/政策与资金面";
const HOME_COMMANDS = [
  { label: "组合变动", to: "/bond-analysis" },
  { label: "久期分析", to: "/risk-overview" },
  { label: "收益归因", to: "/pnl-attribution" },
  { label: "待办管理", to: "/decision-items" },
];

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

function reportDateCommandPath(path: string, reportDate: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(reportDate)) {
    return path;
  }
  const params = new URLSearchParams({ report_date: reportDate });
  return `${path}?${params.toString()}`;
}

function HomeCommandDock({
  reportDate,
  dataSyncPrefix,
}: {
  reportDate: string;
  dataSyncPrefix: string;
}) {
  return (
    <nav className={styles.dhCommandDock} data-testid="dashboard-home-command-dock" aria-label="日报快捷命令">
      <span className={styles.dhCommandLabel}>CMD</span>
      <div className={styles.dhCommandList}>
        {HOME_COMMANDS.map((command) => (
          <Link
            key={command.to}
            className={styles.dhCommandItem}
            to={reportDateCommandPath(command.to, reportDate)}
          >
            <span>{command.label}</span>
          </Link>
        ))}
      </div>
      <span className={styles.dhCommandStatus}>
        <span className={styles.dhCommandStatusDot} aria-hidden="true" />
        <span className={styles.dhCommandStatusSynced}>SYNCED</span>
        <span aria-hidden="true">·</span>
        <span>{dataSyncPrefix}</span>
      </span>
    </nav>
  );
}

function useDeferredHomeContent(snapshotSettled: boolean, eagerLoad: boolean) {
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
  }, [eagerLoad, markUserReached, shouldLoad, snapshotSettled, userReachedDeferredContent]);

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
  }, [eagerLoad, shouldLoad, snapshotSettled, userReachedDeferredContent]);

  return { shouldLoad, userReachedDeferredContent };
}

export default function DashboardHomePage() {
  const location = useLocation();
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
    effectiveReportDate,
    snapshotBoundary,
  } = useDashboardHomeFirstScreenViewModel();
  const {
    shouldLoad: loadDeferredContent,
    userReachedDeferredContent,
  } = useDeferredHomeContent(!snapshotQuery.isFetching, shouldFocusPolicyFunding);
  const homeAvailabilityKind =
    snapshotBoundary.displayMode === "real" && snapshotQuery.isError && !snapshotBoundary.snapshotResult
      ? "serviceUnavailable"
      : "normal";
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
            terminalKpis: hydratedFirstScreen.view.terminalKpis,
            keyRiskStrip: hydratedFirstScreen.view.keyRiskStrip,
          }
        : view,
    [activeReportDate, hydratedFirstScreen, view],
  );
  const deferredHomeContent = loadDeferredContent ? (
    <Suspense fallback={<DeferredEvidenceIndexPreview />}>
      <DeferredTerminalHomeContent
        snapshotBoundary={snapshotBoundary}
        userReachedDeferredContent={userReachedDeferredContent}
        focusPolicyFunding={shouldFocusPolicyFunding}
        homeAvailabilityKind={homeAvailabilityKind}
        onFirstScreenHydrated={handleFirstScreenHydrated}
      />
    </Suspense>
  ) : (
    <DeferredEvidenceIndexPreview />
  );

  return (
    <div className="dark text-foreground bg-background min-h-screen">
        <section data-testid="dashboard-home-page" className={`${styles.dhPage} ${styles.dhApiBackedHome}`}>
      <DashboardHomeToolbar
        title="组合经营日报"
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
        <main className={`${styles.dhMain} flex flex-col gap-4`}>
          <TerminalHomeFirstScreen view={firstScreenView} />
          {deferredHomeContent}
        </main>

        <DecisionRailSection
          decisionRail={firstScreenView.decisionRail}
          reportDate={firstScreenView.reportDate}
          dataSyncPrefix={firstScreenView.decisionRail.dataSyncPrefix}
          dataStatusKind={firstScreenView.headerStatus.dataStatusKind}
          snapshotMeta={snapshotBoundary.snapshotMeta}
        />
      </div>
        <HomeCommandDock
          reportDate={firstScreenView.reportDate}
          dataSyncPrefix={firstScreenView.headerStatus.dataSyncPrefix}
        />
      </section>
      </div>
  );
}
