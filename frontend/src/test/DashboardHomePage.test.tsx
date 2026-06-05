import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="dashboard-echarts-stub" />,
}));

import { createApiClient, type ApiClient } from "../api/client";
import type { ApiEnvelope, ChoiceNewsEvent, ChoiceNewsEventsPayload } from "../api/contracts";
import {
  DASHBOARD_BOND_NEWS_TOPICS,
  DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS,
  DASHBOARD_MACRO_NEWS_TOPICS,
} from "../features/workbench/dashboard/dashboardMacroNewsTopics";
import type { DashboardHomeBodyView } from "../features/workbench/dashboard-home/dashboardHomeBodyView";
import { TerminalHomeContent } from "../features/workbench/dashboard-home/TerminalHomeContent";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

type MockIntersectionObserver = {
  observe: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
  triggerAll: (entry?: Partial<IntersectionObserverEntry>) => void;
};

afterEach(() => {
  vi.unstubAllGlobals();
});

beforeAll(async () => {
  await preloadWorkbenchRouteModules("dashboard-home");
}, 20_000);

function stubIntersectionObserver(): MockIntersectionObserver {
  const callbacks: IntersectionObserverCallback[] = [];
  const observer: MockIntersectionObserver = {
    observe: vi.fn(),
    disconnect: vi.fn(),
    triggerAll: (entry = {}) => {
      const target = (entry.target ?? document.createElement("div")) as Element;
      for (const callback of callbacks) {
        callback(
          [
            {
              isIntersecting: false,
              intersectionRatio: 0,
              target,
              ...entry,
            } as IntersectionObserverEntry,
          ],
          {} as IntersectionObserver,
        );
      }
    },
  };
  const MockObserver = vi.fn(function MockIntersectionObserver(callback: IntersectionObserverCallback) {
    callbacks.push(callback);
    return observer;
  });

  vi.stubGlobal("IntersectionObserver", MockObserver);
  return observer;
}


function createRealModeHomeClient(overrides: Partial<ApiClient> = {}): ApiClient {
  const base = createApiClient({ mode: "real" });
  const mockSnapshotSource = createApiClient({ mode: "mock" });
  return {
    ...base,
    getHomeSnapshot: (...args) => mockSnapshotSource.getHomeSnapshot(...args),
    ...overrides,
  };
}

function renderDashboardHome(client?: ApiClient) {
  return renderWorkbenchApp(["/"], {
    client: client ?? createApiClient({ mode: "mock" }),
  });
}

function stubIdleCallbacks() {
  const callbacks = new Map<number, () => void>();
  let nextHandle = 1;

  vi.stubGlobal(
    "requestIdleCallback",
    vi.fn((callback: () => void) => {
      const handle = nextHandle;
      nextHandle += 1;
      callbacks.set(handle, callback);
      return handle;
    }),
  );
  vi.stubGlobal(
    "cancelIdleCallback",
    vi.fn((handle: number) => {
      callbacks.delete(handle);
    }),
  );

  return {
    pendingCount: () => callbacks.size,
    runPending: () => {
      const pending = Array.from(callbacks.values());
      callbacks.clear();
      for (const callback of pending) {
        callback();
      }
    },
  };
}

type StubbedIdleCallbacks = ReturnType<typeof stubIdleCallbacks>;

async function runNextIdle(idle: StubbedIdleCallbacks) {
  await waitFor(() => {
    expect(idle.pendingCount()).toBeGreaterThan(0);
  });
  await act(async () => {
    idle.runPending();
  });
}

async function waitForDeferredHomeContentDelay() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 850));
  });
}

async function waitForBodyAutoRevealDelay() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 2_100));
  });
}

async function waitForBodyDetailDataDelay() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 1_100));
  });
}

async function waitForEventFeedDataDelay() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 1_100));
  });
}

async function waitForSecondaryEventFeedDataDelay() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 1_100));
  });
}

async function revealHomeBodyAndDetailData(idle: StubbedIdleCallbacks) {
  await runNextIdle(idle);
  await waitForBodyAutoRevealDelay();
  await runNextIdle(idle);
  await screen.findByTestId("dashboard-home-work-grid");
  await waitForBodyDetailDataDelay();
  await runNextIdle(idle);
}

async function revealHomeBodyDetailAndEventFeeds(idle: StubbedIdleCallbacks) {
  await revealHomeBodyAndDetailData(idle);
  await waitForEventFeedDataDelay();
  await runNextIdle(idle);
  await waitForSecondaryEventFeedDataDelay();
  await runNextIdle(idle);
}

function requestedNewsTopicCodes(spy: {
  mock: { calls: Array<Parameters<ApiClient["getChoiceNewsEvents"]>> };
}): string[] {
  return spy.mock.calls.map(([options]) => options.topicCode ?? "");
}

function requestedNewsTopicCount(
  spy: { mock: { calls: Array<Parameters<ApiClient["getChoiceNewsEvents"]>> } },
  topicCode: string,
): number {
  return requestedNewsTopicCodes(spy).filter((requestedTopicCode) => requestedTopicCode === topicCode).length;
}

function bondNewsTopicCodesExcludingFallbackTopics(): string[] {
  const fallbackTopicCodes = new Set<string>(DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code));
  return DASHBOARD_BOND_NEWS_TOPICS.filter((topic) => !fallbackTopicCodes.has(topic.code)).map(
    (topic) => topic.code,
  );
}

function bondNewsProbeTopicCode(): string {
  return bondNewsTopicCodesExcludingFallbackTopics()[0] ?? "";
}

function remainingBondNewsTopicCodesAfterProbe(): string[] {
  return bondNewsTopicCodesExcludingFallbackTopics().slice(1);
}

function choiceNewsEvent(overrides: Partial<ChoiceNewsEvent>): ChoiceNewsEvent {
  return {
    event_key: overrides.event_key ?? "home-choice-news-ok",
    received_at: overrides.received_at ?? "2026-06-04T09:30:00Z",
    group_id: overrides.group_id ?? "home",
    content_type: overrides.content_type ?? "sectornews",
    serial_id: overrides.serial_id ?? 1,
    request_id: overrides.request_id ?? 1,
    error_code: overrides.error_code ?? 0,
    error_msg: overrides.error_msg ?? "",
    topic_code: overrides.topic_code ?? DASHBOARD_MACRO_NEWS_TOPICS[0].code,
    item_index: overrides.item_index ?? 0,
    payload_text: overrides.payload_text ?? "资金面维持平稳，DR007 小幅回落。",
    payload_json: overrides.payload_json ?? null,
  };
}

function choiceNewsEnvelope(events: ChoiceNewsEvent[]): ApiEnvelope<ChoiceNewsEventsPayload> {
  return {
    result_meta: {
      basis: "formal",
      trace_id: "tr_home_choice_news_test",
      result_kind: "news.choice.latest",
      formal_use_allowed: true,
      source_version: "sv_test",
      vendor_version: "vv_test",
      rule_version: "rv_test",
      cache_version: "cv_test",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-06-04T00:00:00Z",
    },
    result: {
      total_rows: events.length,
      limit: events.length,
      offset: 0,
      events,
    },
  };
}

function createSupplementalHomeSpies(mockSnapshotSource: ApiClient) {
  return {
    getMarketDataRates: vi.fn(mockSnapshotSource.getMarketDataRates),
    getCoreMetrics: vi.fn(mockSnapshotSource.getCoreMetrics),
    getDailyChanges: vi.fn(mockSnapshotSource.getDailyChanges),
    getBondDashboardHeadlineKpis: vi.fn(mockSnapshotSource.getBondDashboardHeadlineKpis),
    getBondDashboardHomeSummary: vi.fn(mockSnapshotSource.getBondDashboardHomeSummary),
    getBondAnalyticsPortfolioHeadlines: vi.fn(mockSnapshotSource.getBondAnalyticsPortfolioHeadlines),
    getBondDashboardPortfolioComparison: vi.fn(mockSnapshotSource.getBondDashboardPortfolioComparison),
    getBondAnalyticsCreditSpreadMigration: vi.fn(mockSnapshotSource.getBondAnalyticsCreditSpreadMigration),
    getBondAnalyticsReturnDecomposition: vi.fn(mockSnapshotSource.getBondAnalyticsReturnDecomposition),
    getPnlCampisiFourEffects: vi.fn(mockSnapshotSource.getPnlCampisiFourEffects),
    getBondAnalyticsYieldCurveTermStructure: vi.fn(mockSnapshotSource.getBondAnalyticsYieldCurveTermStructure),
    getBalanceAnalysisDecisionItems: vi.fn(mockSnapshotSource.getBalanceAnalysisDecisionItems),
    getResearchCalendarEvents: vi.fn(async () => []),
    getChoiceNewsEvents: vi.fn(mockSnapshotSource.getChoiceNewsEvents),
    getBondDashboardAssetStructure: vi.fn(mockSnapshotSource.getBondDashboardAssetStructure),
    getBondDashboardMaturityStructure: vi.fn(mockSnapshotSource.getBondDashboardMaturityStructure),
    getBondDashboardIndustryDistribution: vi.fn(mockSnapshotSource.getBondDashboardIndustryDistribution),
    getBondDashboardRiskIndicators: vi.fn(mockSnapshotSource.getBondDashboardRiskIndicators),
    getBondAnalyticsTopHoldings: vi.fn(mockSnapshotSource.getBondAnalyticsTopHoldings),
    getBondAnalyticsPositionChanges: vi.fn(mockSnapshotSource.getBondAnalyticsPositionChanges),
    getHomeResearchReports: vi.fn(mockSnapshotSource.getHomeResearchReports),
    getHomeIncomeTrend: vi.fn(mockSnapshotSource.getHomeIncomeTrend),
    getCockpitWarnings: vi.fn(mockSnapshotSource.getCockpitWarnings),
  };
}

function createTerminalStateView(overrides: Partial<DashboardHomeBodyView> = {}): DashboardHomeBodyView {
  const baseState = { kind: "empty" as const, label: "暂无数据" };
  return {
    reportDate: "2026-04-30",
    quickDrilldowns: [],
    macroBriefing: {
      releaseItems: [],
      releaseWindowLabel: "未来 45 天",
      releaseMessage: "暂无已维护发布日期，请补充配置清单。",
      newsItems: [],
      newsMessage: "政策与资金面：暂无债券相关更新",
      newsStale: false,
      newsFreshnessLabel: "暂无更新",
      newsSourceLabel: "来源：Choice 宏观新闻",
      newsAsOfLabel: "数据截至：暂无",
      newsStatusLabel: "来源状态：暂无数据",
      newsRefreshLabel: "刷新：随页面查询自动更新",
      supplyItems: [{ id: "supply-empty", label: "供给/招标：当前窗口无事件" }],
    },
    bondNews: {
      holdingHits: [],
      marketNews: [],
      creditAndIssuanceNews: [],
      holdingMessage: "持仓命中：当前无相关新闻",
      marketMessage: "债券市场：暂无相关新闻",
      creditMessage: "发行/评级：暂无相关新闻",
      sourceLabel: "来源：Choice / Tushare 债券新闻",
      asOfLabel: "数据截至：暂无",
      statusLabel: "来源状态：暂无数据",
      refreshLabel: "刷新：随页面查询自动更新",
    },
    marketContext: {
      temperatureLabel: "市场温度：中性",
      temperatureScore: 50,
      temperatureTone: "neutral",
      drivers: ["外部市场暂无明显方向"],
      contextBlocks: [
        {
          id: "pnl",
          label: "PnL归因",
          title: "等待正式归因数据",
          detail: "未收到 return-decomposition 正式 payload",
          foot: "不从总 PnL 反推归因",
        },
        {
          id: "curve",
          label: "曲线/利率",
          title: "等待曲线期限结构",
          detail: "未收到 yield_curve_term_structure 正式 payload",
          foot: "默认曲线 treasury,cdb,aaa_credit",
        },
        {
          id: "credit",
          label: "信用利差",
          title: "等待信用利差上下文",
          detail: "未收到 credit_spread_migration 正式 payload",
          foot: "只作解释变量，不改变 PnL 计算",
        },
      ],
      aiSummary: [
        "PnL归因：等待正式归因数据；未收到 return-decomposition 正式 payload。",
        "曲线/利率：等待曲线期限结构；未收到 yield_curve_term_structure 正式 payload。",
      ],
      sourceLabel: "来源：收益归因 / yield_curve_term_structure / credit_spread_migration",
      asOfLabel: "数据截至：暂无",
      statusLabel: "来源状态：等待正式数据",
      refreshLabel: "刷新：随报告日查询自动更新",
    },
    holdingRows: [],
    holdingsState: { kind: "empty", label: "重仓券暂无数据" },
    assetDistribution: [],
    assetDistributionState: baseState,
    ratingDistribution: [],
    ratingDistributionState: baseState,
    maturityDistribution: [],
    maturityDistributionState: { kind: "empty", label: "久期分布暂无数据" },
    industryDistribution: [],
    industryDistributionState: { kind: "error", label: "行业分布加载失败" },
    riskExposureMetrics: [],
    riskExposureState: { kind: "empty", label: "风险指标暂无数据" },
    positionChanges: [],
    positionChangesState: { kind: "error", label: "增减仓加载失败" },
    researchReports: [],
    researchReportsState: { kind: "error", label: "研究报告加载失败" },
    incomeTrend: [],
    incomeTrendState: { kind: "partial", label: "缺 CDB_INDEX 可核验曲线" },
    ...overrides,
  };
}

describe("DashboardHomePage", () => {
  it("renders the home shell while snapshot query is unresolved", async () => {
    const base = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const slowClient: ApiClient = {
      ...base,
      getHomeSnapshot: async () => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return base.getHomeSnapshot();
      },
    };

    renderDashboardHome(slowClient);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    expect(await screen.findByTestId("workbench-group-nav")).toBeInTheDocument();
    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
  });

  it("keeps event feeds behind a separate idle gate after body detail data", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEvents = vi.fn(async (options) =>
      mockSnapshotSource.getChoiceNewsEvents(options),
    );
    const getHomeIncomeTrend = vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
      mockSnapshotSource.getHomeIncomeTrend(...args),
    );
    const getBondAnalyticsTopHoldings = vi.fn(
      async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
      mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
    );
    const getBondAnalyticsPositionChanges = vi.fn(
      async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
      mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEvents,
      getHomeIncomeTrend,
      getBondAnalyticsTopHoldings,
      getBondAnalyticsPositionChanges,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    expect(getResearchCalendarEvents).not.toHaveBeenCalled();
    expect(getChoiceNewsEvents).not.toHaveBeenCalled();
    expect(getHomeIncomeTrend).not.toHaveBeenCalled();

    releaseSnapshot?.();
    await runNextIdle(idle);
    await waitForBodyAutoRevealDelay();
    await runNextIdle(idle);
    expect(getResearchCalendarEvents).not.toHaveBeenCalled();
    expect(getChoiceNewsEvents).not.toHaveBeenCalled();
    expect(getHomeIncomeTrend).not.toHaveBeenCalled();

    await waitForBodyDetailDataDelay();
    await runNextIdle(idle);
    await waitFor(() => {
      expect(getBondAnalyticsTopHoldings).toHaveBeenCalled();
    });
    expect(getResearchCalendarEvents).not.toHaveBeenCalled();
    expect(getChoiceNewsEvents).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(getHomeIncomeTrend).toHaveBeenCalled();
    });

    await waitForEventFeedDataDelay();
    await runNextIdle(idle);
    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
      expect(getChoiceNewsEvents).toHaveBeenCalled();
    });
    expect(requestedNewsTopicCodes(getChoiceNewsEvents)).toEqual([
      DASHBOARD_MACRO_NEWS_TOPICS[0].code,
    ]);
    expect(requestedNewsTopicCodes(getChoiceNewsEvents)).not.toEqual(
      expect.arrayContaining([
        ...DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code),
        ...DASHBOARD_BOND_NEWS_TOPICS.map((topic) => topic.code),
      ]),
    );

    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEvents)).toEqual(
        DASHBOARD_MACRO_NEWS_TOPICS.map((topic) => topic.code),
      );
    });
    expect(requestedNewsTopicCodes(getChoiceNewsEvents)).not.toEqual(
      expect.arrayContaining([
        ...DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code),
        ...DASHBOARD_BOND_NEWS_TOPICS.map((topic) => topic.code),
      ]),
    );

    await waitForSecondaryEventFeedDataDelay();
    await runNextIdle(idle);
    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEvents)).toEqual([
        ...DASHBOARD_MACRO_NEWS_TOPICS.map((topic) => topic.code),
        ...DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code),
        ...bondNewsTopicCodesExcludingFallbackTopics(),
      ]);
    });
  });

  it("skips macro fallback news when Choice macro news is fresh and usable", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEvents = vi.fn(async (options: Parameters<ApiClient["getChoiceNewsEvents"]>[0]) => {
      if (DASHBOARD_MACRO_NEWS_TOPICS.some((topic) => topic.code === options.topicCode)) {
        return choiceNewsEnvelope([
          choiceNewsEvent({
            topic_code: options.topicCode,
            payload_text: "资金面维持平稳，DR007 小幅回落。",
          }),
        ]);
      }
      return mockSnapshotSource.getChoiceNewsEvents(options);
    });
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEvents,
      getHomeIncomeTrend: vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
        mockSnapshotSource.getHomeIncomeTrend(...args),
      ),
      getBondAnalyticsTopHoldings: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
          mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
      ),
      getBondAnalyticsPositionChanges: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
          mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
      ),
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    await revealHomeBodyDetailAndEventFeeds(idle);

    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEvents)).toEqual([
        ...DASHBOARD_MACRO_NEWS_TOPICS.map((topic) => topic.code),
        ...bondNewsTopicCodesExcludingFallbackTopics(),
      ]);
    });
    expect(requestedNewsTopicCodes(getChoiceNewsEvents)).not.toEqual(
      expect.arrayContaining(DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code)),
    );
    expect(getResearchCalendarEvents).toHaveBeenCalled();
  });

  it("short-circuits the remaining Choice macro topics when the probe reports missing permission", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEvents = vi.fn(async (options: Parameters<ApiClient["getChoiceNewsEvents"]>[0]) => {
      if (options.topicCode === DASHBOARD_MACRO_NEWS_TOPICS[0].code) {
        return choiceNewsEnvelope([
          choiceNewsEvent({
            event_key: "choice-permission-error",
            topic_code: options.topicCode,
            error_code: 10001012,
            error_msg: "insufficient user access",
            payload_text: null,
          }),
        ]);
      }
      return mockSnapshotSource.getChoiceNewsEvents(options);
    });
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEvents,
      getHomeIncomeTrend: vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
        mockSnapshotSource.getHomeIncomeTrend(...args),
      ),
      getBondAnalyticsTopHoldings: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
          mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
      ),
      getBondAnalyticsPositionChanges: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
          mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
      ),
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    await revealHomeBodyDetailAndEventFeeds(idle);

    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEvents)).toEqual([
        DASHBOARD_MACRO_NEWS_TOPICS[0].code,
        ...DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code),
        ...bondNewsTopicCodesExcludingFallbackTopics(),
      ]);
    });
    expect(requestedNewsTopicCodes(getChoiceNewsEvents)).not.toEqual(
      expect.arrayContaining(DASHBOARD_MACRO_NEWS_TOPICS.slice(1).map((topic) => topic.code)),
    );
    expect(getResearchCalendarEvents).toHaveBeenCalled();
  });

  it("loads macro fallback news when the Choice probe request fails", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEvents = vi.fn(async (options: Parameters<ApiClient["getChoiceNewsEvents"]>[0]) => {
      if (options.topicCode === DASHBOARD_MACRO_NEWS_TOPICS[0].code) {
        throw new Error("choice probe unavailable");
      }
      return mockSnapshotSource.getChoiceNewsEvents(options);
    });
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEvents,
      getHomeIncomeTrend: vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
        mockSnapshotSource.getHomeIncomeTrend(...args),
      ),
      getBondAnalyticsTopHoldings: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
          mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
      ),
      getBondAnalyticsPositionChanges: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
          mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
      ),
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    await revealHomeBodyDetailAndEventFeeds(idle);

    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEvents)).toEqual(
        expect.arrayContaining([
          DASHBOARD_MACRO_NEWS_TOPICS[0].code,
          ...DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code),
        ]),
      );
    });
    expect(requestedNewsTopicCodes(getChoiceNewsEvents)).not.toEqual(
      expect.arrayContaining(DASHBOARD_MACRO_NEWS_TOPICS.slice(1).map((topic) => topic.code)),
    );
    expect(getResearchCalendarEvents).toHaveBeenCalled();
  });

  it("does not request the shared fallback news topic twice for bond news", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEvents = vi.fn(async (options: Parameters<ApiClient["getChoiceNewsEvents"]>[0]) => {
      if (options.topicCode === DASHBOARD_MACRO_NEWS_TOPICS[0].code) {
        return choiceNewsEnvelope([
          choiceNewsEvent({
            event_key: "choice-permission-error",
            topic_code: options.topicCode,
            error_code: 10001012,
            error_msg: "insufficient user access",
            payload_text: null,
          }),
        ]);
      }
      return mockSnapshotSource.getChoiceNewsEvents(options);
    });
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEvents,
      getHomeIncomeTrend: vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
        mockSnapshotSource.getHomeIncomeTrend(...args),
      ),
      getBondAnalyticsTopHoldings: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
          mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
      ),
      getBondAnalyticsPositionChanges: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
          mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
      ),
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    await revealHomeBodyDetailAndEventFeeds(idle);

    await waitFor(() => {
      expect(requestedNewsTopicCount(getChoiceNewsEvents, "tushare.npr")).toBe(1);
    });
    expect(requestedNewsTopicCodes(getChoiceNewsEvents)).toEqual(
      expect.arrayContaining([
        DASHBOARD_MACRO_NEWS_TOPICS[0].code,
        ...DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code),
      ]),
    );
  });

  it("stops bond news topic loading when the bond probe is empty", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEvents = vi.fn(async (options: Parameters<ApiClient["getChoiceNewsEvents"]>[0]) => {
      if (options.topicCode === DASHBOARD_MACRO_NEWS_TOPICS[0].code) {
        return choiceNewsEnvelope([
          choiceNewsEvent({
            event_key: "choice-permission-error",
            topic_code: options.topicCode,
            error_code: 10001012,
            error_msg: "insufficient user access",
            payload_text: null,
          }),
        ]);
      }
      if (options.topicCode === bondNewsProbeTopicCode()) {
        return choiceNewsEnvelope([]);
      }
      return mockSnapshotSource.getChoiceNewsEvents(options);
    });
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEvents,
      getHomeIncomeTrend: vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
        mockSnapshotSource.getHomeIncomeTrend(...args),
      ),
      getBondAnalyticsTopHoldings: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
          mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
      ),
      getBondAnalyticsPositionChanges: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
          mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
      ),
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    await revealHomeBodyDetailAndEventFeeds(idle);

    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEvents)).toEqual([
        DASHBOARD_MACRO_NEWS_TOPICS[0].code,
        ...DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code),
        bondNewsProbeTopicCode(),
      ]);
    });
    expect(requestedNewsTopicCodes(getChoiceNewsEvents)).not.toEqual(
      expect.arrayContaining(remainingBondNewsTopicCodesAfterProbe()),
    );
  });

  it("loads remaining bond news topics when the bond probe has rows", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const getChoiceNewsEvents = vi.fn(async (options: Parameters<ApiClient["getChoiceNewsEvents"]>[0]) => {
      if (options.topicCode === DASHBOARD_MACRO_NEWS_TOPICS[0].code) {
        return choiceNewsEnvelope([
          choiceNewsEvent({
            event_key: "choice-permission-error",
            topic_code: options.topicCode,
            error_code: 10001012,
            error_msg: "insufficient user access",
            payload_text: null,
          }),
        ]);
      }
      if (options.topicCode === bondNewsProbeTopicCode()) {
        return choiceNewsEnvelope([
          choiceNewsEvent({
            event_key: "bond-probe-hit",
            topic_code: options.topicCode,
            payload_text: "债券市场收益率曲线下行，资金面保持宽松。",
          }),
        ]);
      }
      return mockSnapshotSource.getChoiceNewsEvents(options);
    });
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getResearchCalendarEvents,
      getChoiceNewsEvents,
      getHomeIncomeTrend: vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) =>
        mockSnapshotSource.getHomeIncomeTrend(...args),
      ),
      getBondAnalyticsTopHoldings: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) =>
          mockSnapshotSource.getBondAnalyticsTopHoldings(...args),
      ),
      getBondAnalyticsPositionChanges: vi.fn(
        async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
          mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
      ),
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    releaseSnapshot?.();
    await revealHomeBodyDetailAndEventFeeds(idle);

    await waitFor(() => {
      expect(requestedNewsTopicCodes(getChoiceNewsEvents)).toEqual([
        DASHBOARD_MACRO_NEWS_TOPICS[0].code,
        ...DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code),
        ...bondNewsTopicCodesExcludingFallbackTopics(),
      ]);
    });
  });

  it("starts only first-screen hydration queries after the first idle gate", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();

    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...base,
      ...supplementalCalls,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    for (const spy of Object.values(supplementalCalls)) {
      expect(spy).not.toHaveBeenCalled();
    }

    await act(async () => {
      releaseSnapshot?.();
    });
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });
    for (const spy of Object.values(supplementalCalls)) {
      expect(spy).not.toHaveBeenCalled();
    }

    await runNextIdle(idle);
    await waitFor(() => {
      expect(supplementalCalls.getBondDashboardHeadlineKpis).toHaveBeenCalledTimes(1);
      expect(supplementalCalls.getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getMarketDataRates).not.toHaveBeenCalled();
    expect(supplementalCalls.getCoreMetrics).not.toHaveBeenCalled();
    expect(supplementalCalls.getDailyChanges).not.toHaveBeenCalled();
    expect(supplementalCalls.getBondAnalyticsTopHoldings).not.toHaveBeenCalled();
    expect(supplementalCalls.getHomeIncomeTrend).not.toHaveBeenCalled();
    expect(supplementalCalls.getResearchCalendarEvents).not.toHaveBeenCalled();
    expect(supplementalCalls.getChoiceNewsEvents).not.toHaveBeenCalled();
    expect(supplementalCalls.getBalanceAnalysisDecisionItems).not.toHaveBeenCalled();

    await waitForBodyAutoRevealDelay();
    await runNextIdle(idle);
    await waitFor(() => {
      expect(supplementalCalls.getMarketDataRates).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getCoreMetrics).not.toHaveBeenCalled();
    expect(supplementalCalls.getDailyChanges).not.toHaveBeenCalled();
    expect(supplementalCalls.getBalanceAnalysisDecisionItems).not.toHaveBeenCalled();
    expect(supplementalCalls.getBondAnalyticsTopHoldings).not.toHaveBeenCalled();
    expect(supplementalCalls.getHomeIncomeTrend).not.toHaveBeenCalled();
    expect(supplementalCalls.getResearchCalendarEvents).not.toHaveBeenCalled();
    expect(supplementalCalls.getChoiceNewsEvents).not.toHaveBeenCalled();
    expect(supplementalCalls.getBondDashboardAssetStructure).not.toHaveBeenCalled();
    expect(supplementalCalls.getBondDashboardHeadlineKpis).toHaveBeenCalledTimes(1);
    expect(supplementalCalls.getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledTimes(1);

    await waitForBodyDetailDataDelay();
    await runNextIdle(idle);
    await waitFor(() => {
      expect(supplementalCalls.getBondAnalyticsTopHoldings).toHaveBeenCalled();
      expect(supplementalCalls.getBondDashboardHomeSummary).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getBondDashboardHomeSummary).toHaveBeenCalledWith("2026-04-18");
    expect(supplementalCalls.getBondDashboardAssetStructure).not.toHaveBeenCalled();
    expect(supplementalCalls.getBondDashboardMaturityStructure).not.toHaveBeenCalled();
    expect(supplementalCalls.getBondDashboardIndustryDistribution).not.toHaveBeenCalled();
    expect(supplementalCalls.getBondDashboardRiskIndicators).not.toHaveBeenCalled();
    expect(supplementalCalls.getResearchCalendarEvents).not.toHaveBeenCalled();
    expect(supplementalCalls.getChoiceNewsEvents).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(supplementalCalls.getHomeIncomeTrend).toHaveBeenCalled();
    });

    await waitForEventFeedDataDelay();
    await runNextIdle(idle);
    await waitFor(() => {
      expect(supplementalCalls.getResearchCalendarEvents).toHaveBeenCalled();
      expect(supplementalCalls.getChoiceNewsEvents).toHaveBeenCalled();
    });
  });

  it("keeps first-screen supplemental hydration behind the deferred content reveal delay", async () => {
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...supplementalCalls,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 500));
    });

    expect(idle.pendingCount()).toBe(0);
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();
    expect(supplementalCalls.getBondAnalyticsPortfolioHeadlines).not.toHaveBeenCalled();
    expect(supplementalCalls.getMarketDataRates).not.toHaveBeenCalled();

    await waitForDeferredHomeContentDelay();
    await runNextIdle(idle);

    await waitFor(() => {
      expect(supplementalCalls.getBondDashboardHeadlineKpis).toHaveBeenCalledTimes(1);
      expect(supplementalCalls.getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getMarketDataRates).not.toHaveBeenCalled();
  });

  it("starts deferred content immediately when the user reaches below-fold content", async () => {
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...supplementalCalls,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 100));
    });
    expect(idle.pendingCount()).toBe(0);
    expect(supplementalCalls.getBondDashboardHeadlineKpis).not.toHaveBeenCalled();

    await act(async () => {
      fireEvent.scroll(window);
    });

    await waitFor(() => {
      expect(supplementalCalls.getBondDashboardHeadlineKpis).toHaveBeenCalledTimes(1);
      expect(supplementalCalls.getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();
    expect(supplementalCalls.getMarketDataRates).toHaveBeenCalledTimes(1);
  });

  it("remembers below-fold reach that happens while the snapshot is still pending", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let releaseSnapshot: (() => void) | undefined;
    const idle = stubIdleCallbacks();
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...base,
      ...supplementalCalls,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    await act(async () => {
      fireEvent.scroll(window);
    });

    await act(async () => {
      releaseSnapshot?.();
    });
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });
    await runNextIdle(idle);

    await waitFor(() => {
      expect(supplementalCalls.getBondDashboardHeadlineKpis).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();
  });

  it("does not reuse an old idle gate for supplemental queries while a new report-date snapshot is pending", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();

    let releaseLatestSnapshot: (() => void) | undefined;
    let releaseNewSnapshot: (() => void) | undefined;
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...base,
      ...supplementalCalls,
      getHomeSnapshot: async (options) => {
        if (options?.reportDate === "2026-03-31") {
          await new Promise<void>((resolve) => {
            releaseNewSnapshot = resolve;
          });
          const envelope = await mockSnapshotSource.getHomeSnapshot(options);
          return {
            ...envelope,
            result: {
              ...envelope.result,
              report_date: options.reportDate,
            },
          };
        }
        await new Promise<void>((resolve) => {
          releaseLatestSnapshot = resolve;
        });
        const envelope = await mockSnapshotSource.getHomeSnapshot(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: options?.reportDate ?? envelope.result.report_date,
          },
        };
      },
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseLatestSnapshot).toBeDefined();
    });

    await act(async () => {
      releaseLatestSnapshot?.();
    });
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });

    const reportDateInput = await screen.findByLabelText("报告日");
    await act(async () => {
      fireEvent.change(reportDateInput, { target: { value: "2026-03-31" } });
    });
    await waitFor(() => {
      expect(releaseNewSnapshot).toBeDefined();
    });

    await act(async () => {
      idle.runPending();
    });
    for (const spy of Object.values(supplementalCalls)) {
      expect(spy).not.toHaveBeenCalled();
    }

    await act(async () => {
      releaseNewSnapshot?.();
    });
    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-page")).toBeInTheDocument();
    });
    for (const spy of Object.values(supplementalCalls)) {
      expect(spy).not.toHaveBeenCalled();
    }
  });

  it("does not keep formal supplemental queries enabled while a new report-date snapshot is pending", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();

    let releaseNewSnapshot: (() => void) | undefined;
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...base,
      ...supplementalCalls,
      getHomeSnapshot: async (options) => {
        if (options?.reportDate === "2026-03-31") {
          await new Promise<void>((resolve) => {
            releaseNewSnapshot = resolve;
          });
        }
        const envelope = await mockSnapshotSource.getHomeSnapshot(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: options?.reportDate ?? envelope.result.report_date,
          },
        };
      },
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await runNextIdle(idle);
    expect(supplementalCalls.getHomeIncomeTrend).not.toHaveBeenCalled();
    expect(supplementalCalls.getCockpitWarnings).not.toHaveBeenCalled();

    await waitForBodyAutoRevealDelay();
    await runNextIdle(idle);
    expect(supplementalCalls.getHomeIncomeTrend).not.toHaveBeenCalled();
    expect(supplementalCalls.getCockpitWarnings).not.toHaveBeenCalled();

    await waitForBodyDetailDataDelay();
    await runNextIdle(idle);
    await waitFor(() => {
      expect(supplementalCalls.getHomeIncomeTrend).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getCockpitWarnings).not.toHaveBeenCalled();

    const incomeTrendCallsBeforeSwitch = supplementalCalls.getHomeIncomeTrend.mock.calls.length;
    const cockpitWarningCallsBeforeSwitch = supplementalCalls.getCockpitWarnings.mock.calls.length;
    const reportDateInput = await screen.findByLabelText("报告日");
    await act(async () => {
      fireEvent.change(reportDateInput, { target: { value: "2026-03-31" } });
    });
    await waitFor(() => {
      expect(releaseNewSnapshot).toBeDefined();
    });
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(supplementalCalls.getHomeIncomeTrend).toHaveBeenCalledTimes(incomeTrendCallsBeforeSwitch);
    expect(supplementalCalls.getCockpitWarnings).toHaveBeenCalledTimes(cockpitWarningCallsBeforeSwitch);

    await act(async () => {
      releaseNewSnapshot?.();
    });
  });

  it("does not start supplemental queries when a requested report-date snapshot fails without prior data", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();

    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...base,
      ...supplementalCalls,
      getHomeSnapshot: async () => {
        throw new Error("snapshot unavailable");
      },
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    const reportDateInput = await screen.findByLabelText("报告日");
    await act(async () => {
      fireEvent.change(reportDateInput, { target: { value: "2026-03-31" } });
    });
    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-hero")).toBeInTheDocument();
    });
    await act(async () => {
      idle.runPending();
    });
    await new Promise((resolve) => setTimeout(resolve, 50));

    for (const spy of Object.values(supplementalCalls)) {
      expect(spy).not.toHaveBeenCalled();
    }
  });

  it("waits to request income trend until heavy bond lists have settled", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    let releaseSnapshot: (() => void) | undefined;
    let releaseTopHoldings: (() => void) | undefined;
    let releaseIncomeTrend: (() => void) | undefined;
    const getBondAnalyticsTopHoldings = vi.fn(async (...args: Parameters<ApiClient["getBondAnalyticsTopHoldings"]>) => {
      await new Promise<void>((resolve) => {
        releaseTopHoldings = resolve;
      });
      return mockSnapshotSource.getBondAnalyticsTopHoldings(...args);
    });
    const getBondAnalyticsPositionChanges = vi.fn(
      async (...args: Parameters<ApiClient["getBondAnalyticsPositionChanges"]>) =>
      mockSnapshotSource.getBondAnalyticsPositionChanges(...args),
    );
    const getHomeIncomeTrend = vi.fn(async (...args: Parameters<ApiClient["getHomeIncomeTrend"]>) => {
      await new Promise<void>((resolve) => {
        releaseIncomeTrend = resolve;
      });
      return mockSnapshotSource.getHomeIncomeTrend(...args);
    });
    const getBondAnalyticsReturnDecomposition = vi.fn(mockSnapshotSource.getBondAnalyticsReturnDecomposition);
    const getPnlCampisiFourEffects = vi.fn(mockSnapshotSource.getPnlCampisiFourEffects);
    const getBondAnalyticsYieldCurveTermStructure = vi.fn(
      mockSnapshotSource.getBondAnalyticsYieldCurveTermStructure,
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        await new Promise<void>((resolve) => {
          releaseSnapshot = resolve;
        });
        return mockSnapshotSource.getHomeSnapshot(...args);
      },
      getBondAnalyticsTopHoldings,
      getBondAnalyticsPositionChanges,
      getHomeIncomeTrend,
      getBondAnalyticsReturnDecomposition,
      getPnlCampisiFourEffects,
      getBondAnalyticsYieldCurveTermStructure,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(releaseSnapshot).toBeDefined();
    });
    expect(idle.pendingCount()).toBe(0);
    await act(async () => {
      releaseSnapshot?.();
    });
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });
    expect(getBondAnalyticsTopHoldings).not.toHaveBeenCalled();
    expect(getHomeIncomeTrend).not.toHaveBeenCalled();

    await act(async () => {
      idle.runPending();
    });
    expect(getBondAnalyticsTopHoldings).not.toHaveBeenCalled();
    expect(getHomeIncomeTrend).not.toHaveBeenCalled();

    await waitForBodyAutoRevealDelay();
    await runNextIdle(idle);
    expect(getBondAnalyticsTopHoldings).not.toHaveBeenCalled();
    expect(getHomeIncomeTrend).not.toHaveBeenCalled();

    await waitForBodyDetailDataDelay();
    await runNextIdle(idle);
    await waitFor(() => {
      expect(getBondAnalyticsTopHoldings).toHaveBeenCalled();
      expect(releaseTopHoldings).toBeDefined();
    });
    expect(getHomeIncomeTrend).not.toHaveBeenCalled();
    expect(getBondAnalyticsReturnDecomposition).not.toHaveBeenCalled();
    expect(getPnlCampisiFourEffects).not.toHaveBeenCalled();
    expect(getBondAnalyticsYieldCurveTermStructure).not.toHaveBeenCalled();

    releaseTopHoldings?.();
    await waitFor(() => {
      expect(getHomeIncomeTrend).toHaveBeenCalled();
      expect(releaseIncomeTrend).toBeDefined();
      expect(getBondAnalyticsReturnDecomposition).toHaveBeenCalled();
      expect(getPnlCampisiFourEffects).toHaveBeenCalled();
      expect(getBondAnalyticsYieldCurveTermStructure).toHaveBeenCalled();
    });

    releaseIncomeTrend?.();
  });

  it("does not refetch market tape when only the snapshot report date resolves", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMarketDataRates = vi.fn(base.getMarketDataRates);
    const client: ApiClient = {
      ...base,
      getMarketDataRates,
    };

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMarketDataRates).toHaveBeenCalledTimes(1);
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 100));
    });
    expect(getMarketDataRates).toHaveBeenCalledTimes(1);
  });

  it("uses mock-shaped first-screen content when the app is not using real APIs", async () => {
    renderDashboardHome();

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    const hero = await screen.findByTestId("dashboard-home-hero");
    expect(within(hero).getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("3,708.10");
  });

  it("does not request excluded executive surfaces from the home page", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    let riskCalls = 0;
    let contributionCalls = 0;
    let alertsCalls = 0;

    const guardedClient: ApiClient = {
      ...base,
      getHomeSnapshot: (...args) => mockSnapshotSource.getHomeSnapshot(...args),
      getRiskOverview: async () => {
        riskCalls += 1;
        throw new Error("risk-overview should not be requested");
      },
      getContribution: async () => {
        contributionCalls += 1;
        throw new Error("contribution should not be requested");
      },
      getAlerts: async () => {
        alertsCalls += 1;
        throw new Error("alerts should not be requested");
      },
    };

    renderDashboardHome(guardedClient);

    expect(await screen.findByTestId("dashboard-home-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(riskCalls).toBe(0);
      expect(contributionCalls).toBe(0);
      expect(alertsCalls).toBe(0);
    });
  });

  it("prefers real first-screen values over local fallback", async () => {
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const getHomeSnapshot = vi.fn(async (options) => {
      const envelope = await mockSnapshotSource.getHomeSnapshot(options);
      return {
        ...envelope,
        result_meta: {
          ...envelope.result_meta,
          generated_at: "2026-04-30T10:45:00+08:00",
        },
        result: {
          ...envelope.result,
          report_date: "2026-04-30",
          overview: {
            ...envelope.result.overview,
            metrics: [
              {
                id: "aum",
                label: "债券资产规模",
                caliber_label: "真实接口口径",
                value: {
                  raw: 4_567_890_000_000,
                  unit: "yuan" as const,
                  display: "4,567.89 亿",
                  precision: 2,
                  sign_aware: false,
                },
                delta: {
                  raw: 12_300_000_000,
                  unit: "yuan" as const,
                  display: "+12.30 亿",
                  precision: 2,
                  sign_aware: true,
                },
                tone: "positive" as const,
                detail: "测试真实接口返回值。",
              },
            ],
          },
        },
      };
    });
    const client = createRealModeHomeClient({
      getHomeSnapshot,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderDashboardHome(client);

    const hero = await screen.findByTestId("dashboard-home-hero");
    await waitFor(() => {
      expect(getHomeSnapshot).toHaveBeenCalled();
      expect(within(hero).getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("4,567.89");
    });
  });

  it("hydrates first-screen KPI cards from deferred supplemental data after idle work starts", async () => {
    const base = createApiClient({ mode: "real" });
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    const yuan = (raw: number, display: string, signAware = false) => ({
      raw,
      unit: "yuan" as const,
      display,
      precision: 2,
      sign_aware: signAware,
    });
    const ratio = (raw: number, display: string) => ({
      raw,
      unit: "ratio" as const,
      display,
      precision: 2,
      sign_aware: false,
    });
    const pct = (raw: number, display: string) => ({
      raw,
      unit: "pct" as const,
      display,
      precision: 2,
      sign_aware: false,
    });
    const getBondDashboardHeadlineKpis = vi.fn<ApiClient["getBondDashboardHeadlineKpis"]>(
      async () => ({
        result_meta: {
          result_kind: "bond_dashboard.headline_kpis",
          trace_id: "tr_home_headline",
          basis: "formal",
          formal_use_allowed: true,
          source_version: "sv_home_headline_test",
          vendor_version: "vv_none",
          rule_version: "rv_home_headline_test",
          cache_version: "cv_home_headline_test",
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: "2026-04-30T10:45:00+08:00",
          tables_used: ["bond_position_daily"],
        },
        result: {
          report_date: "2026-04-30",
          prev_report_date: "2026-04-29",
          kpis: {
            total_market_value: yuan(328_709_000_000, "3,287.09 亿"),
            unrealized_pnl: yuan(1_842_000_000, "+18.42 亿", true),
            weighted_ytm: pct(0.0285, "2.85%"),
            weighted_duration: ratio(4.23, "4.23"),
            weighted_coupon: pct(0.031, "3.10%"),
            credit_spread_median: {
              raw: 72,
              unit: "bp" as const,
              display: "72bp",
              precision: 2,
              sign_aware: false,
            },
            total_dv01: {
              raw: 120_000,
              unit: "dv01" as const,
              display: "120,000.00",
              precision: 2,
              sign_aware: false,
            },
            bond_count: 128,
          },
          prev_kpis: {
            total_market_value: yuan(320_000_000_000, "3,200.00 亿"),
            unrealized_pnl: yuan(1_700_000_000, "+17.00 亿", true),
            weighted_ytm: pct(0.0281, "2.81%"),
            weighted_duration: ratio(4.18, "4.18"),
            weighted_coupon: pct(0.0308, "3.08%"),
            credit_spread_median: {
              raw: 75,
              unit: "bp" as const,
              display: "75bp",
              precision: 2,
              sign_aware: false,
            },
            total_dv01: {
              raw: 118_000,
              unit: "dv01" as const,
              display: "118,000.00",
              precision: 2,
              sign_aware: false,
            },
            bond_count: 128,
          },
        },
      }),
    );
    const client = createRealModeHomeClient({
      ...base,
      getHomeSnapshot: async (...args) => {
        const envelope = await mockSnapshotSource.getHomeSnapshot(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-04-30",
          },
        };
      },
      getBondDashboardHeadlineKpis,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderDashboardHome(client);

    const hero = await screen.findByTestId("dashboard-home-hero");
    expect(within(hero).getByTestId("dashboard-home-kpi-bond-market-value")).toHaveTextContent("—");
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });

    await act(async () => {
      idle.runPending();
    });

    await waitFor(() => {
      expect(getBondDashboardHeadlineKpis).toHaveBeenCalledWith("2026-04-30");
      expect(within(hero).getByTestId("dashboard-home-kpi-bond-market-value")).toHaveTextContent("3,287.09");
      expect(within(hero).getByTestId("dashboard-home-kpi-unrealized-pnl")).toHaveTextContent("+18.42");
      expect(within(hero).getByTestId("dashboard-home-kpi-duration")).toHaveTextContent("4.23");
      expect(within(hero).getByTestId("dashboard-home-kpi-ytm")).toHaveTextContent("2.85");
    });
  });

  it("keeps below-fold home body behind a second idle gate after supplemental hydration starts", async () => {
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...supplementalCalls,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });

    await act(async () => {
      idle.runPending();
    });

    await waitFor(() => {
      expect(supplementalCalls.getBondDashboardHeadlineKpis).toHaveBeenCalledTimes(1);
      expect(supplementalCalls.getBondAnalyticsPortfolioHeadlines).toHaveBeenCalledTimes(1);
    });
    expect(supplementalCalls.getMarketDataRates).not.toHaveBeenCalled();
    expect(screen.queryByTestId("dashboard-home-work-grid")).not.toBeInTheDocument();
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 1_000));
    });
    expect(idle.pendingCount()).toBe(0);

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 1_200));
    });
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });

    await act(async () => {
      idle.runPending();
    });

    expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();
    await waitFor(() => {
      expect(supplementalCalls.getMarketDataRates).toHaveBeenCalledTimes(1);
    });
  });

  it("loads below-fold home body immediately when the user reaches deferred content", async () => {
    const mockSnapshotSource = createApiClient({ mode: "mock" });
    const idle = stubIdleCallbacks();
    const supplementalCalls = createSupplementalHomeSpies(mockSnapshotSource);
    const client = createRealModeHomeClient({
      ...supplementalCalls,
    });

    renderDashboardHome(client);

    expect(await screen.findByTestId("dashboard-home-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });

    await act(async () => {
      idle.runPending();
    });

    await waitFor(() => {
      expect(supplementalCalls.getBondDashboardHeadlineKpis).toHaveBeenCalledTimes(1);
    });
    expect(screen.queryByTestId("dashboard-home-work-grid")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(idle.pendingCount()).toBeGreaterThan(0);
    });

    await act(async () => {
      fireEvent.scroll(window);
    });

    expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();
  });

  it("renders terminal holdings and newly landed home backend blocks", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>(async (options) => {
      const envelope = await mockSource.getHomeSnapshot(options);
      return {
        ...envelope,
        result: {
          ...envelope.result,
          report_date: "2026-04-30",
        },
      };
    });
    const yuan = (raw: number, display: string) => ({
      raw,
      unit: "yuan" as const,
      display,
      precision: 2,
      sign_aware: false,
    });
    const ratio = (raw: number, display: string) => ({
      raw,
      unit: "ratio" as const,
      display,
      precision: 2,
      sign_aware: false,
    });
    const pct = (raw: number, display: string) => ({
      raw,
      unit: "pct" as const,
      display,
      precision: 2,
      sign_aware: false,
    });
    const signedYuan = (raw: number, display: string) => ({
      raw,
      unit: "yuan" as const,
      display,
      precision: 2,
      sign_aware: true,
    });
    const missingYuan = {
      raw: null,
      unit: "yuan" as const,
      display: "-",
      precision: 2,
      sign_aware: true,
    };
    const getBondAnalyticsTopHoldings = vi.fn<ApiClient["getBondAnalyticsTopHoldings"]>(
      async (...args) => {
        const envelope = await mockSource.getBondAnalyticsTopHoldings(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            items: [
              {
                instrument_code: "240001.IB",
                instrument_name: "测试国债01",
                issuer_name: "财政部",
                rating: "AAA",
                asset_class: "利率债",
                market_value: yuan(12_350_000_000, "123.50 亿"),
                face_value: yuan(12_000_000_000, "120.00 亿"),
                ytm: pct(0.0236, "2.36%"),
                modified_duration: ratio(4.21, "4.21"),
                weight: pct(0.0961, "9.61%"),
              },
            ],
          },
        };
      },
    );
    const getBondAnalyticsPositionChanges = vi.fn<ApiClient["getBondAnalyticsPositionChanges"]>(
      async (...args) => {
        const envelope = await mockSource.getBondAnalyticsPositionChanges(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-04-30",
            prev_report_date: "2026-04-29",
            source_status: "ready",
            items: [
              {
                instrument_code: "240002.IB",
                instrument_name: "测试增持债",
                issuer_name: "财政部",
                rating: "AAA",
                asset_class: "rate",
                previous_market_value: yuan(10_000_000_000, "100.00 亿"),
                current_market_value: yuan(13_000_000_000, "130.00 亿"),
                change_market_value: signedYuan(3_000_000_000, "+30.00 亿"),
                previous_weight: ratio(0.08, "8.00%"),
                current_weight: ratio(0.1, "10.00%"),
                change_weight: ratio(0.02, "+2.00pp"),
                direction: "increase" as const,
                reason_label: "增持",
                source_status: "ready" as const,
              },
            ],
          },
        };
      },
    );
    const getHomeResearchReports = vi.fn<ApiClient["getHomeResearchReports"]>(
      async (...args) => {
        const envelope = await mockSource.getHomeResearchReports(...args);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            report_date: "2026-04-30",
            source_status: "ready",
            items: [
              {
                id: "research-1",
                title: "利率债周报",
                category: "fixed_income",
                published_at: "2026-04-29T09:00:00",
                link: "https://example.com/report.pdf",
                source: "tushare_research",
                source_status: "ready" as const,
                summary: "关注久期和曲线",
              },
            ],
          },
        };
      },
    );
    const getHomeIncomeTrend = vi.fn<ApiClient["getHomeIncomeTrend"]>(
      async (reportDate, window = 7) => {
        const envelope = await mockSource.getHomeSnapshot({ reportDate });
        return {
          ...envelope,
          result_meta: {
            ...envelope.result_meta,
            result_kind: "home.income_trend",
          },
          result: {
            report_date: "2026-04-30",
            window,
            source_status: "partial",
            missing_components: ["benchmark_pnl", "excess_pnl"],
            warnings: ["Benchmark and excess PnL are not available."],
            points: [
              {
                date: "2026-03-31",
                portfolio_pnl: signedYuan(120_000_000, "+1.20 yi"),
                benchmark_pnl: missingYuan,
                excess_pnl: missingYuan,
                basis: "product_category_pnl_monthly" as const,
                source_status: "partial" as const,
              },
              {
                date: "2026-04-30",
                portfolio_pnl: signedYuan(90_000_000, "+0.90 yi"),
                benchmark_pnl: missingYuan,
                excess_pnl: missingYuan,
                basis: "product_category_pnl_monthly" as const,
                source_status: "partial" as const,
              },
            ],
          },
        };
      },
    );
    const client = createRealModeHomeClient({
      getHomeSnapshot,
      getBondAnalyticsTopHoldings,
      getBondAnalyticsPositionChanges,
      getHomeResearchReports,
      getHomeIncomeTrend,
      getResearchCalendarEvents: vi.fn(async () => []),
    });
    const idle = stubIdleCallbacks();

    renderDashboardHome(client);
    await revealHomeBodyDetailAndEventFeeds(idle);

    await waitFor(() => {
      expect(getBondAnalyticsTopHoldings).toHaveBeenCalledWith(
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        8,
      );
      expect(getBondAnalyticsPositionChanges).toHaveBeenCalledWith(
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        5,
      );
      expect(getHomeResearchReports).toHaveBeenCalledWith(
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        5,
      );
      expect(getHomeIncomeTrend).toHaveBeenCalledWith(
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        7,
      );
    });
    await waitFor(() => {
      const holdingsTable = screen.getByTestId("dashboard-home-holdings-table");
      expect(within(holdingsTable).getAllByTestId("dashboard-home-holding-row").length).toBeGreaterThan(0);
    });
    const positionChanges = await screen.findByTestId("dashboard-home-position-changes");
    expect(positionChanges).toHaveTextContent("240002.IB");
    expect(positionChanges).toHaveTextContent("+2.00pp");
    expect(positionChanges).toHaveTextContent("现值");
    const incomeTrend = await screen.findByTestId("dashboard-home-income-trend");
    await waitFor(() => {
      expect(incomeTrend).toHaveTextContent("组合");
      expect(incomeTrend).toHaveTextContent("基准");
      expect(incomeTrend).toHaveTextContent("超额");
      expect(incomeTrend).toHaveTextContent("+1.20");
    });
    expect(await screen.findByTestId("dashboard-home-research-reports")).toHaveTextContent("利率债周报");
    expect(screen.queryByTestId("dashboard-home-backend-gap-research-reports")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-home-backend-gap-position-changes")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-home-backend-gap-income-trend")).not.toBeInTheDocument();
  });

  it("renders compact explicit states instead of blank terminal cards", () => {
    render(
      <MemoryRouter>
        <TerminalHomeContent view={createTerminalStateView()} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-holdings-table")).toHaveTextContent("重仓券暂无数据");
    expect(screen.getByTestId("dashboard-home-position-changes")).toHaveTextContent("增减仓加载失败");
    expect(screen.getByTestId("dashboard-home-research-reports")).toHaveTextContent("研究报告加载失败");
    expect(screen.getByTestId("dashboard-home-income-trend")).toHaveTextContent("缺 CDB_INDEX 可核验曲线");
    expect(screen.getByTestId("dashboard-home-income-trend")).toHaveTextContent("缺少部分受管字段");
    expect(screen.getByTestId("dashboard-home-market-context")).toHaveTextContent("今日市场解释");
    expect(screen.getByTestId("dashboard-home-market-context")).toHaveTextContent("市场温度：中性");
    expect(screen.getByTestId("dashboard-home-market-context")).toHaveTextContent("PnL归因");
    expect(screen.getByTestId("dashboard-home-market-context")).toHaveTextContent("曲线/利率");
    expect(screen.getByTestId("dashboard-home-market-context")).toHaveTextContent("信用利差");
    expect(screen.queryByText("后端工单")).not.toBeInTheDocument();
    expect(screen.queryByText("杠杆率")).not.toBeInTheDocument();
  });

  it("renders income trend as portfolio benchmark and excess context", () => {
    render(
      <MemoryRouter>
        <TerminalHomeContent
          view={createTerminalStateView({
            incomeTrendState: { kind: "ready", label: "已接入" },
            incomeTrend: [
              {
                id: "2026-03-31",
                date: "2026-03-31",
                portfolioPnl: "+1.20 亿",
                benchmarkPnl: "+0.80 亿",
                excessPnl: "+0.40 亿",
                portfolioRaw: 120_000_000,
                benchmarkRaw: 80_000_000,
                excessRaw: 40_000_000,
              },
              {
                id: "2026-04-30",
                date: "2026-04-30",
                portfolioPnl: "+0.90 亿",
                benchmarkPnl: "+0.60 亿",
                excessPnl: "+0.30 亿",
                portfolioRaw: 90_000_000,
                benchmarkRaw: 60_000_000,
                excessRaw: 30_000_000,
              },
            ],
          })}
        />
      </MemoryRouter>,
    );

    const incomeTrend = screen.getByTestId("dashboard-home-income-trend");
    expect(incomeTrend).toHaveTextContent("数据截至 2026-04-30");
    expect(incomeTrend).toHaveTextContent("CDB_INDEX / MoM");
    expect(incomeTrend).toHaveTextContent("组合");
    expect(incomeTrend).toHaveTextContent("CDB基准");
    expect(incomeTrend).toHaveTextContent("超额");
    expect(incomeTrend).toHaveTextContent("基准 +0.60 亿 · 超额 +0.30 亿");
  });
    /*
    expect(screen.getByTestId("dashboard-home-backend-gap-research-reports")).toHaveTextContent(
      "后端待接入",
    );
    expect(screen.getByTestId("dashboard-home-backend-gap-position-changes")).toHaveTextContent(
      "后端待接入",
    );
  });

    */
  it("defers dashboard chart runtime until visible chart regions are reached by user scroll", async () => {
    const observer = stubIntersectionObserver();

    render(
      <MemoryRouter>
        <TerminalHomeContent
          view={createTerminalStateView({
            assetDistributionState: { kind: "ready", label: "ready" },
            assetDistribution: [
              { id: "bond", label: "Bond", value: "90.00", pct: "90.00%", pctRaw: 90 },
              { id: "cash", label: "Cash", value: "10.00", pct: "10.00%", pctRaw: 10 },
            ],
            incomeTrendState: { kind: "ready", label: "ready" },
            incomeTrend: [
              {
                id: "2026-04-30",
                date: "2026-04-30",
                portfolioPnl: "+0.90",
                benchmarkPnl: "+0.60",
                excessPnl: "+0.30",
                portfolioRaw: 90_000_000,
                benchmarkRaw: 60_000_000,
                excessRaw: 30_000_000,
              },
            ],
          })}
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("dashboard-home-income-trend")).toHaveTextContent("CDB_INDEX / MoM");
    expect(observer.observe).toHaveBeenCalled();
    expect(screen.queryByTestId("dashboard-echarts-stub")).not.toBeInTheDocument();

    await act(async () => {
      observer.triggerAll({ isIntersecting: true, intersectionRatio: 1 });
    });
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(screen.queryByTestId("dashboard-echarts-stub")).not.toBeInTheDocument();

    await act(async () => {
      window.dispatchEvent(new Event("scroll"));
    });

    await waitFor(() => {
      expect(screen.getAllByTestId("dashboard-echarts-stub").length).toBeGreaterThan(0);
    });
  });

  it("renders supply and auction calendar items from the research calendar feed", async () => {
    const researchCalendarCalls: Array<{
      reportDate?: string;
      startDate?: string;
      endDate?: string;
    }> = [];
    const client = createRealModeHomeClient({
      getResearchCalendarEvents: async (options) => {
        researchCalendarCalls.push(options ?? {});
        return [
          {
            id: "cal_supply_001",
            date: "2026-04-18",
            title: "国债净融资节奏",
            kind: "supply" as const,
            severity: "medium" as const,
            amount_label: "净融资 180 亿元",
            note: "供给节奏",
          },
          {
            id: "cal_auction_002",
            date: "2026-04-19",
            title: "政策性金融债招标",
            kind: "auction" as const,
            severity: "high" as const,
            amount_label: "420 亿元",
            note: "国开行",
          },
        ];
      },
    });

    renderDashboardHome(client);

    const calendar = await screen.findByTestId("dashboard-home-research-calendar");
    await waitFor(() => {
      expect(calendar).toHaveTextContent("国债净融资节奏");
      expect(calendar).toHaveTextContent("政策性金融债招标");
    });
    expect(calendar).toHaveTextContent("供给/招标：");
    expect(researchCalendarCalls.some((call) => call.startDate && call.endDate)).toBe(true);
  });

  it("keeps an explicit no-data state when the external event feed is empty", async () => {
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => []);
    const mockNewsClient = createApiClient({ mode: "mock" });
    const getChoiceNewsEvents = vi.fn((options) => mockNewsClient.getChoiceNewsEvents(options));
    const client = createRealModeHomeClient({ getResearchCalendarEvents, getChoiceNewsEvents });

    renderDashboardHome(client);
    await revealHomeBodyDetailAndEventFeeds(idle);

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
      expect(getChoiceNewsEvents).toHaveBeenCalled();
    });
    const calendar = await screen.findByTestId("dashboard-home-research-calendar");
    await waitFor(() => {
      expect(calendar).toHaveTextContent("重大信息发布日期前瞻");
      expect(calendar).toHaveTextContent("政策与资金面");
      expect(calendar).toHaveTextContent("来源：Choice 宏观新闻");
      expect(calendar).toHaveTextContent("数据截至");
      expect(calendar).toHaveTextContent("来源状态");
      expect(calendar).toHaveTextContent("刷新：");
      expect(calendar).toHaveTextContent("供给/招标：当前窗口无事件");
      expect(calendar).not.toHaveTextContent("当前窗口暂无供给/招标事件。");
    });
    const topicCodes = getChoiceNewsEvents.mock.calls.map(([options]) => options.topicCode);
    expect(topicCodes).toEqual(
      expect.arrayContaining([
        "S888010007API",
        "S888010003API",
        "S888010005API",
        "S888005004API",
        "C000003006",
        "C000003002",
        "tushare.news",
      ]),
    );
    expect(topicCodes).not.toEqual(
      expect.arrayContaining(["tushare.major", "tushare.npr", "tushare.research"]),
    );
  });

  it("keeps an explicit error state when the external event feed fails", async () => {
    const idle = stubIdleCallbacks();
    const getResearchCalendarEvents = vi.fn(async () => {
      throw new Error("calendar backend unavailable");
    });
    const client = createRealModeHomeClient({ getResearchCalendarEvents });

    renderDashboardHome(client);
    await revealHomeBodyDetailAndEventFeeds(idle);

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
    });
    const calendar = await screen.findByTestId("dashboard-home-research-calendar");
    await waitFor(() => {
      expect(calendar).toHaveTextContent("供给/招标：加载失败");
    });
  });
});
