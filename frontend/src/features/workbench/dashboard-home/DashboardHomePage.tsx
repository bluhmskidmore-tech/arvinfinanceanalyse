import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

/* 顺序契约：shell 表必须先于 optionTwo 表注册。两表间存在同特异性 (0,3,0) 的
   toolbar 锚点规则（shell 稠密层 id254 组 vs optionTwo .page>[toolbar] 组），
   级联胜负由源顺序决定；首页根元素已不用 shell 局部类，但 Toolbar/SearchBox
   等子组件仍消费其非前缀类，若移除此 side-effect import，shell 表会改由
   子组件在 optionTwo 之后注册，顺序反转将令 toolbar 布局漂移。 */
import "./dashboardHomeShell.module.css";
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

const HOME_DEFERRED_CHUNK_PREFETCH_DELAY_MS = 600;

/**
 * 下折内容藏在 800ms 揭示门控之后，但它的 chunk 原本要等门控放行才开始下载，
 * 形成 Content → Body → API client 三跳串行 RTT，把第二波请求推迟 150-300ms。
 * 在门控等待的窗口里用运行时 import() 预热同一批模块：只下载求值、不渲染、
 * 不发请求，揭示时机不变；chunk 归属与 HTML 预加载预算也不变（bundle 守卫禁止
 * 这些 chunk 出现在 eager preload 里，运行时 import() 不在其检查范围）。
 * 用 setTimeout 而非 requestIdleCallback：600ms 已避开首屏渲染，且不占用
 * 揭示门控依赖的 idle 队列。
 */
function useDeferredHomeChunkPrefetch() {
  useEffect(() => {
    // 纯网络预热，测试环境里既无意义又会把真实 chunk 拉进 jsdom。
    if (import.meta.env.TEST) {
      return undefined;
    }
    let cancelled = false;
    const timeoutHandle = window.setTimeout(() => {
      if (cancelled) {
        return;
      }
      void import("./DeferredTerminalHomeContent");
      void import("./DeferredTerminalHomeBody");
      void import("../../../api/homeSupplementalClient");
      void import("../../../api/homeMarketTickerClient");
    }, HOME_DEFERRED_CHUNK_PREFETCH_DELAY_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutHandle);
    };
  }, []);
}

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

function useDeferredHomeContent(
  snapshotSettled: boolean,
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
    layoutScrollRootRef,
    markUserReached,
    shouldLoad,
    userReachedDeferredContent,
  ]);

  useEffect(() => {
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
    layoutScrollRootRef,
    markUserReached,
    shouldLoad,
    userReachedDeferredContent,
  ]);

  useEffect(() => {
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
  }, [shouldLoad, snapshotSettled, userReachedDeferredContent]);

  return { deferredContentSentinelRef, shouldLoad, userReachedDeferredContent };
}

export default function DashboardHomePage() {
  const layoutScrollRootRef = useRef<HTMLDivElement | null>(null);
  useDeferredHomeChunkPrefetch();
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
  } = useDeferredHomeContent(!snapshotQuery.isFetching, layoutScrollRootRef);
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
  }, [refreshSnapshot]);

  useEffect(
    () => () => {
      if (refreshNoticeTimerRef.current != null) {
        window.clearTimeout(refreshNoticeTimerRef.current);
      }
    },
    [],
  );

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
