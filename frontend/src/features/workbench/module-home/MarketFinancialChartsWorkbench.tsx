import { useEffect, useMemo, useRef, useState } from "react";
import type { ResultMeta } from "../../../api/contracts";
import { ChartCard as UnifiedChartCard } from "../../../components/charts/ChartCard";
import DeferredChart from "../../../lib/echarts";
import type { MarketChartPalette } from "./marketChartPalette";
import {
  buildMarketFinancialChartSections,
  DENSE_FIRST_SCREEN_CHART_PICKS,
  type MarketFinancialChartSpec,
  type MarketFinancialChartSection,
} from "./marketFinancialChartsModel";
import type { ModuleHomeSourceQueries } from "./moduleHomeModel";
import { EM_DASH } from "../../../utils/format";
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

function denseFirstScreenChartKeys(sections: MarketFinancialChartSection[]) {
  const sectionsByKey = new Map(sections.map((section) => [section.key, section]));
  return new Set(
    DENSE_FIRST_SCREEN_CHART_PICKS.flatMap(
      (pick) => sectionsByKey.get(pick.sectionKey)?.charts[pick.chartIndex]?.key ?? [],
    ),
  );
}

function shouldReferenceFirstScreenChart(
  chart: MarketFinancialChartSpec,
  firstScreenChartKeys: ReadonlySet<string>,
) {
  if (!firstScreenChartKeys.has(chart.key)) {
    return false;
  }
  // 单期限/稀疏报价状态下 03 区渲染的是文字对照表（非重复画布），保留原卡。
  if (chart.yieldCurveDisplay && chart.yieldCurveDisplay.kind !== "curve") {
    return false;
  }
  return true;
}

function firstOverviewExpandedSectionKey(
  sections: MarketFinancialChartSection[],
  firstScreenChartKeys: ReadonlySet<string>,
) {
  return (
    sections.find((section) =>
      section.charts.some(
        (chart) => !shouldReferenceFirstScreenChart(chart, firstScreenChartKeys),
      ),
    )?.key ?? SECTION_KEYS[0]
  );
}

type MarketFinancialChartsWorkbenchProps = {
  queries: ModuleHomeSourceQueries;
  chartPalette?: MarketChartPalette;
  onChartSectionsChange?: (keys: MarketFinancialChartSection["key"][]) => void;
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

function MarketFinancialChartCard({ chart }: { chart: MarketFinancialChartSpec }) {
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
      {yieldQuoteComparison ? (
        <header>
          <div>
            <h3 title={chart.title}>{chart.title}</h3>
            <p title={`${chart.subtitle} · ${chart.footnote}`}>
              {chart.subtitle}
            </p>
          </div>
        </header>
      ) : null}
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
        ) : (
          <UnifiedChartCard
            flat
            title={chart.title}
            question={chart.subtitle}
            option={chart.option}
            height={220}
            footnote={chart.footnote}
            emptyMessage="后端暂未返回足够的可绘制数据。"
            chartRenderer={({ option, height }) =>
              ready ? (
                <DeferredChart
                  option={option}
                  style={{ height, width: "100%" }}
                  notMerge
                  lazyUpdate
                  onChartReady={onChartReady}
                />
              ) : null
            }
          />
        )}
      </div>
      {yieldQuoteComparison ? <footer>{chart.footnote}</footer> : null}
    </article>
  );
}

function ChartReferenceCard({ chart }: { chart: MarketFinancialChartSpec }) {
  return (
    <article
      className={styles.chartCard}
      data-chart-view="reference"
      data-testid={`module-home-market-chart-ref-${chart.key}`}
    >
      <header>
        <div>
          <h3 title={chart.title}>{chart.title}</h3>
          <p title={`${chart.subtitle} · ${chart.footnote}`}>{chart.subtitle}</p>
        </div>
      </header>
      <div className={styles.chartCanvas}>
        {chart.readingGuide ? (
          <p className={styles.chartReadingGuide} role="note">
            <strong>怎么看</strong>
            <span>{chart.readingGuide}</span>
          </p>
        ) : null}
        <p className={styles.chartReference}>
          <span>该图已在上方首页展示。</span>
          <a href={`#market-overview-chart-${chart.key}`}>查看上方原图</a>
        </p>
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

/** 分组行业务日期；缺失时返回 undefined，由调用方省略日期段（不渲染占位文案）。 */
function sectionAsOf(meta: ResultMeta | undefined): string | undefined {
  return (
    meta?.as_of_date ??
    meta?.resolved_report_date ??
    meta?.fallback_date ??
    undefined
  );
}

export function MarketFinancialChartsWorkbench({
  queries,
  chartPalette,
  onChartSectionsChange,
}: MarketFinancialChartsWorkbenchProps) {
  const [activeKey, setActiveKey] = useState<MarketFinancialSectionKey>("rates");
  const [expandedKeys, setExpandedKeys] = useState<
    ReadonlySet<MarketFinancialSectionKey>
  >(() => new Set<MarketFinancialSectionKey>());
  const hasUserManagedExpansion = useRef(false);
  const [viewMode, setViewMode] =
    useState<MarketFinancialViewMode>("overview");
  const viewModeRef = useRef<MarketFinancialViewMode>("overview");
  const sectionNavRef = useRef<HTMLElement | null>(null);
  const sectionRefs = useRef<
    Partial<Record<MarketFinancialSectionKey, HTMLElement | null>>
  >({});
  const newsSampleSize =
    queries.newsEvents?.data?.result.limit ?? NEWS_CHART_SAMPLE_SIZE;
  // 新闻信封的 result_meta.as_of_date 是查询日（后端按 date.today() 生成的
  // received_at 过滤截止，date_basis=received_at_as_of_filter），不是样本日期；
  // 分组行按事件 received_at 最大值披露真实样本最新日期，停更时旧日期直接可见。
  const latestNewsSampleDate = useMemo(() => {
    const sampleDays = (queries.newsEvents?.data?.result.events ?? [])
      .map((event) => event.received_at.slice(0, 10))
      .filter(Boolean)
      .sort((left, right) => left.localeCompare(right));
    return sampleDays.at(-1);
  }, [queries.newsEvents?.data]);

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
  const firstScreenChartKeys = useMemo(
    () => denseFirstScreenChartKeys(sections),
    [sections],
  );
  const defaultExpandedKey = useMemo(
    () => firstOverviewExpandedSectionKey(sections, firstScreenChartKeys),
    [firstScreenChartKeys, sections],
  );
  const effectiveExpandedKeys = hasUserManagedExpansion.current
    ? expandedKeys
    : new Set<MarketFinancialSectionKey>([defaultExpandedKey]);

  const requestedSectionKey = SECTION_KEYS.filter((key) =>
    viewMode === "focus" ? key === activeKey : effectiveExpandedKeys.has(key),
  ).join(",");
  useEffect(() => {
    onChartSectionsChange?.(
      requestedSectionKey ? requestedSectionKey.split(",") as MarketFinancialSectionKey[] : [],
    );
  }, [onChartSectionsChange, requestedSectionKey]);

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
    const hasExplicitExpansion = hasUserManagedExpansion.current;
    hasUserManagedExpansion.current = true;
    setExpandedKeys((current) => {
      const next = new Set(
        hasExplicitExpansion ? current : [defaultExpandedKey],
      );
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function handleSectionNav(key: MarketFinancialSectionKey) {
    setActiveKey(key);
    if (viewMode === "focus") return;
    const hasExplicitExpansion = hasUserManagedExpansion.current;
    hasUserManagedExpansion.current = true;
    setExpandedKeys(
      (current) => new Set(hasExplicitExpansion ? current : [defaultExpandedKey]).add(key),
    );
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
          <em>{headerAsOf ?? EM_DASH}</em>
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
          const sectionDate = sectionAsOf(meta);
          const isExpanded =
            viewMode === "focus" || effectiveExpandedKeys.has(section.key);
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
                <p title={section.description}>{section.description}</p>
                <div className={styles.sourceBadge}>
                  <strong
                    data-tone={status.tone}
                    data-testid={`module-home-market-section-status-${section.key}`}
                  >
                    {status.label}
                  </strong>
                  {section.key === "news" ? (
                    <span>最新样本 {latestNewsSampleDate ?? EM_DASH}</span>
                  ) : sectionDate ? (
                    <span>{sectionDate}</span>
                  ) : null}
                  {section.key === "news" ? (
                    <em>最新 {newsSampleSize} 条样本</em>
                  ) : (
                    <em>{section.charts.length} 张图表</em>
                  )}
                </div>
                {viewMode === "overview" ? (
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
                ) : null}
              </aside>

              <div className={styles.sectionBody} id={bodyId}>
                <div className={styles.chartGrid}>
                  {section.charts.map((chart) =>
                    shouldReferenceFirstScreenChart(chart, firstScreenChartKeys) ? (
                      <ChartReferenceCard chart={chart} key={chart.key} />
                    ) : (
                      <MarketFinancialChartCard chart={chart} key={chart.key} />
                    ),
                  )}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
