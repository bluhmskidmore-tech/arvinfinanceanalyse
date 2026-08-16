import { useMemo } from "react";
import { Link } from "react-router-dom";

import type { ChoiceNewsEvent, ResultMeta } from "../../../api/contracts";
import ReactECharts from "../../../lib/echarts";
import { EM_DASH } from "../../../utils/format";
import { summarizeMacroNewsEvent } from "../dashboard-home/adapters/macroNewsPresentation";
import { buildActionQueue } from "./marketActionQueueModel";
import type { MarketChartPalette } from "./marketChartPalette";
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
  formatDenseNewsTopicLabel,
  type DenseMacroPulseRow,
  type DenseNewsDensity,
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
  /** 搜索框已上移到页壳工具栏，这里只消费搜索词做卡片匹配。 */
  searchValue: string;
  chartPalette?: MarketChartPalette;
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

/** 仅做展示层拆分：把已格式化的“数值 单位”拆开，避免长单位截断数值。 */
function splitMetricValue(value: string) {
  const match = /^(\S+)\s+(.+)$/.exec(value.trim());
  return match
    ? { amount: match[1], unit: match[2] }
    : { amount: value, unit: "" };
}

function toneBadge(tone: ModuleHomeTone | "up" | "down" | "ok" | "muted") {
  if (tone === "error" || tone === "up") return "alert";
  if (tone === "watch") return "watch";
  if (tone === "down" || tone === "ok") return "ok";
  return "muted";
}

/**
 * 行情带 tone 由原始数值计算，微小变动格式化后显示为 ±0 时按中性处理（C9），
 * 避免「+0 却着绿/红」的自相矛盾读数。
 */
function normalizeTapeTone(tone: "up" | "down" | "ok" | "muted", delta: string) {
  if (tone !== "up" && tone !== "down") return tone;
  const numericToken = delta.trim().match(/^[+-]?([\d,]+(?:\.\d+)?)/)?.[1];
  if (!numericToken) return tone;
  return Number(numericToken.replace(/,/g, "")) === 0 ? "muted" : tone;
}

/** 事件行 content_type 分类 token（news/major_news）中文化，未登记 token 收进 title（C13）。 */
const NEWS_SOURCE_LABELS: Record<string, string> = {
  news: "新闻",
  major_news: "要闻",
};

function newsEventMeta(row: ModuleHomeDetailRow) {
  const sourceLabel = row.source ? NEWS_SOURCE_LABELS[row.source] : undefined;
  return {
    visible: [row.tradeDate, sourceLabel].filter(Boolean).join(" · "),
    full: [row.tradeDate, row.source].filter(Boolean).join(" · "),
  };
}

/** 脚本/产物类运维状态不属于市场信号（C14），改挂在 01 区状态栏，文件名收 title。 */
const OPS_SIGNAL_PATTERN = /脚本|产物|output[_\s-]?file|script/i;

function compactEventTime(value: string) {
  return value ? value.replace("T", " ").slice(5, 16) : "时间未返回";
}

function signalDetail(row: ModuleHomeDetailRow) {
  const detailParts = [row.detail, row.source]
    .map((part) => part?.trim())
    .filter((part): part is string => Boolean(part && part !== EM_DASH));
  return detailParts[0] ?? row.tradeDate ?? EM_DASH;
}

const FALLBACK_MODE_LABELS: Record<string, string> = {
  none: "无",
  backfill: "回填",
};

function fallbackLabel(meta: ResultMeta | undefined) {
  if (!meta) return "元数据缺失";
  if (meta.fallback_mode === "none" && !meta.fallback_date) return "无";
  const mode = FALLBACK_MODE_LABELS[meta.fallback_mode] ?? meta.fallback_mode;
  return `${mode}${meta.fallback_date ? `/${meta.fallback_date}` : ""}`;
}

/** 01 区状态面板不透出英文枚举（C13）：basis/formal_use_allowed 展示为中文。 */
const OBSERVATION_BASIS_LABELS: Record<string, string> = {
  formal: "正式口径",
  scenario: "情景口径",
  analytical: "分析口径",
  ledger: "台账口径",
  mock: "样例口径",
};

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
    basis: meta ? OBSERVATION_BASIS_LABELS[meta.basis] ?? meta.basis : "未返回",
    formalUse: meta ? (meta.formal_use_allowed ? "是" : "否") : "未返回",
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
  readingGuide,
}: {
  item: DenseChart;
  searchQuery: string;
  className?: string;
  canvasHeight: number;
  readingGuide?: string;
}) {
  const effectiveReadingGuide = readingGuide ?? item.chart.readingGuide;
  const searchableText = `${item.chart.title} ${item.chart.subtitle}`.toLowerCase();
  const isSearchMatch =
    searchQuery.length === 0 || searchableText.includes(searchQuery);
  return (
    <article
      className={[styles.chartCard, className].filter(Boolean).join(" ")}
      data-has-reading-guide={effectiveReadingGuide ? "true" : "false"}
      data-search-match={isSearchMatch ? "true" : "false"}
      data-testid={`module-home-market-dense-chart-${item.chart.key}`}
    >
      <header className={styles.cardHeader}>
        <div>
          <span className={styles.cardIndex}>{item.indexLabel}</span>
          <h3>{item.chart.title}</h3>
        </div>
        <span title={item.chart.subtitle}>{item.chart.subtitle}</span>
      </header>
      {effectiveReadingGuide ? (
        <p className={styles.chartGuide} title={effectiveReadingGuide}>
          {effectiveReadingGuide}
        </p>
      ) : null}
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
      <footer title={item.chart.footnote}>{item.chart.footnote}</footer>
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
    .map(
      (row) =>
        `${row.label} ${row.previousValue} ${row.latestValue} ${row.change} ${row.source}`,
    )
    .join(" ")}`.toLowerCase();
  const isSearchMatch =
    searchQuery.length === 0 || searchableText.includes(searchQuery);
  // 「绝对变化/百分比变化」字样上收列头（C16）；口径混排时列头退回「变化」，行内以悬浮说明。
  const changeLabels = [
    ...new Set(
      rows
        .map((row) => row.changeLabel)
        .filter((label) => label !== "变化未返回"),
    ),
  ];
  const changeHeader = changeLabels.length === 1 ? changeLabels[0] : "变化";
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
        <span title="各行日期见悬浮 · 单位按原始口径">
          各行日期见悬浮 · 单位按原始口径
        </span>
      </header>
      <div className={`${styles.chartCanvas} ${styles.macroPulse}`}>
        <div className={styles.pulseColumns} aria-hidden="true">
          <span>指标</span>
          <span>前值 → 最新值</span>
          <span>{changeHeader}</span>
        </div>
        <div className={styles.pulseRows}>
          {rows.length > 0 ? (
            rows.map((row) => (
              <div
                className={styles.pulseRow}
                key={row.key}
                title={`最新日期 ${row.latestDate} · 来源 ${row.source}${changeLabels.length > 1 ? ` · ${row.changeLabel}` : ""}`}
              >
                <span>{row.label}</span>
                <div
                  className={styles.pulseValueFlow}
                  aria-label={`${row.label}：前值 ${row.previousValue}，最新值 ${row.latestValue}，${row.changeLabel} ${row.change}；最新日期 ${row.latestDate}；来源 ${row.source}`}
                >
                  <span>{row.previousValue}</span>
                  <i aria-hidden="true">→</i>
                  <strong>{row.latestValue}</strong>
                </div>
                <em>
                  <strong>{row.change}</strong>
                </em>
              </div>
            ))
          ) : (
            <div className={styles.compactEmpty}>后端分析暂未返回可展示指标</div>
          )}
        </div>
      </div>
      <footer
        title={`分析截至 ${asOfDate || EM_DASH}；各指标最新日期以行内悬浮信息为准。变化列按单位区分绝对变化或百分比，不代表利好或利空。`}
      >
        分析截至 {asOfDate || EM_DASH} ·
        各指标日期见悬浮；变化按单位区分绝对值或百分比
      </footer>
    </article>
  );
}

function DenseNewsDensityCard({
  density,
  events,
  searchQuery,
  totalRows,
  excludedFutureRows,
}: {
  density: DenseNewsDensity;
  events: ChoiceNewsEvent[];
  searchQuery: string;
  totalRows: number;
  excludedFutureRows: number;
}) {
  const searchableText = `事件流入密度 ${events
    .map((event) => `${event.topic_code} ${event.payload_text ?? ""}`)
    .join(" ")}`.toLowerCase();
  const isSearchMatch =
    searchQuery.length === 0 || searchableText.includes(searchQuery);
  const sampleRangeLabel =
    density.sampledEvents > 0
      ? `有效样本区间 ${density.startDate || EM_DASH}–${density.endDate || EM_DASH}`
      : "无有效样本区间";
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
          最新有效样本 {density.sampledEvents.toLocaleString("zh-CN")} /
          当前查询总记录 {totalRows.toLocaleString("zh-CN")}
        </span>
      </header>
      <div className={`${styles.chartCanvas} ${styles.newsDensity}`}>
        <div className={styles.heatmapPanel}>
          {density.rows.length > 0 ? (
            <>
              <div className={styles.heatmapGrid}>
                <span />
                {density.hourLabels.map((hour, index) => (
                  <time
                    data-label={
                      index === 0 || index === 5 || index === 11
                        ? "true"
                        : "false"
                    }
                    key={hour}
                  >
                    {hour}
                  </time>
                ))}
                {density.rows.map((row) => (
                  <div className={styles.heatmapRow} key={row.key}>
                    <span title={row.key}>{row.label}</span>
                    {row.cells.map((cell, bucketIndex) => {
                      const bucketStart = density.hourLabels[bucketIndex];
                      const bucketEnd = String(
                        Number(bucketStart) + 1,
                      ).padStart(2, "0");
                      const cellLabel = `${row.label}（原码 ${row.key}）· received_at ${bucketStart}:00–${bucketEnd}:59 · ${cell.count} 条`;
                      return (
                        <i
                          aria-label={cellLabel}
                          data-intensity={cell.intensity}
                          key={cell.key}
                          role="img"
                          title={cellLabel}
                        />
                      );
                    })}
                  </div>
                ))}
              </div>
              <div
                aria-label="颜色图例：无、较少、较多"
                className={styles.heatmapLegend}
              >
                <span>无</span>
                <i data-intensity={0} />
                <span>较少</span>
                <i data-intensity={2} />
                <span>较多</span>
                <i data-intensity={4} />
              </div>
            </>
          ) : (
            <div className={styles.heatmapEmpty}>无可分桶事件</div>
          )}
        </div>
        <div className={styles.newsMiniFeed}>
          <div className={styles.newsMiniHead}>
            <span>时间</span>
            <span>最新事件</span>
            <span>主题</span>
          </div>
          {events.length > 0 ? (
            events.slice(0, 3).map((event) => {
              const eventText =
                summarizeMacroNewsEvent(event) ||
                event.error_msg ||
                event.event_key;
              return (
                <article key={event.event_key}>
                  <time>{compactEventTime(event.received_at)}</time>
                  <strong title={eventText}>{eventText}</strong>
                  <em title={event.topic_code || event.group_id || "未分类"}>
                    {formatDenseNewsTopicLabel(
                      event.topic_code || event.group_id || "未分类",
                    )}
                  </em>
                </article>
              );
            })
          ) : (
            <div className={styles.compactEmpty}>新闻事件暂未返回</div>
          )}
        </div>
      </div>
      <footer
        title={`${sampleRangeLabel}；按 received_at 接收时间两小时分桶；颜色仅代表最新样本内相对接收密度，不代表重要性、情绪或影响${excludedFutureRows > 0 ? `；已排除未来记录 ${excludedFutureRows.toLocaleString("zh-CN")} 条` : ""}`}
      >
        {sampleRangeLabel} · 按 received_at 两小时分桶 ·
        颜色仅代表样本内相对接收密度，不代表重要性、情绪或影响
        {excludedFutureRows > 0
          ? ` · 已排除未来记录 ${excludedFutureRows.toLocaleString("zh-CN")} 条`
          : ""}
      </footer>
    </article>
  );
}

export function MarketOverviewDenseFirstScreen({
  view,
  queries,
  latestTradeDate,
  searchValue,
  chartPalette,
}: MarketOverviewDenseFirstScreenProps) {
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
        palette: chartPalette,
      }),
    [catalog, chartPalette, latest, macro, news, rates, strategies],
  );
  const charts = useMemo(() => selectedDenseCharts(sections), [sections]);
  const liquidityChart = useMemo(
    () => buildDenseLiquidityChartSpec(rates, chartPalette),
    [chartPalette, rates],
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
  const allSignalRows = signalPanel?.rows ?? [];
  const opsSignalRow = allSignalRows.find((row) => OPS_SIGNAL_PATTERN.test(row.label));
  const signalRows = allSignalRows
    .filter((row) => !OPS_SIGNAL_PATTERN.test(row.label))
    .slice(0, 6);
  const searchQuery = searchValue.trim().toLowerCase();
  const judgmentDate = macro?.as_of_date ?? latestTradeDate ?? EM_DASH;
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
          <aside className={styles.decisionAside} aria-label="状态与口径事实">
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
                  {view.marketCrisisExplain?.crisisScore?.toFixed(2) ?? EM_DASH} ·{" "}
                  {view.marketCrisisExplain?.regime ?? "待返回"}
                </strong>
              </div>
              {opsSignalRow ? (
                <div
                  data-testid="module-home-market-dense-ops-signal"
                  title={[
                    ...new Set(
                      [opsSignalRow.detail, opsSignalRow.source].filter(Boolean),
                    ),
                  ].join("；")}
                >
                  <span>{opsSignalRow.label}</span>
                  <strong>{opsSignalRow.value}</strong>
                </div>
              ) : null}
            </div>
            <div
              className={styles.observationMeta}
              data-testid="module-home-market-dense-observation-meta"
            >
              <article className={styles.observationFact}>
                <span>口径</span>
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
                <strong
                  data-testid="module-home-market-dense-observation-quality"
                  title={macroObservationGate.sourceQuality}
                >
                  {macroObservationGate.sourceQuality}
                </strong>
              </article>
              <article className={styles.observationFact}>
                <span>使用边界</span>
                <strong
                  data-testid="module-home-market-dense-observation-gate"
                  title={macroObservationGate.gate}
                >
                  {macroObservationGate.gate}
                </strong>
              </article>
            </div>
          </aside>
        </article>

        <section className={styles.marketTape} aria-label="市场行情带">
          {tapeMetrics.map((metric) => {
            const { amount, unit } = splitMetricValue(metric.value);
            return (
              <article
                className={styles.tapeCell}
                data-tone={normalizeTapeTone(metric.tone, metric.delta)}
                key={metric.key}
                title={metric.title}
              >
                <span>{metric.label}</span>
                <strong>
                  {amount}
                  {unit ? <small>{unit}</small> : null}
                </strong>
                <em>{metric.delta}</em>
                <time>{metric.tradeDate ?? EM_DASH}</time>
              </article>
            );
          })}
        </section>

        <div className={styles.judgmentGrid}>
          <article className={styles.infoPanel}>
            <header className={styles.panelHeader}>
              <h3>最新追踪</h3>
              <Link to="/news-events">全部事件 →</Link>
            </header>
            <div className={styles.eventRows}>
              {eventRows.length > 0 ? (
                eventRows.map((row, index) => {
                  const meta = newsEventMeta(row);
                  return (
                    <article key={row.key}>
                      <time>{String(index + 1).padStart(2, "0")}</time>
                      <strong>{row.value}</strong>
                      <span title={meta.full}>{meta.visible}</span>
                    </article>
                  );
                })
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
                    title={`${item.conclusion}（证据：${item.evidence}）`}
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
            </header>
            <div className={styles.queueHead} aria-hidden="true">
              <span>优先级</span>
              <span>核验事项 / 证据</span>
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
                canvasHeight={186}
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
                canvasHeight={202}
                className={styles.secondaryChart}
                item={item}
                key={`${item.sectionKey}-${item.chart.key}`}
                searchQuery={searchQuery}
              />
            ))}
            <DenseChartCard
              canvasHeight={180}
              className={styles.secondaryChart}
              item={{
                sectionKey: "rates",
                indexLabel: "D",
                chart: liquidityChart,
              }}
              readingGuide={liquidityChart.readingHint}
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
            excludedFutureRows={news?.excluded_future_rows ?? 0}
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
