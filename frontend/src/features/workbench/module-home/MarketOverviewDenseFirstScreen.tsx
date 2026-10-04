import { useMemo, useState, type ReactNode } from "react";
import { Drawer } from "antd";
import { Link } from "react-router-dom";

import type {
  MarketOverviewCrisis,
  MarketOverviewCrisisRiskGate,
  MarketOverviewCrisisTrend,
  MarketOverviewGateIssue,
  MarketOverviewNews,
  MarketOverviewPulseItem,
  MarketOverviewTapeSlot,
} from "../../../api/contracts";
import { StateSurface, type SurfaceStatus } from "../../../components/layout";
import { DataTable } from "../../../components/layout/DataTable";
import { ChartCard } from "../../../components/charts/ChartCard";
import type { ChartCardHeight } from "../../../components/charts/chartCardScale";
import { EM_DASH } from "../../../utils/format";
import { repairActionCodeLabel } from "../../macro-toolkit/lib/macroToolkitDataHealthSupport";
import type { MarketChartPalette } from "./marketChartPalette";
import {
  buildMarketFinancialChartSections,
  DENSE_FIRST_SCREEN_CHART_PICKS,
  type MarketFinancialChartSection,
  type MarketFinancialChartSpec,
} from "./marketFinancialChartsModel";
import { MarketFundingRatesObservations } from "./MarketFundingRatesObservations";
import { MarketPortfolioScenarioPanel } from "./MarketPortfolioScenarioPanel";
import { MarketRiskObservation } from "./MarketRiskObservation";
import { buildMarketSourceLink } from "./marketSourceContext";
import { isMarketTechnicalReason, marketBusinessReason } from "./marketRiskObservationModel";
import { formatDenseNewsTopicLabel } from "./marketOverviewDenseModel";
import type {
  ModuleHomeSourceQueries,
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
  /** 搜索框已上移到页壳工具栏，这里只消费搜索词做卡片匹配。 */
  searchValue: string;
  chartPalette?: MarketChartPalette;
  chapterNav?: ReactNode;
};

function selectedDenseCharts(
  sections: MarketFinancialChartSection[],
): DenseChart[] {
  const byKey = new Map(sections.map((section) => [section.key, section]));
  return DENSE_FIRST_SCREEN_CHART_PICKS.flatMap((pick) => {
    const chart = byKey.get(pick.sectionKey)?.charts[pick.chartIndex];
    return chart ? [{ ...pick, chart }] : [];
  });
}

/** 仅拆分已格式化文本，保留数值精度与符号，让单位和主值各用对应层级。 */
function splitMetricValue(value: string) {
  const match = /^(\S+)\s+(.+)$/.exec(value.trim())
    ?? /^(\S+?)(%|‰|bps?)$/i.exec(value.trim());
  return match
    ? { amount: match[1], unit: match[2] }
    : { amount: value, unit: "" };
}

function compactEventTime(value: string) {
  return value ? value.replace("T", " ").slice(5, 16) : "时间未返回";
}

function snapshotState(
  query: ModuleHomeSourceQueries["marketSnapshot"],
): SurfaceStatus {
  if (query?.isLoading && !query.data) return "loading";
  if (query?.isError && !query.data) return "error";
  if (!query?.data) return "empty";
  if (query.isError) return "partial";
  const meta = query.data.result_meta;
  if (meta.quality_flag === "stale" || meta.vendor_status === "vendor_stale") return "stale";
  if (meta.quality_flag !== "ok" || meta.vendor_status !== "ok") return "partial";
  return "ready";
}

function compactNumber(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return EM_DASH;
  return value.toLocaleString("zh-CN", { maximumFractionDigits: Math.abs(value) < 10 ? 4 : 2 });
}

function unitSuffix(unit: string | null | undefined) {
  const normalized = unit?.trim();
  if (!normalized || normalized.toLowerCase() === "unknown") return "";
  const label = ["point", "index"].includes(normalized.toLowerCase()) ? "点" : normalized;
  return /^(?:%|‰|bp|bps)$/i.test(label) ? label : ` ${label}`;
}

function tapeValue(slot: MarketOverviewTapeSlot) {
  return slot.status === "unresolved" ? "未绑定" : slot.value == null ? EM_DASH : `${compactNumber(slot.value)}${unitSuffix(slot.unit)}`;
}

function tapeDelta(slot: MarketOverviewTapeSlot) {
  if (slot.status === "unresolved" || slot.change == null) return "未返回";
  if (slot.change === 0) return "持平";
  const sign = slot.change > 0 ? "+" : "";
  return `${sign}${compactNumber(slot.change)}${unitSuffix(slot.change_unit)}`;
}

function tapeTone(slot: MarketOverviewTapeSlot) {
  if (slot.status === "unresolved" || slot.tone_hint === "unavailable" || slot.change === 0) return "muted";
  if (slot.kind === "rate" && slot.tone_hint === "up") return "warn";
  if (slot.kind === "rate" && slot.tone_hint === "down") return "muted";
  return slot.tone_hint;
}

function basisLabel(basis: string | null) {
  if (basis === "formal") return "正式";
  if (basis === "analytical") return "分析";
  return basis || "口径待返回";
}

/** 业务结论位不展示回执对象路径；完整原因仍在可展开的核验依据中保留。 */
function hasReceiptPath(text: string | null | undefined) {
  return isMarketTechnicalReason(text);
}

function actionEvidenceLabel(actionKey: string, evidence: Record<string, unknown>) {
  const reviewNeeded = evidence.review_needed;
  if (typeof reviewNeeded === "number") {
    return [`待人工复核 ${reviewNeeded} 项`];
  }
  if (actionKey.startsWith("rate_move_")) {
    const changeBp = evidence.change_bp;
    const thresholdBp = evidence.threshold_bp;
    return typeof changeBp === "number" && typeof thresholdBp === "number"
      ? [`变动 ${changeBp > 0 ? "+" : ""}${changeBp.toFixed(1)}bp，复核阈值 ±${thresholdBp.toFixed(1)}bp`]
      : [];
  }
  if (actionKey === "crisis_regime_review") {
    const score = evidence.score;
    const threshold = evidence.threshold;
    const gateLabel = evidence.eligible === false
      ? "当前风险门不可用"
      : evidence.triggered === true
        ? "当前风险门已触发"
        : "当前风险门需复核";
    const scoreLabel = typeof score === "number" ? `分数 ${score.toFixed(2)}` : "";
    const thresholdLabel = typeof threshold === "number" ? `阈值 ${threshold.toFixed(2)}` : "";
    return [[gateLabel, scoreLabel, thresholdLabel].filter(Boolean).join("，")];
  }
  if (actionKey.startsWith("surface_stale_")) {
    const ageDays = evidence.age_days;
    return typeof ageDays === "number"
      ? [`距页面计算日 ${Math.round(ageDays)} 天`]
      : [];
  }
  if (actionKey === "refresh_gate_blocked") {
    return ["核心宏观分析或刷新回执当前不可用"];
  }
  return [];
}

function issueForAction(
  actionKey: string,
  issues: MarketOverviewGateIssue[],
) {
  const issueKey = actionKey.startsWith("gate_review_")
    ? actionKey.slice("gate_review_".length)
    : "";
  return issues.find((issue) => issue.key === issueKey);
}

function crisisTrendDeltaLabel(windowPoints: number, delta: number | null) {
  if (windowPoints < 2 || delta == null) return `近${windowPoints || 20}期趋势待返回`;
  const magnitude = Math.abs(delta) > 0 && Math.abs(delta) < 0.01 ? "<0.01" : Math.abs(delta).toFixed(2);
  if (delta > 0) return `近${windowPoints}期上升${magnitude}`;
  if (delta < 0) return `近${windowPoints}期回落${magnitude}`;
  return `近${windowPoints}期基本持平`;
}

function crisisTrendLabel(trend: MarketOverviewCrisisTrend | undefined, requestedWindow: number) {
  if (!trend || trend.direction === "insufficient" || trend.window_points < 2) {
    return `近${requestedWindow}期趋势待返回`;
  }
  const delta = trend.score_change;
  if (delta == null) return `近${requestedWindow}期趋势待返回`;
  const magnitude = Math.abs(delta) > 0 && Math.abs(delta) < 0.01 ? "<0.01" : Math.abs(delta).toFixed(2);
  if (trend.direction === "rising") return `近${requestedWindow}期上升${magnitude}`;
  if (trend.direction === "falling") return `近${requestedWindow}期回落${magnitude}`;
  if (trend.direction === "flat") return `近${requestedWindow}期基本持平`;
  return `近${requestedWindow}期变化${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`;
}

function crisisTrendForWindow(crisis: MarketOverviewCrisis | undefined, requestedWindow: number) {
  const trend = crisis?.score_trends?.find(
    (item) => item.requested_window_points === requestedWindow,
  );
  if (trend) return crisisTrendLabel(trend, requestedWindow);
  if (requestedWindow === 20 && crisis?.delta) {
    return crisisTrendDeltaLabel(crisis.delta.window_points, crisis.delta.score_delta);
  }
  return `近${requestedWindow}期趋势待返回`;
}

function crisisWarningLabel(code: string) {
  if (code === "CREDIT_SPREAD_UNAVAILABLE") return "信用利差不可用";
  return repairActionCodeLabel(code);
}

function crisisQualityEvidence(crisis: MarketOverviewCrisis | undefined) {
  if (!crisis || (crisis.data_status === "complete" && crisis.risk_gate?.eligible)) return [];
  const parts: string[] = [];
  if (crisis.available_component_count != null && crisis.component_count != null) {
    parts.push(`组件 ${crisis.available_component_count}/${crisis.component_count}`);
  }
  parts.push(...(crisis.warnings ?? []).map(crisisWarningLabel));
  const aaFiveYear = crisis.input_evidence?.inputs?.find((item) => item.field === "aa_5y");
  if (aaFiveYear) {
    parts.push(`AA 5Y 最新日期 ${aaFiveYear.latest_date ?? "待返回"}`);
  }
  return Array.from(new Set(parts));
}

function crisisRiskGateLabel(riskGate: MarketOverviewCrisisRiskGate | undefined) {
  if (!riskGate) return "风险门待返回";
  const threshold = riskGate.threshold.toFixed(2);
  if (!riskGate.eligible) return "风险门不可用 · 数据不完整";
  if (riskGate.triggered) return `高风险门已触发 · 阈值 ${threshold}`;
  return `高风险门未触发 · 阈值 ${threshold}`;
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
  canvasHeight: ChartCardHeight;
  readingGuide?: string;
}) {
  const effectiveReadingGuide = readingGuide ?? item.chart.readingGuide;
  const searchableText = `${item.chart.title} ${item.chart.subtitle}`.toLowerCase();
  const isSearchMatch =
    searchQuery.length === 0 || searchableText.includes(searchQuery);
  return (
    <article
      id={`market-overview-chart-${item.chart.key}`}
      tabIndex={-1}
      className={[styles.chartCard, className].filter(Boolean).join(" ")}
      data-has-reading-guide={effectiveReadingGuide ? "true" : "false"}
      data-chartcard-shell="true"
      data-search-match={isSearchMatch ? "true" : "false"}
      data-testid={`module-home-market-dense-chart-${item.chart.key}`}
    >
      <header className={styles.observationChartHeader}>
        <h3>{item.chart.title}</h3>
        <p>{item.chart.subtitle}</p>
      </header>
      <ChartCard
        flat
        option={item.chart.option}
        legend={item.chart.key === "cross-asset-move" ? "none" : undefined}
        legendRows={item.chart.key === "key-rate-trend" ? 2 : undefined}
        height={canvasHeight}
        emptyMessage="暂无足够数据绘制图表"
        ariaLabel={item.chart.title}
      />
      <p className={styles.chartBoundary}>
        {item.chart.key === "cross-asset-move"
          ? "各项比较日期见图中标签，非同日涨跌排名。"
          : "各序列按自身日期展示；缺口留空，不据此认定因果。"}
      </p>
      <details className={styles.chartDetails}>
        <summary>图表说明与使用限制</summary>
        {effectiveReadingGuide ? <p>{effectiveReadingGuide}</p> : null}
        <p>{item.chart.footnote}</p>
      </details>
    </article>
  );
}

function DenseMacroPulseCard({
  rows,
  searchQuery,
  asOfDate,
}: {
  rows: MarketOverviewPulseItem[];
  searchQuery: string;
  asOfDate: string;
}) {
  const searchableText = `指标变动雷达 ${rows
    .map(
      (row) =>
        `${row.label} ${row.previous_value} ${row.latest_value} ${row.change} ${row.source}`,
    )
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
        <span>各项观测日期见行内</span>
      </header>
      <div className={`${styles.chartCanvas} ${styles.macroPulse}`}>
        <DataTable
          rows={rows}
          rowKey="key"
          rowHeaderKey="name"
          ariaLabel="宏观指标变动"
          emptyMessage="暂无可展示指标"
          columns={[
            {
              key: "name", title: "指标与观测日期", width: 220,
              render: (row) => (
                <span className={styles.pulseMetricLabel} title={`来源 ${row.source ?? EM_DASH}${row.reason ? `；${row.reason}` : ""}`}>
                  {row.label}
                  <time dateTime={row.latest_date ?? undefined} aria-label={`观测日期 ${row.latest_date ?? EM_DASH}`}>
                    {row.latest_date ?? EM_DASH}
                  </time>
                </span>
              ),
            },
            {
              key: "previous", title: "前值", align: "numeric", width: 130,
              render: (row) => `${compactNumber(row.previous_value)}${row.previous_value == null ? "" : unitSuffix(row.unit)}`,
            },
            {
              key: "latest", title: "最新值", align: "numeric", width: 150,
              render: (row) => (
                <div
                  className={styles.pulseValueFlow}
                  aria-label={`${row.label}：前值 ${compactNumber(row.previous_value)}${unitSuffix(row.unit)}，最新值 ${compactNumber(row.latest_value)}${unitSuffix(row.unit)}，变化 ${compactNumber(row.change)}${unitSuffix(row.change_unit)}；最新日期 ${row.latest_date ?? EM_DASH}；来源 ${row.source ?? EM_DASH}`}
                >
                  <strong>{compactNumber(row.latest_value)}{row.latest_value == null ? "" : unitSuffix(row.unit)}</strong>
                  {!unitSuffix(row.unit) ? <small>单位待确认</small> : null}
                </div>
              ),
            },
            {
              key: "change", title: "变化", align: "numeric", width: 170,
              render: (row) => (
                <div className={styles.pulseValueFlow}>
                  <strong>{compactNumber(row.change)}{row.change == null ? "" : unitSuffix(row.change_unit)}</strong>
                  {!unitSuffix(row.change_unit) ? <small>单位待确认</small> : null}
                </div>
              ),
            },
          ]}
        />
      </div>
      <footer
        className={styles.pulseFootnote}
        title={`分析日期 ${asOfDate || EM_DASH}；分析日期不代表指标所属期，各项观测日期见行内。指标变动不代表利好或利空。`}
      >
        <span>分析日期 {asOfDate || EM_DASH}</span>
        <span>分析日期不代表指标所属期</span>
      </footer>
    </article>
  );
}

function DenseNewsDensityCard({
  news,
  searchQuery,
}: {
  news: MarketOverviewNews | undefined;
  searchQuery: string;
}) {
  const density = news?.density ?? {
    tz: "Asia/Shanghai",
    bucket_hours: 2,
    topics: [],
    max_count: 0,
  };
  const events = news?.latest ?? [];
  const sampledEvents = news?.granularity.datetime_rows ?? 0;
  const totalRows = news?.sample.total_rows ?? 0;
  const excludedFutureRows = news?.sample.excluded_future_rows ?? 0;
  const hourLabels = Array.from(
    { length: Math.max(1, Math.ceil(24 / density.bucket_hours)) },
    (_, index) => String(index * density.bucket_hours).padStart(2, "0"),
  );
  const searchableText = `事件流入密度 ${events
    .map((event) => `${event.topic_code ?? ""} ${event.summary ?? ""}`)
    .join(" ")}`.toLowerCase();
  const isSearchMatch =
    searchQuery.length === 0 || searchableText.includes(searchQuery);
  const sampleRangeLabel = news?.sample.latest_received_at
    ? `有效样本截至 ${news.sample.latest_received_at.slice(0, 10)}`
    : "无有效样本日期";
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
          最新有效样本 {sampledEvents.toLocaleString("zh-CN")} /
          当前查询总记录 {totalRows.toLocaleString("zh-CN")}
        </span>
        <Link to="/news-events">全部事件</Link>
      </header>
      <div className={`${styles.chartCanvas} ${styles.newsDensity}`}>
        <div className={styles.heatmapPanel}>
          {density.topics.length > 0 ? (
            <>
              <div className={styles.heatmapGrid}>
                <span />
                {hourLabels.map((hour, index) => (
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
                {density.topics.map((row) => (
                  <div className={styles.heatmapRow} key={row.key}>
                    <span title={row.key}>{row.label}</span>
                    {row.cells.map((count, bucketIndex) => {
                      const bucketStart = hourLabels[bucketIndex] ?? "00";
                      const bucketEnd = String(
                        Number(bucketStart) + density.bucket_hours - 1,
                      ).padStart(2, "0");
                      const intensity = density.max_count > 0
                        ? Math.min(4, Math.ceil((count / density.max_count) * 4))
                        : 0;
                      const cellLabel = `${formatDenseNewsTopicLabel(row.label)}（原码 ${row.key}）· ${density.tz} received_at ${bucketStart}:00–${bucketEnd}:59 · ${count} 条`;
                      return (
                        <i
                          aria-label={cellLabel}
                          data-intensity={intensity}
                          key={`${row.key}-${bucketIndex}`}
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
              const eventText = event.summary || event.event_key || "事件摘要待返回";
              return (
                <article key={event.event_key ?? event.received_at}>
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
        className={styles.densityFootnote}
        title={`${sampleRangeLabel}；按 ${density.tz} 接收时间（received_at）每 ${density.bucket_hours} 小时分桶；已排除仅日期记录 ${(news?.granularity.date_only_rows ?? 0).toLocaleString("zh-CN")} 条；颜色仅代表最新样本内相对接收密度，不代表重要性、情绪或影响${excludedFutureRows > 0 ? `；已排除未来记录 ${excludedFutureRows.toLocaleString("zh-CN")} 条` : ""}`}
      >
        {/* 单行最多 1 个 `·`（DESIGN.md §7）：脚注拆两行，received_at 收进 title。 */}
        <span>
          {sampleRangeLabel} · {density.tz} 每 {density.bucket_hours} 小时分桶
          {excludedFutureRows > 0
            ? `（已排除未来记录 ${excludedFutureRows.toLocaleString("zh-CN")} 条）`
            : ""}
        </span>
        <span>
          已排除仅日期记录 {(news?.granularity.date_only_rows ?? 0).toLocaleString("zh-CN")} 条；颜色仅代表样本内相对接收密度
        </span>
      </footer>
    </article>
  );
}

export function MarketOverviewDenseFirstScreen({
  view,
  queries,
  searchValue,
  chartPalette,
  chapterNav,
}: MarketOverviewDenseFirstScreenProps) {
  const [contextDrawer, setContextDrawer] = useState<"macro" | "events" | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<MarketOverviewNews["latest"][number] | null>(null);
  const snapshotEnvelope = queries.marketSnapshot?.data;
  const snapshot = snapshotEnvelope?.result;
  const latest = snapshot?.charts?.choice_latest ?? undefined;
  const rates = snapshot?.charts?.market_rates ?? undefined;
  const gate = snapshot?.gate;
  const dates = snapshot?.dates;
  const tape = snapshot?.tape;
  const pulse = snapshot?.pulse;
  const crisis = snapshot?.crisis;
  const news = snapshot?.news;
  const actions = snapshot?.actions;
  const observationState = snapshotState(queries.marketSnapshot);
  const sections = useMemo(
    () =>
      buildMarketFinancialChartSections({
        latest,
        rates,
        palette: chartPalette,
      }),
    [chartPalette, latest, rates],
  );
  const charts = useMemo(() => selectedDenseCharts(sections), [sections]);
  const macroPulseRows = pulse?.items ?? [];
  const tapeMetrics = tape?.slots ?? [];
  const homeTapeKeys = ["gov_10y", "dr007", "shibor_3m", "usd_cny_mid"];
  const homeTape = homeTapeKeys.flatMap((key) => tapeMetrics.filter((slot) => slot.key === key));
  const allSignalCards = snapshot?.signals?.cards ?? [];
  const opsSignalRow = allSignalCards.find((card) => card.kind === "ops_status");
  const gateIssues = gate?.issues ?? [];
  const actionItems = (actions?.items ?? []).map((item) => {
    const matchingIssue = issueForAction(item.key, gateIssues);
    return {
      key: item.key,
      rank: item.priority,
      title: item.label,
      path: item.route,
      label: "进入核验",
      evidence: matchingIssue
        ? [matchingIssue.reason, matchingIssue.impact]
        : actionEvidenceLabel(item.key, item.evidence),
      tone: item.priority === "P0" ? "error" : item.priority === "P1" ? "watch" : "muted",
    };
  });
  const searchQuery = searchValue.trim().toLowerCase();
  const macroDate = dates?.surfaces.find((surface) => surface.key === "macro_analysis")?.latest;
  const fundingDate = snapshot?.funding_observation?.observation_date ?? EM_DASH;
  const curveDate = snapshot?.rates_observation?.observation_date ?? EM_DASH;
  const evidenceDate = dates?.tape_span.earliest && dates.tape_span.latest
    ? `${dates.tape_span.earliest}–${dates.tape_span.latest}`
    : dates?.tape_span.latest ?? dates?.tape_span.earliest ?? EM_DASH;
  const staleSurfaceLabels: Record<string, string> = {
    rates_formal: "正式利率", choice_latest: "跨资产行情", macro_analysis: "宏观分析",
    news: "新闻事件", strategy: "策略观察",
  };
  const staleSurfaceNotes = (dates?.surfaces ?? [])
    .filter((surface) => surface.age_days != null && surface.age_days >= 5)
    .map((surface) => {
      const surfaceLabel = staleSurfaceLabels[surface.key] ?? "数据来源";
      const dateLabel = surface.latest ? `截至 ${surface.latest}` : "日期未返回";
      return `${surfaceLabel}${dateLabel}（距页面计算日 ${surface.age_days} 天）`;
    });
  const commonObservationReason = !snapshot?.funding_observation?.judgment_allowed
    && !snapshot?.rates_observation?.judgment_allowed
    && snapshot?.funding_observation?.reason === snapshot?.rates_observation?.reason
    ? snapshot?.funding_observation?.reason : null;
  const observationSummary = Array.from(new Set([
    snapshot?.funding_observation?.summary ?? "资金观察尚未返回，暂不形成判断。",
    snapshot?.rates_observation?.summary ?? "国债曲线观察尚未返回，暂不形成判断。",
    commonObservationReason,
  ].filter(Boolean))).join(" ");
  const observationAction = gate?.recovery_action ?? "按各块观察日查看依据。";
  const gateReason = marketBusinessReason(gate?.human_reason,
    gate?.level === "blocked"
      ? "必要数据与刷新结果尚未通过核验，市场判断暂不可用。"
      : gate?.level === "review"
        ? "部分数据使用条件尚需核验，当前结论仅供分析复核。"
        : "各项数据使用边界与核验依据见详情。");
  const receiptEvidence = Array.from(new Set([
    gate?.human_reason,
    snapshot?.funding_observation?.reason,
    snapshot?.rates_observation?.reason,
  ].filter((reason): reason is string => Boolean(reason && hasReceiptPath(reason) && !observationSummary.includes(reason)))));
  const technicalMarketNotes = Array.from(new Set([
    ...tapeMetrics.map((item) => item.reason),
    ...macroPulseRows.map((item) => item.reason),
    news?.reason,
  ].filter((reason): reason is string => Boolean(reason && isMarketTechnicalReason(reason)))));
  const crisisTrend20 = crisisTrendForWindow(crisis, 20);
  const crisisTrend60 = crisisTrendForWindow(crisis, 60);
  const crisisCurrentAvailable = crisis?.score != null && Number.isFinite(crisis.score)
    && crisis.current_available !== false && crisis.status !== "unavailable"
    && crisis.dependency_gate?.status !== "blocked";
  const crisisCurrentLabel = crisisCurrentAvailable
    ? `${crisis.score!.toFixed(2)} · ${crisis.regime ?? "状态待返回"}`
    : "当前不可用";
  const crisisHistoryDate = crisis?.score_trends?.find((trend) => trend.end_date)?.end_date
    ?? crisis?.score_history?.at(-1)?.date;
  const crisisDateLabel = crisisHistoryDate
    ? `${crisisCurrentAvailable ? "趋势截至" : "历史截至"} ${crisisHistoryDate}`
    : "历史日期待返回";
  const crisisPercentileLabel = crisis?.percentile == null ? EM_DASH : `${crisis.percentile.toFixed(1)}%`;
  const crisisRiskGate = crisisRiskGateLabel(crisis?.risk_gate);
  const crisisQuality = crisisQualityEvidence(crisis);
  const crisisEvidence = [
    crisisTrend20,
    crisisTrend60,
    `历史分位 ${crisisPercentileLabel}`,
    crisisRiskGate,
    crisisDateLabel,
    ...crisisQuality,
  ].filter((item): item is string => Boolean(item));
  const crisisEvidenceTitle = [
    ...crisisEvidence,
    crisis?.reason ?? undefined,
    crisis?.rule_version ? `规则 ${crisis.rule_version}` : undefined,
    crisis?.warnings?.length ? `原始告警 ${crisis.warnings.join(" / ")}` : undefined,
  ].filter((item): item is string => Boolean(item)).join("；");
  const macroComponent = snapshot?.components.macro_analysis_core;
  const sourceQuality = macroComponent
    ? `质量 ${macroComponent.quality_flag ?? "未知"} / 供应方 ${macroComponent.vendor_status ?? "未知"}`
    : "未知";
  const newsAvailable = news != null && news.status !== "unavailable";
  const focusItems = [
    {
      title: "宏观工具",
      conclusion: observationSummary,
      evidence: gate?.human_reason ?? "闸门原因待返回",
      tone: gate?.level === "blocked" ? "error" : gate?.level === "review" ? "watch" : "ok",
    },
    {
      title: "Crisis Score",
      conclusion: crisisCurrentLabel,
      evidence: crisisEvidence.join("；"),
      tone:
        crisis?.risk_gate?.triggered || crisis?.risk_gate?.eligible === false
          ? "watch"
          : crisis?.status === "ok"
            ? "ok"
            : "watch",
    },
    {
      title: "新闻复核",
      conclusion: newsAvailable ? `${news.compare.review_needed} 项待复核` : "复核状态不可用",
      evidence: newsAvailable ? `有效分桶 ${news.granularity.datetime_rows} 条` : news?.reason ?? "新闻数据未返回",
      tone: !newsAvailable || news.status !== "ok" || news.compare.review_needed > 0 ? "watch" : "ok",
    },
    {
      title: "数据日期",
      conclusion: evidenceDate,
      evidence: dates?.status === "ok" ? "各面日期已返回" : "部分日期面需复核",
      tone: dates?.status === "ok" ? "ok" : "watch",
    },
  ];

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
        <header className={styles.observationHeading}>
          <h2 id="market-overview-judgment-title" data-testid="module-home-market-dense-observation-title">市场观察</h2>
          <span data-testid="module-home-market-dense-observation-date">资金 {fundingDate}；曲线 {curveDate}</span>
        </header>

        {observationState === "loading" || observationState === "error" || observationState === "empty" ? (
          <StateSurface
            status={observationState}
            message={observationState === "loading" ? "正在读取市场数据" : observationState === "error" ? "市场判断读取失败" : "暂无可用市场判断"}
            reason={observationState === "error" ? "市场数据读取失败，暂不形成判断。" : observationState === "empty" ? "暂无市场分析结果；请刷新数据或进入宏观工具页核验。" : undefined}
            minHeight={120}
            testId="module-home-market-dense-observation-surface"
            actions={observationState === "loading" ? undefined : <Link to="/macro-toolkit">进入宏观工具核验</Link>}
          />
        ) : (
          <div className={styles.marketReading} data-testid="market-home-reading">
            <header><h2>本期市场观察</h2><a href="#market-home-verification" onClick={() => { const detail = document.getElementById("market-home-verification"); if (detail instanceof HTMLDetailsElement) detail.open = true; }}>查看依据</a></header>
            <div className={styles.readingColumns}>
              {([['资金观察', snapshot?.funding_observation], ['国债利率观察', snapshot?.rates_observation]] as const).map(([label, observation]) => <article key={label}>
                <h3>{label}</h3>
                <p data-restricted={!observation?.judgment_allowed}>{observation?.judgment_allowed ? observation.summary : commonObservationReason ? `${label}待核验，暂不形成判断。` : marketBusinessReason(observation?.reason || observation?.summary, '观察尚未返回，暂不形成判断。')}</p>
                <time>观察 {observation?.observation_date ?? EM_DASH}；比较 {observation?.comparison_date ?? EM_DASH}</time>
                {!observation?.judgment_allowed && observation?.verification_route ? <Link to={observation.verification_route}>恢复与核验</Link> : null}
              </article>)}
            </div>
            {commonObservationReason ? <p className={styles.snapshotNotice}>{marketBusinessReason(commonObservationReason, "市场数据尚未通过核验，暂不形成判断。")}</p> : null}
          <details className={styles.observationStatus} data-state={observationState}>
            <summary data-testid="module-home-market-dense-observation-summary">
              <span className={styles.statusLabel}>分析参考 · 非正式</span>
              <span className={styles.statusReason} data-tone={gate?.level === "blocked" || gate?.level === "review" ? "watch" : "muted"} data-testid="module-home-market-dense-observation-gate">{gateReason}</span>
              <span className={styles.statusMore}>使用说明</span>
            </summary>
            <div className={styles.statusBody}>
              <p data-testid="module-home-market-dense-observation-context">{marketBusinessReason(observationSummary, "当前市场判断受限，请按各项数据日期和使用条件复核。")}</p>
              <p data-testid="module-home-market-dense-observation-action">{marketBusinessReason(observationAction, "请更新数据后复核当前市场判断。")}</p>
              {staleSurfaceNotes.length > 0 ? <p data-testid="module-home-market-dense-stale-dates">{staleSurfaceNotes.join("；")}</p> : null}
              {receiptEvidence.length > 0 || hasReceiptPath(observationSummary) || hasReceiptPath(observationAction) ? <details><summary>技术诊断</summary>{hasReceiptPath(observationSummary) ? <p>{observationSummary}</p> : null}{receiptEvidence.map((reason) => <p key={reason} className={styles.receiptEvidence}>{reason}</p>)}{hasReceiptPath(observationAction) ? <p>{observationAction}</p> : null}</details> : null}
            </div>
          </details>
          </div>
        )}
        {queries.marketSnapshot?.isError ? (
          <p className={styles.snapshotNotice} role="status">最新数据读取失败，当前保留上次数据，请刷新后复核。</p>
        ) : observationState === "stale" ? (
          <p className={styles.snapshotNotice} role="status">当前数据已过期，请按各项日期复核。</p>
        ) : staleSurfaceNotes.length > 0 ? (
          <p className={styles.snapshotNotice} role="status">部分来源距页面计算日已达 5 天，请按各项日期复核；详细日期见使用说明。</p>
        ) : null}

        {chapterNav}
        <div className={styles.tapeWithAction}>
        <section className={styles.marketTape} aria-label="市场行情带">
          {homeTape.map((metric) => {
            const { amount, unit } = splitMetricValue(tapeValue(metric));
            const fallbackLabel = metric.fallback_mode === "latest_snapshot"
              ? `回退至 ${metric.fallback_date ?? "日期未披露"}`
              : metric.quality_flag === "stale" ? "数据已过期" : null;
            const formalRestriction = metric.formal_use_allowed === false ? "正式使用受限" : null;
            return (
              <article
                className={styles.tapeCell}
                data-tone={tapeTone(metric)}
                key={metric.key}
                title={`${metric.series_name ?? metric.label}；${metric.reason ? `${marketBusinessReason(metric.reason, "数据使用条件待核验")}；` : ""}${basisLabel(metric.basis)}口径`}
              >
                <span>
                  {metric.label}
                  <small className={styles.basisBadge}>{basisLabel(metric.basis)}</small>
                </span>
                <strong aria-label={tapeValue(metric)}>
                  <span className={styles.tapeAmount}>{amount}</span>
                  {unit ? <small>{unit}</small> : null}
                </strong>
                <em>{tapeDelta(metric)}</em>
                <time>{metric.trade_date ?? EM_DASH}</time>
                {fallbackLabel || formalRestriction ? (
                  <small className={styles.tapeRestriction}>
                    {[fallbackLabel, formalRestriction].filter(Boolean).join(" · ")}
                  </small>
                ) : null}
              </article>
            );
          })}
        </section>
        </div>

        <div className={styles.primaryObservation}>
          <MarketFundingRatesObservations display="rates" funding={snapshot?.funding_observation} rates={snapshot?.rates_observation} />
          <aside className={styles.impactPanel} aria-label="影响核对">
            <h3>影响核对</h3>
            <div className={styles.impactItems}>
              <section><h4>估值影响</h4><p>{snapshot?.rates_observation?.judgment_allowed ? snapshot.rates_observation.interpretation : "利率观察待核验，暂不解释估值影响。"}</p></section>
              <section><h4>融资成本</h4><p>{snapshot?.funding_observation?.judgment_allowed ? snapshot.funding_observation.interpretation : "资金观察待核验，暂不解释融资影响。"}</p></section>
              <section><h4>宏观背景</h4><p>{pulse?.reason || "各指标及事件的观察日期见宏观与组合，影响解释待依据核验。"}</p></section>
            </div>
            <a href="#market-home-scenario">查看组合情景</a>
          </aside>
        </div>
        <div className={styles.supportingObservation}>
          <MarketFundingRatesObservations display="funding" funding={snapshot?.funding_observation} rates={snapshot?.rates_observation} keyRatesContent={charts.filter((item) => item.sectionKey === "rates").map((item) => <DenseChartCard className={styles.embeddedChart} canvasHeight={220} item={item} key={item.chart.key} searchQuery={searchQuery} />)} />
          {charts.filter((item) => item.sectionKey === "cross").map((item) => (
            <DenseChartCard
              canvasHeight={280}
              className={styles.primaryChart}
              item={item}
              key={item.chart.key}
              searchQuery={searchQuery}
            />
          ))}
        </div>


      </section>

      <MarketRiskObservation snapshot={snapshot} chartPalette={chartPalette} />

      <section
        className={styles.chapterSection}
        id="market-overview-evidence"
        aria-labelledby="market-overview-evidence-title"
      >
        <header className={styles.sectionHeader}>
          <h2 id="market-overview-evidence-title">宏观与组合</h2>
        </header>
        <div className={styles.evidenceLayout}>
          <div className={styles.contextSummaries}>
            <article className={styles.contextCard} data-testid="market-home-macro-summary">
              <header><h3>宏观脉冲</h3><button id="market-home-macro-trigger" type="button" onClick={() => setContextDrawer("macro")}>宏观详情</button></header>
              <p className={styles.contextMeta}>各项指标独立观察，不合成为市场方向</p>
              {([['cpi', 'CPI 同比'], ['ppi', 'PPI 同比'], ['pmi', '制造业 PMI'], ['social_financing', '社融存量同比']] as const).map(([key, label]) => {
                const row = macroPulseRows.find((item) => item.key === key);
                return <section className={styles.macroSummaryRow} key={key}>
                  <div><span>{row?.label || label}</span><strong title={row?.unit ?? undefined}>{compactNumber(row?.latest_value)}{row?.latest_value == null || row.unit === 'index' ? '' : unitSuffix(row.unit)}</strong><em>{row?.change != null && row.change > 0 ? '+' : ''}{compactNumber(row?.change)}{row?.change == null ? '' : unitSuffix(row.change_unit)}</em></div>
                  <p>观测日期 {row?.latest_date ?? EM_DASH}</p>
                  {row?.reason ? <p className={styles.snapshotNotice}>{marketBusinessReason(row.reason, "该指标的数据尚未通过核验，请查看宏观详情。")}</p> : null}
                </section>;
              })}
              <p className={styles.contextMeta}>按观测日期展示，指标所属期与发布日期待核实。</p>
            </article>
            <article className={styles.contextCard} data-testid="market-home-events-summary">
              <header><h3>最新事件</h3><button id="market-home-events-trigger" type="button" onClick={() => { setSelectedEvent(null); setContextDrawer("events"); }}>更多事件</button></header>
              <p className={styles.contextMeta}>截至 {news?.sample.latest_received_at?.slice(0, 10) ?? EM_DASH} · 按接收时间查看</p>
              {news?.latest?.length ? news.latest.slice(0, 3).map((event, index) => <section className={styles.eventSummaryRow} key={event.event_key || event.received_at}>
                <span>{formatDenseNewsTopicLabel(event.topic_code || event.group_id || '未分类')}</span>
                <p className={styles.eventSummaryText}>{event.summary || '事件摘要待返回'}</p>
                <div className={styles.eventSummaryFooter}><p>接收 {event.received_at.replace('T', ' ')}</p><button type="button" aria-label={`查看第${index + 1}条事件全文`} onClick={() => { setSelectedEvent(event); setContextDrawer("events"); }}>查看全文</button></div>
              </section>) : <p>{marketBusinessReason(news?.reason, '新闻事件暂未返回')}</p>}
              <p className={styles.contextMeta}>按接收时间展示，事件发生时间与来源待核实；条数不代表影响程度。</p>
            </article>
          </div>
          <div id="market-home-scenario"><MarketPortfolioScenarioPanel curveObservationDate={snapshot?.rates_observation?.observation_date ?? null} /></div>
        <details id="market-home-verification" className={styles.verificationDetails} data-testid="module-home-market-dense-verification">
          <summary>
            核验详情
            <span>
              {gateIssues.length > 0
                ? `${gateIssues.length} 项复核说明、来源与历史风险趋势`
                : "来源、口径与历史风险趋势"}
            </span>
          </summary>
          <div className={styles.verificationBody}>
            {technicalMarketNotes.length > 0 ? <details><summary>技术诊断</summary>{technicalMarketNotes.map((reason) => <p key={reason}>{reason}</p>)}</details> : null}
            <div data-testid="module-home-market-background-details">
              <DenseMacroPulseCard
                asOfDate={macroDate ?? ""}
                rows={macroPulseRows}
                searchQuery={searchQuery}
              />
              <DenseNewsDensityCard
                news={news}
                searchQuery={searchQuery}
              />
            </div>
            <aside className={styles.decisionAside} aria-label="当前风险可用性">
              <span>Crisis Score</span>
              <strong data-testid="module-home-market-dense-crisis-current" data-available={crisisCurrentAvailable}>{crisisCurrentLabel}</strong>
              {crisisCurrentAvailable ? <em>当前截至 {crisis?.report_date ?? EM_DASH}</em> : null}
              <em>{crisisDateLabel}</em>
            </aside>
            <div className={styles.judgmentGrid}>
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
                  <h3>待处理的核验事项</h3>
                </header>
                <div className={styles.queueHead} aria-hidden="true">
                  <span>优先级</span>
                  <span>核验事项 / 证据</span>
                  <span>入口</span>
                </div>
                <div className={styles.queueRows}>
                  {actionItems.map((item, index) => (
                    <Link
                      className={styles.queueRow}
                      data-tone={item.tone}
                      key={`${item.key}-${index}`}
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

            <p>{gate?.recovery_action ?? "恢复动作待返回"}</p>
            {gateIssues.length > 0 ? (
              <div className={styles.gateIssueList} aria-label="受限结论与复核入口">
                {gateIssues.map((issue, index) => (
                  <article
                    className={styles.gateIssue}
                    data-testid={`module-home-market-dense-gate-issue-${issue.key}`}
                    key={`${issue.key}-${index}`}
                  >
                    <div>
                      <span>{issue.label}</span>
                      <strong>{issue.reason}</strong>
                      <em>影响：{issue.impact}</em>
                    </div>
                    <Link to={issue.route}>进入核验</Link>
                  </article>
                ))}
              </div>
            ) : null}
            <div className={styles.decisionFacts}>
              <div>
                <span>状态</span>
                <strong>{view.stateLabel}</strong>
              </div>
              <div className={styles.crisisFact}>
                <span>{crisisCurrentAvailable ? "Crisis 趋势" : "Crisis 历史趋势（当前不可用）"}</span>
                <em
                  className={styles.crisisTrendMeta}
                  data-testid="module-home-market-dense-crisis-trend"
                  title={crisisEvidenceTitle || undefined}
                >
                  {crisis
                    ? crisisEvidence.join("；")
                    : "趋势待返回"}
                </em>
              </div>
              {opsSignalRow ? (
                <div
                  data-testid="module-home-market-dense-ops-signal"
                  title={opsSignalRow.evidence?.join("；")}
                >
                  <span>{opsSignalRow.title ?? "工具产物"}</span>
                  <strong>{opsSignalRow.stance ?? EM_DASH}</strong>
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
                  {snapshotEnvelope ? `${basisLabel(snapshotEnvelope.result_meta.basis)}口径` : "未返回"}
                </strong>
              </article>
              <article className={styles.observationFact}>
                <span>允许正式使用</span>
                <strong data-testid="module-home-market-dense-observation-formal">
                  {snapshotEnvelope ? (snapshotEnvelope.result_meta.formal_use_allowed ? "是" : "否") : "未返回"}
                </strong>
              </article>
              <article className={styles.observationFact}>
                <span>来源质量</span>
                <strong
                  data-testid="module-home-market-dense-observation-quality"
                  title={sourceQuality}
                >
                  {sourceQuality}
                </strong>
              </article>
            </div>
          </div>
        </details>
        </div>

      </section>
      <Drawer open={contextDrawer != null} onClose={() => setContextDrawer(null)} title={contextDrawer === 'macro' ? '宏观指标依据' : selectedEvent ? '事件全文' : '事件范围依据'} width="min(640px, 100vw)" rootClassName={`theme-dh-api ${styles.contextDrawer}`} data-moss-theme-scope="market-overview">
        {contextDrawer === 'macro' ? <><p>来源行情日期 {evidenceDate}；分析快照 {macroDate ?? EM_DASH}</p><DenseMacroPulseCard rows={macroPulseRows} searchQuery={searchQuery} asOfDate={macroDate ?? ''} /><Link to={buildMarketSourceLink('/macro-observation', 'macro', { market_observation_date: snapshot?.rates_observation?.observation_date ?? undefined })}>进入宏观观察</Link></> : contextDrawer === 'events' ? <><p>来源范围按接收时间，事件发生时间未独立返回。</p>{selectedEvent ? <section className={styles.eventDetail}><button type="button" onClick={() => setSelectedEvent(null)}>返回事件概览</button><p className={styles.contextMeta}>{formatDenseNewsTopicLabel(selectedEvent.topic_code || selectedEvent.group_id || '未分类')}；接收 {selectedEvent.received_at.replace('T', ' ')}</p><p className={styles.eventFullText}>{selectedEvent.summary || '事件摘要待返回'}</p></section> : <DenseNewsDensityCard news={news} searchQuery={searchQuery} />}<Link to={buildMarketSourceLink('/news-events', 'events', {})}>进入新闻事件</Link></> : null}
      </Drawer>
    </section>
  );
}
