import { useEffect, useMemo, useRef, useState } from "react";
import type { ResultMeta } from "../../../api/contracts";
import ReactECharts from "../../../lib/echarts";
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
};

type MarketFinancialSectionKey = MarketFinancialChartSection["key"];

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

  return (
    <article
      className={styles.chartCard}
      data-testid={`module-home-market-chart-${chart.key}`}
    >
      <header>
        <div>
          <h3>{chart.title}</h3>
          <p title={`${chart.subtitle} · ${chart.footnote}`}>
            {chart.subtitle} · {chart.footnote}
          </p>
        </div>
      </header>
      <div
        className={styles.chartCanvas}
        ref={containerRef}
      >
        {!chart.option ? (
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
}: MarketFinancialChartsWorkbenchProps) {
  const [activeKey, setActiveKey] = useState<MarketFinancialSectionKey>("rates");
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
      }),
    [
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
    if (typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visibleEntry = [...entries]
          .filter((entry) => entry.isIntersecting)
          .sort(
            (left, right) => right.intersectionRatio - left.intersectionRatio,
          )[0];
        if (!visibleEntry) return;
        const key = visibleEntry.target.getAttribute(
          "data-section-key",
        ) as MarketFinancialSectionKey | null;
        if (!key) return;
        setActiveKey(key);
      },
      {
        rootMargin: "-72px 0px -42% 0px",
        threshold: [0.25, 0.5, 0.75],
      },
    );

    for (const key of SECTION_KEYS) {
      const section = sectionRefs.current[key];
      if (section) observer.observe(section);
    }

    return () => observer.disconnect();
  }, [sections]);

  function handleSectionNav(key: MarketFinancialSectionKey) {
    setActiveKey(key);
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
      data-testid="module-home-market-financial-charts"
    >
      <header className={styles.workbenchHeader}>
        <div>
          <span>03</span>
          <h2>金融图表 · 12 张</h2>
          <p>
            金融图表工作台保留 6 类金融问题与 12 张原始图表，改成章节化全展开浏览；导航只负责定位，不再隐藏任何一组数据。
          </p>
        </div>
        <div className={styles.headerStatus}>
          <span>数据日期</span>
          <em>{headerAsOf}</em>
        </div>
      </header>

      <div
        className={styles.sectionNav}
        role="tablist"
        aria-label="金融图表分组导航"
      >
        {sections.map((section, index) => (
          <button
            key={section.key}
            type="button"
            role="tab"
            aria-selected={section.key === activeKey}
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
      </div>

      <div className={styles.sectionStack}>
        {sections.map((section, index) => {
          const query = sectionQuery(section.key, queries);
          const meta = query?.data?.result_meta;
          const status = sectionStatus(query);

          return (
            <article
              key={section.key}
              id={`market-financial-section-${section.key}`}
              className={styles.sectionChapter}
              data-section-key={section.key}
              data-active={section.key === activeKey ? "true" : "false"}
              ref={(node) => {
                sectionRefs.current[section.key] = node;
              }}
              tabIndex={-1}
            >
              <aside className={styles.sectionRail}>
                <span>{index + 1}</span>
                <strong>{section.title}</strong>
                <em>{section.kicker}</em>
              </aside>

              <div className={styles.sectionBody}>
                <div className={styles.sectionIntro}>
                  <div>
                    <span>{section.kicker}</span>
                    <p>{section.description}</p>
                  </div>
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
                </div>

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
