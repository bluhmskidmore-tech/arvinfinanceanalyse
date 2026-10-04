import { useEffect, useRef, useState, type MouseEvent } from "react";
import { useLocation } from "react-router-dom";
import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";

import { EM_DASH } from "../../../utils/format";
import type {
  ModuleHomeSourceQueries,
  ModuleHomeView,
} from "./moduleHomeModel";
import type { ModuleWorkbenchHomeConfig } from "./moduleHomeConfig";
import { MarketBackendDataWorkbench } from "./MarketBackendDataWorkbench";
import { MarketFinancialChartsWorkbench } from "./MarketFinancialChartsWorkbench";
import { MarketOverviewDenseFirstScreen } from "./MarketOverviewDenseFirstScreen";
import { useMarketChartPalette } from "./marketChartPalette";
import type { MarketFinancialChartSection } from "./marketFinancialChartsModel";
import styles from "./marketHomeNocturne.module.css";

const MARKET_CHAPTERS = [
  { id: "market-overview-judgment", label: "市场观察" },
  { id: "market-risk-observation", label: "风险观察" },
  { id: "market-overview-evidence", label: "宏观与组合" },
  { id: "market-financial-charts-all", label: "专题图表" },
  { id: "market-backend-data-all", label: "全部行情" },
] as const;

type MarketChapterId = (typeof MARKET_CHAPTERS)[number]["id"];
const HOME_RETURN_STATE_KEY = "moss:market-home:return-state";
type MarketReturnState = { search: string; openDetails: string[]; scrollY: number; focusId: string };
function readReturnState(): MarketReturnState | null {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(HOME_RETURN_STATE_KEY) || "null");
    if (!value || typeof value !== "object") return null;
    const state = value as Partial<MarketReturnState>;
    return typeof state.search === "string" && Array.isArray(state.openDetails) && state.openDetails.every((key) => typeof key === "string") && typeof state.scrollY === "number" && Number.isFinite(state.scrollY) && typeof state.focusId === "string" ? state as MarketReturnState : null;
  } catch { return null; }
}
function detailKey(detail: HTMLDetailsElement) { return detail.id || detail.dataset.testid || detail.querySelector("summary")?.textContent || ""; }

type MarketHomeLayoutProps = {
  view: ModuleHomeView;
  config: ModuleWorkbenchHomeConfig;
  tapeDateRange: string;
  formalTradeDate: string;
  isRefreshing: boolean;
  refreshStatus: string;
  refreshError: string;
  queries: ModuleHomeSourceQueries;
  onBackendActiveKeyChange: (key: string) => void;
  onChartsVisible: () => void;
  onChartSectionsChange: (keys: MarketFinancialChartSection["key"][]) => void;
  onRefreshData: () => void;
};

function isMarketChapterId(value: string): value is MarketChapterId {
  return MARKET_CHAPTERS.some((chapter) => chapter.id === value);
}

export default function MarketHomeLayout({
  view,
  config,
  tapeDateRange,
  formalTradeDate,
  isRefreshing,
  refreshStatus,
  refreshError,
  queries,
  onBackendActiveKeyChange,
  onChartsVisible,
  onChartSectionsChange,
  onRefreshData,
}: MarketHomeLayoutProps) {
  const location = useLocation();
  const pageRootRef = useRef<HTMLDivElement>(null);
  const chartPalette = useMarketChartPalette(pageRootRef);
  const returnState = useRef(readReturnState());
  const restored = useRef(false);
  const [searchValue, setSearchValue] = useState(() => returnState.current?.search ?? "");
  const [activeChapter, setActiveChapter] = useState<MarketChapterId>(() => {
    const hashChapter = location.hash.slice(1);
    return isMarketChapterId(hashChapter)
      ? hashChapter
      : "market-overview-judgment";
  });

  function rememberReturnState(event: MouseEvent<HTMLDivElement>) {
    const anchor = event.target instanceof Element ? event.target.closest("a") : null;
    const href = anchor?.getAttribute("href");
    if (!href || !href.includes("origin=market-overview")) return;
    const section = new URL(href, window.location.origin).searchParams.get("return_section");
    const state: MarketReturnState = {
      search: searchValue,
      openDetails: Array.from(pageRootRef.current?.querySelectorAll<HTMLDetailsElement>("details[open]") ?? []).map(detailKey),
      scrollY: window.scrollY,
      focusId: section === "events" ? "market-home-events-trigger" : section === "macro" ? "market-home-macro-trigger" : "market-risk-observation",
    };
    try { sessionStorage.setItem(HOME_RETURN_STATE_KEY, JSON.stringify(state)); } catch { /* Storage may be disabled; normal navigation still works. */ }
  }

  useEffect(() => {
    const state = returnState.current;
    if (restored.current || !state || !queries.marketSnapshot?.data) return;
    const frame = requestAnimationFrame(() => {
      restored.current = true;
      pageRootRef.current?.querySelectorAll<HTMLDetailsElement>("details").forEach((detail) => { if (state.openDetails.includes(detailKey(detail))) detail.open = true; });
      if (state.openDetails.includes("market-financial-charts-all")) onChartsVisible();
      const target = document.getElementById(state.focusId);
      (target?.matches("button, a, input") ? target : target?.querySelector<HTMLElement>("button, a"))?.focus({ preventScroll: true });
      window.scrollTo({ top: state.scrollY, behavior: "instant" });
      try { sessionStorage.removeItem(HOME_RETURN_STATE_KEY); } catch { /* Optional restoration only. */ }
    });
    return () => cancelAnimationFrame(frame);
  }, [onChartsVisible, queries.marketSnapshot?.data]);

  useEffect(() => {
    const hashChapter = location.hash.slice(1);
    if (isMarketChapterId(hashChapter)) {
      const chapter = document.getElementById(hashChapter);
      if (chapter instanceof HTMLDetailsElement) chapter.open = true;
      setActiveChapter(hashChapter);
      if (hashChapter === "market-financial-charts-all") onChartsVisible();
    } else if (location.hash === "") {
      setActiveChapter("market-overview-judgment");
    }
  }, [location.hash, onChartsVisible]);

  useEffect(() => {
    const chapterElements = MARKET_CHAPTERS.map((chapter) =>
      document.getElementById(chapter.id),
    ).filter((element): element is HTMLElement => Boolean(element));

    if (chapterElements.length === 0 || !("IntersectionObserver" in window)) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const nearestVisibleChapter = entries
          .filter((entry) => entry.isIntersecting)
          .sort(
            (left, right) =>
              Math.abs(left.boundingClientRect.top) -
              Math.abs(right.boundingClientRect.top),
          )[0];

        if (
          nearestVisibleChapter &&
          isMarketChapterId(nearestVisibleChapter.target.id)
        ) {
          setActiveChapter(nearestVisibleChapter.target.id);
          if (
            nearestVisibleChapter.target.id === "market-financial-charts-all" &&
            nearestVisibleChapter.target instanceof HTMLDetailsElement &&
            nearestVisibleChapter.target.open
          ) {
            onChartsVisible();
          }
        }
      },
      {
        rootMargin: "-10% 0px -72% 0px",
        threshold: [0, 0.01, 0.2],
      },
    );

    chapterElements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [onChartsVisible]);

  const statusTitle = [view.stateDetail, view.marketDeskIntel?.curveShapeLabel]
    .filter(Boolean)
    .join(" · ");
  const refreshFeedback = refreshError || refreshStatus;

  return (
    <div className={styles.pageRoot} data-state={view.dataState} ref={pageRootRef} onClickCapture={rememberReturnState}>
      <header className={styles.topbar} data-testid="module-home-toolbar">
        <div className={styles.topbarLeft}>
          <div className={styles.headingLine}>
            <h1 className={styles.pageTitle}>市场总览</h1>
            <span
              className={styles.statusPill}
              data-testid="module-home-market-dense-status"
              data-tone={refreshError ? "error" : view.dataState}
              title={statusTitle || undefined}
            >
              <i aria-hidden="true" />
              {isRefreshing ? "刷新中" : view.stateLabel}
            </span>
          </div>
          <div
            className={styles.tradeDates}
            data-testid="module-home-market-dense-date"
          >
            <span>
              行情区间
              <strong>{tapeDateRange || EM_DASH}</strong>
            </span>
            <span>
              正式序列
              <strong>{formalTradeDate || EM_DASH}</strong>
            </span>
          </div>
        </div>
        <div
          className={styles.topbarRight}
          data-testid="module-home-market-dense-utility"
        >
          {refreshFeedback ? (
            <span
              className={styles.refreshFeedback}
              role="status"
              data-tone={refreshError ? "error" : "ok"}
              title={refreshFeedback}
            >
              {refreshFeedback}
            </span>
          ) : null}
          <label
            className={styles.searchBox}
            data-testid="module-home-market-dense-search"
          >
            <SearchOutlined aria-hidden="true" />
            <span className={styles.visuallyHidden}>
              搜索指标、图表或事件
            </span>
            <input
              value={searchValue}
              placeholder="搜索指标、图表、事件或代码"
              onChange={(event) => setSearchValue(event.target.value)}
            />
          </label>
          <button
            type="button"
            className={styles.refreshButton}
            data-testid="module-home-market-dense-refresh"
            disabled={isRefreshing}
            aria-busy={isRefreshing || undefined}
            onClick={() => void onRefreshData()}
          >
            <ReloadOutlined aria-hidden="true" />
            刷新数据
          </button>
        </div>
      </header>

      <div className={styles.main}>
        <MarketOverviewDenseFirstScreen
          view={view}
          queries={queries}
          searchValue={searchValue}
          chartPalette={chartPalette}
          chapterNav={<nav
        aria-label={`${config.title}章节导航`}
        className={styles.chapterNav}
        data-testid="module-home-market-chapter-nav"
      >
        {MARKET_CHAPTERS.map((chapter) => (
          <a
            aria-current={activeChapter === chapter.id ? "location" : undefined}
            className={styles.chapterNavLink}
            data-active={activeChapter === chapter.id ? "true" : "false"}
            href={`#${chapter.id}`}
            key={chapter.id}
            onClick={() => {
              const target = document.getElementById(chapter.id);
              if (target instanceof HTMLDetailsElement) target.open = true;
              setActiveChapter(chapter.id);
              if (chapter.id === "market-financial-charts-all") onChartsVisible();
            }}
          >
            {chapter.label}
          </a>
        ))}
        <details className={styles.marketFunctions}>
          <summary>市场功能</summary>
          <div>
            <a href="#market-financial-charts-all" onClick={() => { const target = document.getElementById("market-financial-charts-all"); if (target instanceof HTMLDetailsElement) target.open = true; onChartsVisible(); }}>十二项专题图表</a>
            <a href="#market-backend-data-all" onClick={() => { const target = document.getElementById("market-backend-data-all"); if (target instanceof HTMLDetailsElement) target.open = true; }}>全部行情与来源</a>
            <a href="/macro-toolkit">宏观工具与刷新核验</a>
            <a href="/news-events">新闻事件</a>
          </div>
        </details>
      </nav>}
        />
        <details
          id="market-financial-charts-all"
          className={styles.secondaryDetails}
          onToggle={(event) => {
            if (event.currentTarget.open) onChartsVisible();
          }}
        >
          <summary>
            <strong>专题图表</strong>
            <span>利率、跨资产、宏观、策略与事件</span>
          </summary>
          <MarketFinancialChartsWorkbench
            queries={queries}
            chartPalette={chartPalette}
            onChartSectionsChange={onChartSectionsChange}
          />
        </details>
        <details id="market-backend-data-all" className={styles.secondaryDetails}>
          <summary>
            <strong>全部行情</strong>
            <span>行情明细、数据来源与质量</span>
          </summary>
          <MarketBackendDataWorkbench
            queries={queries}
            onActiveKeyChange={onBackendActiveKeyChange}
          />
        </details>
      </div>
    </div>
  );
}
