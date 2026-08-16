import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";

import { EM_DASH } from "../../../utils/format";
import { getMarketWorkbenchNav } from "../market-shell/marketWorkbenchNav";
import type {
  ModuleHomeSourceQueries,
  ModuleHomeView,
} from "./moduleHomeModel";
import type { ModuleWorkbenchHomeConfig } from "./moduleHomeConfig";
import { MarketBackendDataWorkbench } from "./MarketBackendDataWorkbench";
import { MarketFinancialChartsWorkbench } from "./MarketFinancialChartsWorkbench";
import { MarketOverviewDenseFirstScreen } from "./MarketOverviewDenseFirstScreen";
import { useMarketChartPalette } from "./marketChartPalette";
import styles from "./marketHomeNocturne.module.css";

const MARKET_CHAPTERS = [
  { id: "market-overview-judgment", label: "分析观察" },
  { id: "market-overview-evidence", label: "市场证据" },
  { id: "market-financial-charts-all", label: "金融图表 12" },
  { id: "market-backend-data-all", label: "数据核验 6" },
] as const;

const MARKET_SUBPAGES = getMarketWorkbenchNav();

type MarketChapterId = (typeof MARKET_CHAPTERS)[number]["id"];

type MarketHomeLayoutProps = {
  view: ModuleHomeView;
  config: ModuleWorkbenchHomeConfig;
  latestTradeDate: string;
  formalTradeDate: string;
  isRefreshing: boolean;
  refreshStatus: string;
  refreshError: string;
  queries: ModuleHomeSourceQueries;
  onRefreshData: () => void;
};

function isMarketChapterId(value: string): value is MarketChapterId {
  return MARKET_CHAPTERS.some((chapter) => chapter.id === value);
}

export default function MarketHomeLayout({
  view,
  config,
  latestTradeDate,
  formalTradeDate,
  isRefreshing,
  refreshStatus,
  refreshError,
  queries,
  onRefreshData,
}: MarketHomeLayoutProps) {
  const location = useLocation();
  const pageRootRef = useRef<HTMLDivElement>(null);
  const chartPalette = useMarketChartPalette(pageRootRef);
  const [searchValue, setSearchValue] = useState("");
  const [activeChapter, setActiveChapter] = useState<MarketChapterId>(() => {
    const hashChapter = location.hash.slice(1);
    return isMarketChapterId(hashChapter)
      ? hashChapter
      : "market-overview-judgment";
  });

  useEffect(() => {
    const hashChapter = location.hash.slice(1);
    if (isMarketChapterId(hashChapter)) {
      setActiveChapter(hashChapter);
    } else if (location.hash === "") {
      setActiveChapter("market-overview-judgment");
    }
  }, [location.hash]);

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
        }
      },
      {
        rootMargin: "-10% 0px -72% 0px",
        threshold: [0, 0.01, 0.2],
      },
    );

    chapterElements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);

  const statusTitle = [view.stateDetail, view.marketDeskIntel?.curveShapeLabel]
    .filter(Boolean)
    .join(" · ");
  const refreshFeedback = refreshError || refreshStatus;

  return (
    <div className={styles.pageRoot} ref={pageRootRef}>
      <header className={styles.topbar} data-testid="module-home-toolbar">
        <div className={styles.topbarLeft}>
          <h1 className={styles.pageTitle}>市场总览</h1>
          <div
            className={styles.tradeDates}
            data-testid="module-home-market-dense-date"
          >
            <span>
              行情
              <strong>{latestTradeDate || EM_DASH}</strong>
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
          <span
            className={styles.statusPill}
            data-testid="module-home-market-dense-status"
            data-tone={refreshError ? "error" : "ok"}
            title={statusTitle || undefined}
          >
            <i aria-hidden="true" />
            {isRefreshing ? "刷新中" : view.stateLabel}
          </span>
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
              placeholder="搜索指标 / 图表 / 事件 / 代码"
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

      <nav
        aria-label="市场工作台子页面入口"
        className={styles.subpageNav}
        data-testid="module-home-market-subpage-nav"
      >
        {MARKET_SUBPAGES.map((page) => {
          const isActive = location.pathname === page.path;

          return (
            <Link
              aria-current={isActive ? "page" : undefined}
              className={styles.subpageLink}
              data-active={isActive ? "true" : "false"}
              key={page.key}
              title={`${page.label} · ${page.statusLabel} · ${page.description}`}
              to={page.path}
            >
              {page.compactLabel}
            </Link>
          );
        })}
      </nav>

      <nav
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
            onClick={() => setActiveChapter(chapter.id)}
          >
            {chapter.label}
          </a>
        ))}
      </nav>

      <main className={styles.main}>
        <MarketOverviewDenseFirstScreen
          view={view}
          queries={queries}
          latestTradeDate={latestTradeDate}
          searchValue={searchValue}
          chartPalette={chartPalette}
        />
        <MarketFinancialChartsWorkbench
          queries={queries}
          chartPalette={chartPalette}
        />
        <MarketBackendDataWorkbench queries={queries} />
      </main>
    </div>
  );
}
