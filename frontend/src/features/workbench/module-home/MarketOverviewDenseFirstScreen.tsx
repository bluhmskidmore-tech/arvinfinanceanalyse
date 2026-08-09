import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";

import type { ChoiceNewsEvent, ResultMeta } from "../../../api/contracts";
import ReactECharts from "../../../lib/echarts";
import { buildActionQueue } from "./marketActionQueueModel";
import {
  buildMarketFinancialChartSections,
  type MarketFinancialChartSection,
  type MarketFinancialChartSpec,
} from "./marketFinancialChartsModel";
import { buildDenseLiquidityChartSpec } from "./marketOverviewDenseLiquidityModel";
import {
  buildDenseLedgerRows,
  buildDenseMacroPulseRows,
  buildDenseNewsDensity,
  buildDenseTapeMetrics,
  type DenseMacroPulseRow,
  type DenseNewsDensity,
  type DenseTapeMetric,
} from "./marketOverviewDenseModel";
import type {
  ModuleHomeDetailPanel,
  ModuleHomeDetailRow,
  ModuleHomeSourceQueries,
  ModuleHomeTone,
  ModuleHomeView,
} from "./moduleHomeModel";
import styles from "./marketOverviewDenseFirstScreen.module.css";

type DenseChart = {
  sectionKey: MarketFinancialChartSection["key"];
  indexLabel: string;
  chart: MarketFinancialChartSpec;
};

type MarketOverviewDenseFirstScreenProps = {
  view: ModuleHomeView;
  queries: ModuleHomeSourceQueries;
  latestTradeDate: string;
  formalTradeDate: string;
  isRefreshing: boolean;
  refreshStatus: string;
  refreshError: string;
  onRefreshData: () => void | Promise<void>;
};

function panelByKey(
  panels: ModuleHomeDetailPanel[] | undefined,
  key: string,
) {
  return panels?.find((panel) => panel.key === key);
}

function selectedDenseCharts(
  sections: MarketFinancialChartSection[],
): DenseChart[] {
  const byKey = new Map(sections.map((section) => [section.key, section]));
  const picks: Array<{
    sectionKey: MarketFinancialChartSection["key"];
    chartIndex: number;
    indexLabel: string;
  }> = [
    { sectionKey: "rates", chartIndex: 0, indexLabel: "A" },
    { sectionKey: "rates", chartIndex: 1, indexLabel: "B" },
    { sectionKey: "cross", chartIndex: 1, indexLabel: "C" },
  ];
  return picks.flatMap((pick) => {
    const chart = byKey.get(pick.sectionKey)?.charts[pick.chartIndex];
    return chart ? [{ ...pick, chart }] : [];
  });
}

function metricReportDate(metric: DenseTapeMetric) {
  return metric.title.split(" · ").at(-1) ?? "—";
}

function toneBadge(tone: ModuleHomeTone | "up" | "down" | "ok" | "muted") {
  if (tone === "error" || tone === "up") return "alert";
  if (tone === "watch") return "watch";
  if (tone === "down" || tone === "ok") return "ok";
  return "muted";
}

function compactEventTime(value: string) {
  return value ? value.replace("T", " ").slice(5, 16) : "时间未返回";
}

function signalDetail(row: ModuleHomeDetailRow) {
  const detailParts = [row.detail, row.source]
    .map((part) => part?.trim())
    .filter((part): part is string => Boolean(part && part !== "-"));
  return detailParts[0] ?? row.tradeDate ?? "—";
}

function fallbackLabel(meta: ResultMeta | undefined) {
  if (!meta) return "meta_missing";
  if (meta.fallback_mode === "none" && !meta.fallback_date) return "none";
  return `${meta.fallback_mode}${meta.fallback_date ? `/${meta.fallback_date}` : ""}`;
}

type MacroObservationGate = {
  basis: string;
  formalUse: string;
  sourceQuality: string;
  gate: string;
  blocked: boolean;
  reasonSummary: string;
};

const QUALITY_LABELS: Record<ResultMeta["quality_flag"], string> = {
  ok: "正常",
  warning: "预警",
  error: "异常",
  stale: "过期",
  missing: "缺失",
};

const VENDOR_LABELS: Record<ResultMeta["vendor_status"], string> = {
  ok: "正常",
  vendor_stale: "数据过期",
  vendor_unavailable: "不可用",
};

function buildMacroObservationGate(
  meta: ResultMeta | undefined,
  hasRefreshErrorWithData: boolean,
): MacroObservationGate {
  const fallback = fallbackLabel(meta);
  const blockingReasons: string[] = [];
  if (!meta) blockingReasons.push("结果元数据缺失");
  if (meta?.quality_flag && meta.quality_flag !== "ok") {
    blockingReasons.push(`数据质量${QUALITY_LABELS[meta.quality_flag]}`);
  }
  if (meta?.vendor_status && meta.vendor_status !== "ok") {
    blockingReasons.push(`供应方${VENDOR_LABELS[meta.vendor_status]}`);
  }
  if (meta && (meta.fallback_mode !== "none" || meta.fallback_date)) {
    blockingReasons.push(
      `使用回退数据${meta.fallback_date ? `（${meta.fallback_date}）` : ""}`,
    );
  }
  if (hasRefreshErrorWithData) {
    blockingReasons.push("刷新失败且保留缓存数据");
  }
  const blocked = blockingReasons.length > 0;
  return {
    basis: meta?.basis ?? "unknown",
    formalUse: meta ? String(meta.formal_use_allowed) : "unknown",
    sourceQuality: [
      `质量 ${meta ? QUALITY_LABELS[meta.quality_flag] : "未知"}`,
      `供应方 ${meta ? VENDOR_LABELS[meta.vendor_status] : "未知"}`,
      `回退 ${fallback}`,
      hasRefreshErrorWithData ? "刷新失败且保留缓存数据" : null,
    ]
      .filter(Boolean)
      .join(" / "),
    gate: blocked
      ? `暂停判断：${blockingReasons.join("；")}`
      : "仅供复核（非正式观察）",
    blocked,
    reasonSummary: blockingReasons.join("；"),
  };
}

function DenseChartCard({
  item,
  searchQuery,
  className,
  canvasHeight,
}: {
  item: DenseChart;
  searchQuery: string;
  className?: string;
  canvasHeight: number;
}) {
  const searchableText = `${item.chart.title} ${item.chart.subtitle}`.toLowerCase();
  const isSearchMatch =
    searchQuery.length === 0 || searchableText.includes(searchQuery);
  return (
    <article
      className={[styles.chartCard, className].filter(Boolean).join(" ")}
      data-search-match={isSearchMatch ? "true" : "false"}
      data-testid={`module-home-market-dense-chart-${item.chart.key}`}
    >
      <header className={styles.cardHeader}>
        <div>
          <span className={styles.cardIndex}>{item.indexLabel}</span>
          <h3>{item.chart.title}</h3>
        </div>
        <span>{item.chart.subtitle}</span>
      </header>
      <div className={styles.chartCanvas}>
        {item.chart.option ? (
          <ReactECharts
            className={styles.chartInstance}
            option={item.chart.option}
            style={{ height: canvasHeight }}
            notMerge
            lazyUpdate
            opts={{ renderer: "canvas" }}
          />
        ) : (
          <div className={styles.chartEmpty}>后端暂未返回足够的可绘制数据</div>
        )}
      </div>
      <footer>{item.chart.footnote}</footer>
    </article>
  );
}

function DenseMacroPulseCard({
  rows,
  searchQuery,
  asOfDate,
}: {
  rows: DenseMacroPulseRow[];
  searchQuery: string;
  asOfDate: string;
}) {
  const searchableText = `指标变动雷达 ${rows
    .map((row) => `${row.label} ${row.source}`)
    .join(" ")}`.toLowerCase();
  const isSearchMatch =
    searchQuery.length === 0 || searchableText.includes(searchQuery);
  return (
    <article
      className={`${styles.chartCard} ${styles.pulseCard}`}
      data-search-match={isSearchMatch ? "true" : "false"}
      data-testid="module-home-market-dense-chart-macro-pulse"
    >
      <header className={styles.cardHeader}>
        <div>
          <span className={styles.cardIndex}>E</span>
          <h3>指标变动表</h3>
        </div>
        <span>{asOfDate || "—"} · 单位按原始口径</span>
      </header>
      <div className={`${styles.chartCanvas} ${styles.macroPulse}`}>
        <div className={styles.pulseColumns} aria-hidden="true">
          <span>指标</span>
          <span>最新</span>
          <span>变化率</span>
          <span>信号</span>
        </div>
        <div className={styles.pulseRows}>
          {rows.length > 0 ? (
            rows.map((row) => (
              <div
                className={styles.pulseRow}
                key={row.key}
                title={`${row.source} · ${row.latestDate}`}
              >
                <span>{row.label}</span>
                <strong>{row.value}</strong>
                <em data-tone={row.tone}>{row.change}</em>
                <div
                  className={styles.microHistory}
                  aria-label={`${row.label}前值与最新值比较`}
                >
                  {[null, null, null, null, ...row.levels].map(
                    (level, index) => (
                      <i
                        data-empty={level == null ? "true" : "false"}
                        key={`${row.key}-${index}`}
                        style={level == null ? undefined : { height: `${level}%` }}
                      />
                    ),
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className={styles.compactEmpty}>后端分析暂未返回可展示指标</div>
          )}
        </div>
      </div>
      <footer>数据截至 {asOfDate || "—"} · change_pct 与原始最新值</footer>
    </article>
  );
}

function DenseNewsDensityCard({
  density,
  events,
  searchQuery,
  totalRows,
}: {
  density: DenseNewsDensity;
  events: ChoiceNewsEvent[];
  searchQuery: string;
  totalRows: number;
}) {
  const searchableText = `事件流入密度 ${events
    .map((event) => `${event.topic_code} ${event.payload_text ?? ""}`)
    .join(" ")}`.toLowerCase();
  const isSearchMatch =
    searchQuery.length === 0 || searchableText.includes(searchQuery);
  return (
    <article
      className={`${styles.chartCard} ${styles.newsCard}`}
      data-search-match={isSearchMatch ? "true" : "false"}
      data-testid="module-home-market-dense-chart-news-density"
    >
      <header className={styles.cardHeader}>
        <div>
          <span className={styles.cardIndex}>F</span>
          <h3>事件流入密度</h3>
        </div>
        <span>
          样本 {density.sampledEvents.toLocaleString("zh-CN")} / 全库{" "}
          {totalRows.toLocaleString("zh-CN")}
        </span>
      </header>
      <div className={`${styles.chartCanvas} ${styles.newsDensity}`}>
        <div className={styles.heatmapPanel}>
          <div className={styles.heatmapGrid}>
            <span />
            {density.hourLabels.map((hour, index) => (
              <time
                data-label={
                  index === 0 || index === 5 || index === 11 ? "true" : "false"
                }
                key={hour}
              >
                {hour}
              </time>
            ))}
            {density.rows.map((row) => (
              <div className={styles.heatmapRow} key={row.key}>
                <span title={row.key}>{row.label}</span>
                {row.cells.map((cell, bucketIndex) => (
                  <i
                    data-intensity={cell.intensity}
                    key={cell.key}
                    title={`${row.label} · ${density.hourLabels[bucketIndex]}时段 · ${cell.count} 条`}
                  />
                ))}
              </div>
            ))}
          </div>
          <div className={styles.heatmapLegend}>
            <span>低</span>
            {[0, 1, 2, 3, 4].map((intensity) => (
              <i data-intensity={intensity} key={intensity} />
            ))}
            <span>高</span>
          </div>
        </div>
        <div className={styles.newsMiniFeed}>
          <div className={styles.newsMiniHead}>
            <span>时间</span>
            <span>最新事件</span>
            <span>主题</span>
          </div>
          {events.length > 0 ? (
            events.slice(0, 3).map((event) => (
              <article key={event.event_key}>
                <time>{compactEventTime(event.received_at)}</time>
                <strong>{event.payload_text || event.error_msg || event.event_key}</strong>
                <em>{event.topic_code || event.group_id || "未分类"}</em>
              </article>
            ))
          ) : (
            <div className={styles.compactEmpty}>新闻事件暂未返回</div>
          )}
        </div>
      </div>
      <footer>
        样本区间 {density.startDate || "—"}–{density.endDate || "—"} · 主题 ×
        两小时桶
      </footer>
    </article>
  );
}

export function MarketOverviewDenseFirstScreen({
  view,
  queries,
  latestTradeDate,
  formalTradeDate,
  isRefreshing,
  refreshStatus,
  refreshError,
  onRefreshData,
}: MarketOverviewDenseFirstScreenProps) {
  const [searchValue, setSearchValue] = useState("");

  const latest = queries.choiceLatest?.data?.result;
  const rates = queries.marketRates?.data?.result;
  const catalog = queries.marketCatalog?.data?.result;
  const macro = queries.macroToolkitAnalysis?.data?.result;
  const macroMeta = queries.macroToolkitAnalysis?.data?.result_meta;
  const macroRefreshErrorWithData = Boolean(
    queries.macroToolkitAnalysis?.isError && queries.macroToolkitAnalysis?.data,
  );
  const strategies = queries.macroToolkitStrategySummaries?.data?.result;
  const news = queries.newsEvents?.data?.result;
  const sections = useMemo(
    () =>
      buildMarketFinancialChartSections({
        latest,
        rates,
        catalog,
        macro,
        strategies,
        news,
      }),
    [catalog, latest, macro, news, rates, strategies],
  );
  const charts = useMemo(() => selectedDenseCharts(sections), [sections]);
  const liquidityChart = useMemo(
    () => buildDenseLiquidityChartSpec(rates),
    [rates],
  );
  const macroPulseRows = useMemo(() => buildDenseMacroPulseRows(macro), [macro]);
  const newsDensity = useMemo(() => buildDenseNewsDensity(news), [news]);
  const tapeMetrics = useMemo(
    () => buildDenseTapeMetrics({ latest, rates, news }),
    [latest, news, rates],
  );
  const ledgerRows = useMemo(
    () => buildDenseLedgerRows(view.detailPanels),
    [view.detailPanels],
  );
  const keyRatePanel = panelByKey(view.detailPanels, "key-rate-snapshot");
  const macroSnapshotPanel = panelByKey(view.detailPanels, "latest-macro-snapshot");
  const yieldCurvePanel = panelByKey(view.detailPanels, "yield-curve-quotes");
  const signalPanel = panelByKey(view.detailPanels, "macro-toolkit-signals");
  const newsPanel = panelByKey(view.detailPanels, "news-events-snapshot");
  const actionItems = useMemo(
    () =>
      buildActionQueue({
        view,
        keyRatePanel,
        yieldCurvePanel,
        macroPanel: macroSnapshotPanel,
      }),
    [keyRatePanel, macroSnapshotPanel, view, yieldCurvePanel],
  );
  const focusItems = view.briefings.slice(0, 4);
  const eventRows =
    newsPanel?.rows.filter((row) => row.key.startsWith("news-event-")).slice(0, 3) ??
    [];
  const signalRows = signalPanel?.rows.slice(0, 6) ?? [];
  const searchQuery = searchValue.trim().toLowerCase();
  const refreshFeedback =
    refreshError ||
    refreshStatus ||
    `${view.stateLabel} · 行情 ${latestTradeDate || "—"} · 正式序列 ${formalTradeDate || "—"}`;
  const judgmentDate = macro?.as_of_date ?? latestTradeDate ?? "—";
  const macroObservationGate = buildMacroObservationGate(
    macroMeta,
    macroRefreshErrorWithData,
  );
  const heroSourceParts = [
    "分析观察（非正式）",
    macro
      ? `覆盖 ${macro.coverage.hit_count}/${macro.coverage.indicator_count}`
      : undefined,
    macro
      ? `工具产物 ${macro.coverage.script_count}/${macro.coverage.output_file_count}`
      : undefined,
  ].filter(Boolean);
  const judgmentTitle = macro?.conclusion.stance ?? view.stateLabel ?? "待判断";
  const judgmentSummary = macro?.conclusion.summary ?? view.summary;
  const judgmentAction =
    macro?.conclusion.recommended_action ?? view.stateDetail ?? "建议动作待返回";
  const regimeText = [view.stateLabel, view.marketDeskIntel?.curveShapeLabel]
    .filter(Boolean)
    .join(" · ");
  const observationTitle =
    macroObservationGate.blocked
      ? "暂停形成今日判断"
      : judgmentTitle || "观察结论待返回";
  const observationSummary =
    macroObservationGate.blocked
      ? `因${macroObservationGate.reasonSummary}，本页不展示来源结论摘要。请先核验来源证据，再形成判断。`
      : `非正式观察，仅供复核。口径 ${macroObservationGate.basis}；允许正式使用 ${macroObservationGate.formalUse}。${judgmentSummary || "来源摘要待返回。"}`;
  const observationAction =
    macroObservationGate.blocked
      ? "操作边界：不得将当前保留数据用于今日判断或建议动作。"
      : `待复核事项：${judgmentAction || "后续事项待返回"}`;
  const signalCards = signalRows.length > 0
    ? signalRows.map((row) => ({
        key: row.key,
        label: row.label,
        value: row.value,
        detail: signalDetail(row),
        tradeDate: row.tradeDate,
        tone: row.tone,
        source: row.source,
      }))
    : ledgerRows.slice(0, 6).map((row) => ({
        key: row.key,
        label: row.label,
        value: row.value,
        detail: [row.delta, row.source].filter(Boolean).join(" · "),
        tradeDate: row.reportDate,
        tone: row.tone,
        source: row.source,
      }));

  return (
    <section
      className={styles.screen}
      data-testid="module-home-market-dense"
      aria-label="市场工作台分析观察与市场证据"
    >
      <header className={styles.topRail} data-testid="module-home-toolbar">
        <nav
          className={styles.chapterTabs}
          aria-label="市场总览章节"
          data-testid="module-home-market-dense-chapter-tabs"
        >
          <a
            aria-label="分析观察"
            className={styles.activeTab}
            href="#market-overview-judgment"
          >
            分析观察
          </a>
          <a href="#market-overview-evidence">市场证据</a>
          <a href="#market-financial-charts-all">全部图表 12</a>
          <a href="#market-backend-data-all">数据核验 6</a>
        </nav>
        <div
          className={styles.utilityRail}
          data-testid="module-home-market-dense-utility"
        >
          <div
            className={styles.marketDate}
            data-testid="module-home-market-dense-date"
          >
            <span>数据日期</span>
            <strong>{latestTradeDate || "—"}</strong>
          </div>
          <span
            className={styles.updateState}
            data-testid="module-home-market-dense-status"
            data-tone={refreshError ? "error" : "ok"}
            title={regimeText || view.stateDetail}
          >
            <i aria-hidden="true" />
            {isRefreshing ? "刷新中" : view.stateLabel}
          </span>
          <label
            className={styles.searchBox}
            data-testid="module-home-market-dense-search"
          >
            <SearchOutlined aria-hidden="true" />
            <span className={styles.visuallyHidden}>搜索指标、图表或事件</span>
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
            title={refreshFeedback}
            onClick={() => void onRefreshData()}
          >
            <ReloadOutlined aria-hidden="true" />
            刷新
          </button>
        </div>
      </header>

      <section
        className={styles.chapterSection}
        id="market-overview-judgment"
        aria-labelledby="market-overview-judgment-title"
      >
        <header className={styles.sectionHeader}>
          <div className={styles.sectionTitle}>
            <span>01</span>
            <div>
              <h2 id="market-overview-judgment-title">分析观察</h2>
              <em>{heroSourceParts.join(" / ")}</em>
            </div>
          </div>
          <strong>数据日期 {judgmentDate}</strong>
        </header>

        <article className={styles.decisionHero}>
          <div className={styles.decisionMain}>
            <span className={styles.heroKicker}>仅供复核 · 非正式</span>
            <h3 data-testid="module-home-market-dense-observation-title">
              {observationTitle}
            </h3>
            <p data-testid="module-home-market-dense-observation-summary">
              {observationSummary}
            </p>
            <div
              className={styles.observationMeta}
              data-testid="module-home-market-dense-observation-meta"
            >
              <article className={styles.observationFact}>
                <span>口径 basis</span>
                <strong data-testid="module-home-market-dense-observation-basis">
                  {macroObservationGate.basis}
                </strong>
              </article>
              <article className={styles.observationFact}>
                <span>允许正式使用</span>
                <strong data-testid="module-home-market-dense-observation-formal">
                  {macroObservationGate.formalUse}
                </strong>
              </article>
              <article className={styles.observationFact}>
                <span>来源质量</span>
                <strong data-testid="module-home-market-dense-observation-quality">
                  {macroObservationGate.sourceQuality}
                </strong>
              </article>
              <article className={styles.observationFact}>
                <span>使用边界</span>
                <strong data-testid="module-home-market-dense-observation-gate">
                  {macroObservationGate.gate}
                </strong>
              </article>
            </div>
            <p
              className={styles.observationAction}
              data-testid="module-home-market-dense-observation-action"
              data-tone={
                macroObservationGate.blocked ? "watch" : "ok"
              }
            >
              {observationAction}
            </p>
          </div>
          <div className={styles.decisionFacts}>
            <div>
              <span>状态</span>
              <strong>{view.stateLabel}</strong>
            </div>
            <div>
              <span>曲线</span>
              <strong>{view.marketDeskIntel?.curveShapeLabel ?? "待返回"}</strong>
            </div>
            <div>
              <span>Crisis</span>
              <strong>
                {view.marketCrisisExplain?.crisisScore?.toFixed(2) ?? "—"} ·{" "}
                {view.marketCrisisExplain?.regime ?? "待返回"}
              </strong>
            </div>
          </div>
        </article>

        <section className={styles.marketTape} aria-label="市场行情带">
          {tapeMetrics.map((metric) => (
            <article
              className={styles.tapeCell}
              data-tone={metric.tone}
              key={metric.key}
              title={metric.title}
            >
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <em>{metric.delta}</em>
              <time>{metricReportDate(metric)}</time>
            </article>
          ))}
        </section>

        <div className={styles.judgmentGrid}>
          <article className={styles.infoPanel}>
            <header className={styles.panelHeader}>
              <h3>最新追踪</h3>
              <Link to="/news-events">全部事件 →</Link>
            </header>
            <div className={styles.eventRows}>
              {eventRows.length > 0 ? (
                eventRows.map((row, index) => (
                  <article key={row.key}>
                    <time>{String(index + 1).padStart(2, "0")}</time>
                    <strong>{row.value}</strong>
                    <span>{[row.tradeDate, row.source].filter(Boolean).join(" · ")}</span>
                  </article>
                ))
              ) : (
                <div className={styles.eventEmpty}>
                  {newsPanel?.stateDetail ?? "新闻事件待读取"}
                </div>
              )}
            </div>
          </article>

          <article className={styles.infoPanel} id="market-overview-focus">
            <header className={styles.panelHeader}>
              <h3>焦点解读</h3>
              <span>利率 / 跨资 / 宏观 / 事件</span>
            </header>
            <div className={styles.focusGrid}>
              {focusItems.map((item) => {
                const matchesSearch =
                  searchQuery.length === 0 ||
                  `${item.title} ${item.conclusion} ${item.evidence}`
                    .toLowerCase()
                    .includes(searchQuery);
                return (
                  <article
                    className={styles.focusCard}
                    data-search-match={matchesSearch ? "true" : "false"}
                    data-tone={item.tone}
                    key={item.title}
                  >
                    <span>{item.title}</span>
                    <strong>{item.conclusion}</strong>
                    <em>{item.evidence}</em>
                  </article>
                );
              })}
            </div>
          </article>

          <article className={styles.infoPanel} id="market-overview-actions">
            <header className={styles.panelHeader}>
              <h3>P0 - P2 核验队列</h3>
              <span>优先级 / 核验事项 / 证据 / 入口</span>
            </header>
            <div className={styles.queueHead} aria-hidden="true">
              <span>优先级</span>
              <span>核验事项</span>
              <span>证据</span>
              <span>入口</span>
            </div>
            <div className={styles.queueRows}>
              {actionItems.map((item) => (
                <Link
                  className={styles.queueRow}
                  data-tone={item.tone}
                  key={item.key}
                  to={item.path}
                >
                  <span>{item.rank}</span>
                  <strong>{item.title}</strong>
                  <em>{item.evidence.join(" / ") || "待返回"}</em>
                  <b>{item.label}</b>
                </Link>
              ))}
            </div>
          </article>
        </div>
      </section>

      <section
        className={styles.chapterSection}
        id="market-overview-evidence"
        aria-labelledby="market-overview-evidence-title"
      >
        <header className={styles.sectionHeader}>
          <div className={styles.sectionTitle}>
            <span>02</span>
            <div>
              <h2 id="market-overview-evidence-title">市场证据</h2>
              <em>曲线 / 利率 / 跨资产 / 信号 / 事件</em>
            </div>
          </div>
          <strong>数据日期 {judgmentDate}</strong>
        </header>

        <div className={styles.evidenceLayout}>
          <div className={styles.evidencePrimary}>
            {charts.slice(0, 2).map((item) => (
              <DenseChartCard
                canvasHeight={178}
                className={styles.primaryChart}
                item={item}
                key={`${item.sectionKey}-${item.chart.key}`}
                searchQuery={searchQuery}
              />
            ))}
          </div>

          <div className={styles.evidenceSecondary}>
            {charts.slice(2).map((item) => (
              <DenseChartCard
                canvasHeight={194}
                className={styles.secondaryChart}
                item={item}
                key={`${item.sectionKey}-${item.chart.key}`}
                searchQuery={searchQuery}
              />
            ))}
            <DenseChartCard
              canvasHeight={194}
              className={styles.secondaryChart}
              item={{
                sectionKey: "rates",
                indexLabel: "D",
                chart: liquidityChart,
              }}
              searchQuery={searchQuery}
            />
            <DenseMacroPulseCard
              asOfDate={macro?.as_of_date ?? ""}
              rows={macroPulseRows}
              searchQuery={searchQuery}
            />
          </div>

          <DenseNewsDensityCard
            density={newsDensity}
            events={news?.events ?? []}
            searchQuery={searchQuery}
            totalRows={news?.total_rows ?? 0}
          />
        </div>

        <div className={styles.signalStrip} id="market-overview-signals">
          {signalCards.map((row) => (
            <article
              className={styles.signalCard}
              data-tone={toneBadge(row.tone)}
              key={row.key}
              title={`${row.tradeDate} · ${row.source}`}
            >
              <span>{row.label}</span>
              <strong>{row.value}</strong>
              <em>{row.detail}</em>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
