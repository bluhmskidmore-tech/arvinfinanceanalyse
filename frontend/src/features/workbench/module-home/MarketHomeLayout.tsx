import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { getMarketWorkbenchNav } from "../market-shell/marketWorkbenchNav";
import type {
  ModuleHomeSourceQueries,
  ModuleHomeView,
} from "./moduleHomeModel";
import type { ModuleWorkbenchHomeConfig } from "./moduleHomeConfig";
import { MarketBackendDataWorkbench } from "./MarketBackendDataWorkbench";
import { MarketFinancialChartsWorkbench } from "./MarketFinancialChartsWorkbench";
import { MarketOverviewDenseFirstScreen } from "./MarketOverviewDenseFirstScreen";
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

  return (
    <div className={styles.pageRoot}>
      <header className={styles.chapterNav}>
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
          className={styles.chapterNavInner}
          data-testid="module-home-market-chapter-nav"
        >
          {MARKET_CHAPTERS.map((chapter) => (
            <a
              aria-current={
                activeChapter === chapter.id ? "location" : undefined
              }
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
      </header>

      <main className={styles.main}>
        <MarketOverviewDenseFirstScreen
          view={view}
          queries={queries}
          latestTradeDate={latestTradeDate}
          formalTradeDate={formalTradeDate}
          isRefreshing={isRefreshing}
          refreshStatus={refreshStatus}
          refreshError={refreshError}
          onRefreshData={onRefreshData}
        />
        <MarketFinancialChartsWorkbench queries={queries} />
        <MarketBackendDataWorkbench queries={queries} />
      </main>
    </div>
  );
}
