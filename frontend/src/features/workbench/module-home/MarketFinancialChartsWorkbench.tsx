import { useEffect, useMemo, useRef, useState } from "react";
import type { ResultMeta } from "../../../api/contracts";
import ReactECharts from "../../../lib/echarts";
import type { MarketChartPalette } from "./marketChartPalette";
import {
  buildMarketFinancialChartSections,
  type MarketFinancialChartSpec,
  type MarketFinancialChartSection,
} from "./marketFinancialChartsModel";
import type { ModuleHomeSourceQueries } from "./moduleHomeModel";
import { useDeferredChartMount } from "./useDeferredChartMount";
import styles from "./marketFinancialChartsWorkbench.module.css";

const NEWS_CHART_SAMPLE_SIZE = 500;
const SECTION_KEYS = [
  "rates",
  "cross",
  "macro",
  "strategy",
  "news",
  "coverage",
] as const satisfies readonly MarketFinancialChartSection["key"][];

type MarketFinancialChartsWorkbenchProps = {
  queries: ModuleHomeSourceQueries;
  chartPalette?: MarketChartPalette;
};

type MarketFinancialSectionKey = MarketFinancialChartSection["key"];
type MarketFinancialViewMode = "focus" | "overview";

type MarketFinancialSectionQuery = {
  data?: { result_meta: ResultMeta };
  isError?: boolean;
};

function metaStatus(meta: ResultMeta | undefined) {
  if (!meta) return { label: "等待数据", tone: "muted" };
  if (meta.quality_flag === "error") {
    return { label: "质量异常", tone: "error" };
  }
  if (
    meta.quality_flag === "stale" ||
    meta.fallback_mode !== "none" ||
    meta.vendor_status !== "ok"
  ) {
    return { label: "回退/过期", tone: "watch" };
  }
  if (meta.quality_flag === "warning" || meta.quality_flag === "missing") {
    return { label: "部分可用", tone: "watch" };
  }
  return { label: "已返回", tone: "ok" };
}

function ChartCard({ chart }: { chart: MarketFinancialChartSpec }) {
  const { containerRef, ready, onChartReady } =
    useDeferredChartMount<HTMLDivElement>();
  const yieldQuoteComparison =
    chart.yieldCurveDisplay && chart.yieldCurveDisplay.kind !== "curve"
      ? chart.yieldCurveDisplay
      : undefined;

  return (
    <article
      className={styles.chartCard}
      data-chart-view={yieldQuoteComparison?.kind ?? "chart"}
      data-testid={`module-home-market-chart-${chart.key}`}
    >
      <header>
        <div>
          <h3 title={chart.title}>{chart.title}</h3>
          <p title={`${chart.subtitle} · ${chart.footnote}`}>
            {chart.subtitle}
          </p>
        </div>
      </header>
      <div
        className={styles.chartCanvas}
        ref={containerRef}
      >
        {chart.readingGuide ? (
          <p className={styles.chartReadingGuide} role="note">
            <strong>怎么看</strong>
            <span>{chart.readingGuide}</span>
          </p>
        ) : null}
        {yieldQuoteComparison ? (
          <div
            className={styles.yieldQuoteComparison}
            aria-label={
              yieldQuoteComparison.kind === "single-tenor"
                ? `${yieldQuoteComparison.tenorLabel} 收益率报价`
                : `${yieldQuoteComparison.uniqueTenorCount} 个期限收益率报价`
            }
            data-testid={`module-home-market-yield-${yieldQuoteComparison.kind}`}
          >
            <p>{yieldQuoteComparison.message}</p>
            <dl>
              {yieldQuoteComparison.rows.map((row) => (
                <div key={`${row.curve}-${row.tenorLabel}-${row.tradeDate}`}>
                  <dt>
                    {row.curve} {row.tenorLabel}
                  </dt>
                  <dd>
                    {row.value.toFixed(3)}
                    <span>{row.unit}</span>
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ) : !chart.option ? (
          <div className={styles.chartEmpty}>
            后端暂未返回足够的可绘制数据。
          </div>
        ) : ready ? (
          <ReactECharts
            option={chart.option}
            style={{
              height: "var(--market-chart-canvas-height)",
              width: "100%",
            }}
            notMerge
            lazyUpdate
            onChartReady={onChartReady}
          />
        ) : null}
      </div>
      <footer>{chart.footnote}</footer>
    </article>
  );
}

function sectionQuery(
  sectionKey: MarketFinancialChartSection["key"],
  queries: ModuleHomeSourceQueries,
): MarketFinancialSectionQuery | undefined {
  if (sectionKey === "rates") return queries.marketRates;
  if (sectionKey === "cross") return queries.choiceLatest;
  if (sectionKey === "macro") return queries.macroToolkitAnalysis;
  if (sectionKey === "strategy")
    return queries.macroToolkitStrategySummaries;
  if (sectionKey === "news") return queries.newsEvents;
  return queries.marketCatalog;
}

function sectionStatus(query: MarketFinancialSectionQuery | undefined) {
  if (query?.isError) {
    return query.data
      ? { label: "刷新失败 · 保留旧数据", tone: "error" }
      : { label: "读取失败", tone: "error" };
  }
  return metaStatus(query?.data?.result_meta);
}

function sectionAsOf(meta: ResultMeta | undefined) {
  return (
    meta?.as_of_date ??
    meta?.resolved_report_date ??
    meta?.fallback_date ??
    "日期未返回"
  );
}

export function MarketFinancialChartsWorkbench({
  queries,
  chartPalette,
}: MarketFinancialChartsWorkbenchProps) {
  const [activeKey, setActiveKey] = useState<MarketFinancialSectionKey>("rates");
  const [expandedKeys, setExpandedKeys] = useState<
    ReadonlySet<MarketFinancialSectionKey>
  >(() => new Set<MarketFinancialSectionKey>([SECTION_KEYS[0]]));
  const [viewMode, setViewMode] =
    useState<MarketFinancialViewMode>("overview");
  const viewModeRef = useRef<MarketFinancialViewMode>("overview");
  const sectionNavRef = useRef<HTMLElement | null>(null);
  const sectionRefs = useRef<
    Partial<Record<MarketFinancialSectionKey, HTMLElement | null>>
  >({});
  const newsSampleSize =
    queries.newsEvents?.data?.result.limit ?? NEWS_CHART_SAMPLE_SIZE;

  const sections = useMemo(
    () =>
      buildMarketFinancialChartSections({
        latest: queries.choiceLatest?.data?.result,
        rates: queries.marketRates?.data?.result,
        catalog: queries.marketCatalog?.data?.result,
        macro: queries.macroToolkitAnalysis?.data?.result,
        strategies: queries.macroToolkitStrategySummaries?.data?.result,
        news: queries.newsEvents?.data?.result,
        palette: chartPalette,
      }),
    [
      chartPalette,
      queries.choiceLatest?.data,
      queries.macroToolkitAnalysis?.data,
      queries.macroToolkitStrategySummaries?.data,
      queries.marketCatalog?.data,
      queries.marketRates?.data,
      queries.newsEvents?.data,
    ],
  );
  const headerAsOf = sectionAsOf(queries.marketRates?.data?.result_meta);

  useEffect(() => {
    if (
      viewMode !== "overview" ||
      typeof IntersectionObserver === "undefined"
    ) {
      return;
    }

    let isTracking = true;
    const observer = new IntersectionObserver(
      () => {
        if (!isTracking || viewModeRef.current !== "overview") return;

        const navigationAnchor = Math.max(
          sectionNavRef.current?.getBoundingClientRect().bottom ?? 0,
          0,
        );
        const viewportBottom =
          window.innerHeight || document.documentElement.clientHeight;
        const visibleSection = SECTION_KEYS.flatMap((key) => {
          const section = sectionRefs.current[key];
          if (!section) return [];

          const bounds = section.getBoundingClientRect();
          const intersectsVisibleArea =
            bounds.bottom > navigationAnchor && bounds.top < viewportBottom;

          return intersectsVisibleArea ? [{ bounds, key }] : [];
        }).sort((left, right) => {
          const leftDistance = Math.abs(
            left.bounds.top - navigationAnchor,
          );
          const rightDistance = Math.abs(
            right.bounds.top - navigationAnchor,
          );
          return leftDistance - rightDistance;
        })[0];

        if (visibleSection) setActiveKey(visibleSection.key);
      },
      {
        rootMargin: "0px",
        threshold: [0.25, 0.5, 0.75],
      },
    );

    for (const key of SECTION_KEYS) {
      const section = sectionRefs.current[key];
      if (section) observer.observe(section);
    }

    return () => {
      isTracking = false;
      observer.disconnect();
    };
  }, [sections, viewMode]);

  function handleViewModeChange(nextViewMode: MarketFinancialViewMode) {
    viewModeRef.current = nextViewMode;
    setViewMode(nextViewMode);
  }

  function handleSectionToggle(key: MarketFinancialSectionKey) {
    setExpandedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function handleSectionNav(key: MarketFinancialSectionKey) {
    setActiveKey(key);
    if (viewMode === "focus") return;
    setExpandedKeys((current) => new Set(current).add(key));
    const sectionNode = sectionRefs.current[key];
    if (typeof sectionNode?.scrollIntoView === "function") {
      sectionNode.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  }

  return (
    <section
      id="market-financial-charts-all"
      className={styles.workbench}
      data-view-mode={viewMode}
      data-testid="module-home-market-financial-charts"
    >
      <header className={styles.workbenchHeader}>
        <div>
          <span>03</span>
          <h2>金融图表 · 12 张</h2>
          <p>
            全览按分组渐进展开：默认打开首个分组，其余收为摘要行，点开即看该组图表；重点模式只聚焦当前分组。
          </p>
        </div>
        <div
          className={styles.modeToggle}
          role="group"
          aria-label="金融图表显示模式"
        >
          <button
            type="button"
            className={styles.modeButton}
            aria-pressed={viewMode === "focus"}
            onClick={() => handleViewModeChange("focus")}
          >
            重点
          </button>
          <button
            type="button"
            className={styles.modeButton}
            aria-pressed={viewMode === "overview"}
            onClick={() => handleViewModeChange("overview")}
          >
            全览
          </button>
        </div>
        <div className={styles.headerStatus}>
          <span>数据日期</span>
          <em>{headerAsOf}</em>
        </div>
      </header>

      <nav
        ref={sectionNavRef}
        className={styles.sectionNav}
        aria-label="金融图表分组导航"
      >
        {sections.map((section, index) => (
          <button
            key={section.key}
            type="button"
            aria-current={
              viewMode === "overview" && section.key === activeKey
                ? "location"
                : undefined
            }
            aria-pressed={
              viewMode === "focus" ? section.key === activeKey : undefined
            }
            aria-controls={`market-financial-section-${section.key}`}
            aria-label={section.title}
            className={styles.sectionNavButton}
            data-active={section.key === activeKey ? "true" : "false"}
            onClick={() => handleSectionNav(section.key)}
          >
            <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
            <strong>{section.title}</strong>
            <em>{section.charts.length} 张</em>
          </button>
        ))}
      </nav>

      <div className={styles.sectionStack}>
        {sections.map((section, index) => {
          const query = sectionQuery(section.key, queries);
          const meta = query?.data?.result_meta;
          const status = sectionStatus(query);
          const isExpanded =
            viewMode === "focus" || expandedKeys.has(section.key);
          const bodyId = `market-financial-section-body-${section.key}`;

          return (
            <article
              key={section.key}
              id={`market-financial-section-${section.key}`}
              className={styles.sectionChapter}
              data-section-key={section.key}
              data-active={section.key === activeKey ? "true" : "false"}
              data-expanded={isExpanded ? "true" : "false"}
              ref={(node) => {
                sectionRefs.current[section.key] = node;
              }}
              tabIndex={-1}
            >
              <aside className={styles.sectionRail}>
                <span>{index + 1}</span>
                <strong>{section.title}</strong>
                <em>{section.kicker}</em>
                <p title={section.description}>{section.description}</p>
                <div className={styles.sourceBadge}>
                  <strong
                    data-tone={status.tone}
                    data-testid={`module-home-market-section-status-${section.key}`}
                  >
                    {status.label}
                  </strong>
                  <span>{sectionAsOf(meta)}</span>
                  {section.key === "news" ? (
                    <em>最新 {newsSampleSize} 条样本</em>
                  ) : (
                    <em>{section.charts.length} 张图表</em>
                  )}
                </div>
                <button
                  type="button"
                  className={styles.sectionToggle}
                  aria-controls={bodyId}
                  aria-expanded={isExpanded}
                  data-testid={`module-home-market-section-toggle-${section.key}`}
                  onClick={() => handleSectionToggle(section.key)}
                >
                  {isExpanded ? "收起" : "展开"}
                </button>
              </aside>

              <div className={styles.sectionBody} id={bodyId}>
                <div className={styles.chartGrid}>
                  {section.charts.map((chart) => (
                    <ChartCard chart={chart} key={chart.key} />
                  ))}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
