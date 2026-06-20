import { lazy, Suspense, useEffect, useRef, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";

import {
  mossChartAxisLabel,
  mossChartAxisLine,
  mossChartCategoricalPalette,
  mossChartSplitLine,
} from "../../../components/charts/chartTheme";
import { LightIcon } from "../../../components/LightIcon";
import { ibTokens } from "../../../theme/designSystem";
import type {
  DashboardHomeBodyView,
  HomeDataStateKind,
  HomeDistributionSlice,
  HomeResearchReportRow,
  HomeTerminalListState,
} from "./dashboardHomeBodyView";
import { resolveDeltaClass } from "./dashboardHomeBodyView";
import styles from "./dashboardHome.module.css";

type TerminalHomeWorkGridProps = {
  view: DashboardHomeBodyView;
};

type EChartsOption = import("../../../lib/echarts").EChartsOption;

const CHART_COLORS = mossChartCategoricalPalette;
const INCOME_TREND_COLORS = [
  mossChartCategoricalPalette[0],
  mossChartCategoricalPalette[3],
  mossChartCategoricalPalette[5],
] as const;
const ReactECharts = lazy(() => import("../../../lib/echarts"));
const CHART_REVEAL_KEYS = new Set(["ArrowDown", "PageDown", "End", " ", "Space"]);

function ChartFallback() {
  return <div aria-hidden="true" className={styles.dhTerminalChartPlaceholder} />;
}

function useDeferredChartMount() {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [isVisible, setIsVisible] = useState(
    () => typeof window === "undefined" || typeof window.IntersectionObserver === "undefined",
  );
  const [hasUserReachedCharts, setHasUserReachedCharts] = useState(
    () =>
      typeof window === "undefined" ||
      typeof window.IntersectionObserver === "undefined" ||
      window.scrollY > 0,
  );

  useEffect(() => {
    if (isVisible) return;

    if (typeof window === "undefined" || typeof window.IntersectionObserver === "undefined") {
      setIsVisible(true);
      return;
    }

    const chartNode = chartRef.current;
    if (!chartNode) return;

    const observer = new window.IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting || entry.intersectionRatio > 0)) {
        setIsVisible(true);
        observer.disconnect();
      }
    });

    observer.observe(chartNode);
    return () => observer.disconnect();
  }, [isVisible]);

  useEffect(() => {
    if (hasUserReachedCharts) return;

    if (typeof window === "undefined") {
      setHasUserReachedCharts(true);
      return;
    }

    if (window.scrollY > 0) {
      setHasUserReachedCharts(true);
      return;
    }

    function removeUserReachListeners() {
      window.removeEventListener("scroll", markUserReachedCharts);
      window.removeEventListener("wheel", markUserReachedCharts);
      window.removeEventListener("touchmove", markUserReachedCharts);
      window.removeEventListener("keydown", handleKeyDown);
    }

    function markUserReachedCharts() {
      setHasUserReachedCharts(true);
      removeUserReachListeners();
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (CHART_REVEAL_KEYS.has(event.key)) {
        markUserReachedCharts();
      }
    }

    window.addEventListener("scroll", markUserReachedCharts);
    window.addEventListener("wheel", markUserReachedCharts);
    window.addEventListener("touchmove", markUserReachedCharts);
    window.addEventListener("keydown", handleKeyDown);
    return removeUserReachListeners;
  }, [hasUserReachedCharts]);

  return { chartRef, shouldMount: isVisible && hasUserReachedCharts };
}

function LazyEChart({
  option,
}: {
  option: EChartsOption;
}) {
  const { chartRef, shouldMount } = useDeferredChartMount();

  return (
    <div ref={chartRef} className={styles.dhTerminalChartMount}>
      {shouldMount ? (
        <Suspense fallback={<ChartFallback />}>
          <ReactECharts
            option={option}
            opts={{ renderer: "canvas" }}
            notMerge
            lazyUpdate
            style={{ height: "100%", width: "100%" }}
          />
        </Suspense>
      ) : (
        <ChartFallback />
      )}
    </div>
  );
}

function buildReportDatePath(path: string, reportDate: string): string {
  const trimmed = reportDate.trim();
  return trimmed && trimmed !== "—" ? `${path}?report_date=${encodeURIComponent(trimmed)}` : path;
}

const STATE_COPY: Record<HomeDataStateKind, string> = {
  ready: "已接入",
  partial: "部分接入",
  empty: "暂无数据",
  loading: "加载中",
  error: "加载失败",
  stale: "数据过期",
  "backend-gap": "后端待接入",
};

const STATE_HINT: Record<HomeDataStateKind, string> = {
  ready: "接口已返回受管数据",
  partial: "缺少部分受管字段",
  empty: "当前口径没有可展示记录",
  loading: "等待后端接口返回",
  error: "保留空态，不使用前端补数",
  stale: "数据日期与报告日不一致",
  "backend-gap": "已列为后端工单",
};

function stateClass(kind: HomeDataStateKind): string {
  if (kind === "ready") return styles.dhTerminalStateReady ?? "";
  if (kind === "partial") return styles.dhTerminalStateWarn ?? "";
  if (kind === "error" || kind === "backend-gap") return styles.dhTerminalStateWarn ?? "";
  if (kind === "stale") return styles.dhTerminalStateStale ?? "";
  return styles.dhTerminalStateMuted ?? "";
}

function DataStateBadge({ kind, label }: { kind: HomeDataStateKind; label?: string }) {
  return (
    <span className={`${styles.dhTerminalState} ${stateClass(kind)}`}>
      {STATE_COPY[kind]}
      {label && kind !== "ready" ? ` · ${label}` : ""}
    </span>
  );
}

function StateIcon({ kind }: { kind: HomeDataStateKind }) {
  if (kind === "loading") return <LightIcon name="loading" />;
  if (kind === "error" || kind === "backend-gap") return <LightIcon name="warning" />;
  if (kind === "stale" || kind === "partial") return <LightIcon name="alert" />;
  return <LightIcon name="info-circle" />;
}

function StateSurface({
  state,
  compact = false,
  testId,
}: {
  state: HomeTerminalListState;
  compact?: boolean;
  testId?: string;
}) {
  return (
    <div
      data-testid={testId}
      data-state={state.kind}
      className={`${styles.dhTerminalStateSurface} ${compact ? styles.dhTerminalStateSurfaceCompact : ""}`}
    >
      <span className={styles.dhTerminalStateIcon}>
        <StateIcon kind={state.kind} />
      </span>
      <b>{state.label}</b>
      <small>{STATE_HINT[state.kind]}</small>
    </div>
  );
}

function buildPieOption(slices: readonly HomeDistributionSlice[]): EChartsOption {
  return {
    color: CHART_COLORS,
    tooltip: { trigger: "item" },
    series: [
      {
        type: "pie",
        radius: ["58%", "82%"],
        center: ["50%", "50%"],
        minAngle: 4,
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: {
          borderColor: ibTokens.color.surface,
          borderWidth: 2,
        },
        emphasis: {
          scaleSize: 4,
        },
        data: slices.map((slice) => ({
          name: slice.label,
          value: Math.max(slice.pctRaw, 0),
        })),
      },
    ],
  };
}

function buildBarOption(slices: readonly HomeDistributionSlice[]): EChartsOption {
  return {
    color: CHART_COLORS,
    grid: { top: 8, right: 10, bottom: 8, left: 28 },
    xAxis: {
      type: "category",
      data: slices.map((slice) => slice.label),
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: mossChartAxisLine,
    },
    yAxis: {
      type: "value",
      axisLabel: {
        fontSize: 10,
        formatter: (value: number) => `${Number(value).toFixed(0)}%`,
      },
      splitLine: mossChartSplitLine,
    },
    tooltip: { trigger: "axis" },
    series: [
      {
        type: "bar",
        data: slices.map((slice) => Number(slice.pctRaw.toFixed(2))),
        barWidth: 14,
        barMaxWidth: 16,
        itemStyle: { borderRadius: [2, 2, 0, 0] },
      },
    ],
  };
}

function buildIncomeTrendOption(points: DashboardHomeBodyView["incomeTrend"]): EChartsOption {
  return {
    color: INCOME_TREND_COLORS,
    legend: {
      top: 0,
      right: 0,
      itemWidth: 10,
      itemHeight: 6,
      textStyle: { ...mossChartAxisLabel, fontSize: 10 },
      data: ["组合", "CDB基准", "超额"],
    },
    grid: { top: 24, right: 8, bottom: 20, left: 34 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: points.map((point) => point.date.slice(5)),
      boundaryGap: false,
      axisTick: { show: false },
      axisLine: mossChartAxisLine,
      axisLabel: { ...mossChartAxisLabel, fontSize: 10 },
    },
    yAxis: {
      type: "value",
      axisLabel: {
        fontSize: 10,
        color: mossChartAxisLabel.color,
        formatter: (value: number) => `${(Number(value) / 100_000_000).toFixed(1)}亿`,
      },
      splitLine: mossChartSplitLine,
    },
    series: [
      {
        name: "组合",
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 4,
        showSymbol: true,
        data: points.map((point) => point.portfolioRaw ?? 0),
        lineStyle: { width: 2.2 },
        areaStyle: { opacity: 0.1 },
      },
      {
        name: "CDB基准",
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 3,
        showSymbol: true,
        data: points.map((point) => point.benchmarkRaw),
        lineStyle: { width: 1.8, type: "dashed" },
        connectNulls: false,
      },
      {
        name: "超额",
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 3,
        showSymbol: true,
        data: points.map((point) => point.excessRaw),
        lineStyle: { width: 1.8 },
        connectNulls: false,
      },
    ],
  };
}

function DistributionList({ slices }: { slices: readonly HomeDistributionSlice[] }) {
  return (
    <div className={styles.dhTerminalDistributionList}>
      {slices.slice(0, 5).map((slice, index) => {
        const width = `${Math.max(2, Math.min(slice.pctRaw, 100))}%`;
        return (
          <div key={slice.id} className={styles.dhTerminalDistributionRow}>
            <span className={styles.dhTerminalLegendDot} data-color-index={index % CHART_COLORS.length} />
            <span className={styles.dhTerminalDistributionName}>{slice.label}</span>
            <span className={`${styles.dhTerminalDistributionValue} ${styles.dhNum}`}>{slice.value}</span>
            <span className={`${styles.dhTerminalDistributionPct} ${styles.dhNum}`}>{slice.pct}</span>
            <span className={styles.dhTerminalDistributionTrack}>
              <span
                className={styles.dhTerminalDistributionFill}
                style={{ "--dh-terminal-bar-width": width } as CSSProperties}
              />
            </span>
          </div>
        );
      })}
    </div>
  );
}

function DistributionPanel({
  title,
  state,
  slices,
  chart,
}: {
  title: string;
  state: DashboardHomeBodyView["ratingDistributionState"];
  slices: readonly HomeDistributionSlice[];
  chart: "pie" | "bar";
}) {
  const hasData = state.kind === "ready" && slices.length > 0;
  return (
    <article className={`${styles.dhCard} ${styles.dhTerminalPanel}`}>
      <div className={styles.dhTerminalPanelHead}>
        <h3>{title}</h3>
        <DataStateBadge kind={state.kind} label={state.label} />
      </div>
      {hasData ? (
        <div className={styles.dhTerminalDistribution}>
          <div className={styles.dhTerminalChart}>
            <LazyEChart
              option={chart === "pie" ? buildPieOption(slices) : buildBarOption(slices)}
            />
          </div>
          <DistributionList slices={slices} />
        </div>
      ) : (
        <StateSurface state={state} />
      )}
    </article>
  );
}

function HoldingsPanel({ view }: { view: DashboardHomeBodyView }) {
  const hasRows = view.holdingsState.kind === "ready" && view.holdingRows.length > 0;
  return (
    <article
      className={`${styles.dhCard} ${styles.dhTerminalPanel} ${styles.dhTerminalPanelWide}${hasRows ? ` ${styles.dhTerminalHoldings}` : ""}`}
    >
      <div className={styles.dhTerminalPanelHead}>
        <h3>持仓券种分布</h3>
        <DataStateBadge kind={view.holdingsState.kind} label={view.holdingsState.label} />
      </div>
      {hasRows ? (
        <table data-testid="dashboard-home-holdings-table" className={styles.dhTerminalTable}>
          <colgroup>
            <col className={styles.dhTerminalHoldColBond} />
            <col className={styles.dhTerminalHoldColType} />
            <col className={styles.dhTerminalHoldColMetric} />
            <col className={styles.dhTerminalHoldColMetric} />
            <col className={styles.dhTerminalHoldColMetric} />
            <col className={styles.dhTerminalHoldColMetric} />
            <col className={styles.dhTerminalHoldColRating} />
          </colgroup>
          <thead>
            <tr>
              <th>券种</th>
              <th>分类</th>
              <th>市值</th>
              <th>占比</th>
              <th>YTM</th>
              <th>久期</th>
              <th>评级</th>
            </tr>
          </thead>
          <tbody>
            {view.holdingRows.map((row) => (
              <tr key={row.id} data-testid="dashboard-home-holding-row">
                <td>
                  <b>{row.code}</b>
                  <span>{row.name}</span>
                </td>
                <td>{row.assetClass}</td>
                <td className={styles.dhNum}>{row.marketValue}</td>
                <td className={styles.dhNum}>{row.weight}</td>
                <td className={styles.dhNum}>{row.ytm}</td>
                <td className={styles.dhNum}>{row.duration}</td>
                <td>{row.rating}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <StateSurface state={view.holdingsState} testId="dashboard-home-holdings-table" />
      )}
    </article>
  );
}

function RiskExposurePanel({ view }: { view: DashboardHomeBodyView }) {
  return (
    <article className={`${styles.dhCard} ${styles.dhTerminalPanel}`}>
      <div className={styles.dhTerminalPanelHead}>
        <h3>风险敞口</h3>
        <DataStateBadge kind={view.riskExposureState.kind} label={view.riskExposureState.label} />
      </div>
      {view.riskExposureMetrics.length > 0 ? (
        <div className={styles.dhTerminalExposureGrid}>
          {view.riskExposureMetrics.map((metric) => (
            <div key={metric.id} className={styles.dhTerminalExposureItem}>
              <span>{metric.label}</span>
              <b className={styles.dhNum}>{metric.value}</b>
            </div>
          ))}
        </div>
      ) : (
        <StateSurface state={view.riskExposureState} />
      )}
    </article>
  );
}

function PositionChangesPanel({ view }: { view: DashboardHomeBodyView }) {
  const hasRows = view.positionChangesState.kind === "ready" && view.positionChanges.length > 0;
  return (
    <article data-testid="dashboard-home-position-changes" className={`${styles.dhCard} ${styles.dhTerminalPanel}`}>
      <div className={styles.dhTerminalPanelHead}>
        <h3>增减仓 TOP5</h3>
        <DataStateBadge kind={view.positionChangesState.kind} label={view.positionChangesState.label} />
      </div>
      {hasRows ? (
        <div className={styles.dhTerminalChangeList}>
          {view.positionChanges.map((row) => (
            <div key={row.id} className={styles.dhTerminalChangeRow}>
              <span className={styles.dhTerminalChangeBond}>
                <b>{row.code}</b>
                <small>{row.name}</small>
              </span>
              <span className={styles.dhTerminalChangeReason} data-direction={row.direction}>
                {row.reason}
              </span>
              <span className={styles.dhTerminalChangeBar}>
                <span
                  className={styles.dhTerminalChangeFill}
                  data-direction={row.direction}
                  style={{ "--dh-terminal-bar-width": `${row.barPct}%` } as CSSProperties}
                />
              </span>
              <span className={`${styles.dhTerminalChangeValue} ${styles.dhNum} ${resolveDeltaClass(row.tone, styles)}`}>
                {row.changeValue}
                <small>{row.weightDelta}</small>
              </span>
              <span className={`${styles.dhTerminalChangeCurrent} ${styles.dhNum}`}>
                <small>现值</small>
                {row.currentValue}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <StateSurface state={view.positionChangesState} />
      )}
    </article>
  );
}

function formatResearchMonthDay(publishedAt: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(publishedAt.trim());
  if (match) {
    return `${match[2]}-${match[3]}`;
  }
  return publishedAt.trim() || "—";
}

function formatResearchCategoryLabel(category: string): string {
  const trimmed = category.trim();
  if (!trimmed || trimmed === "research") {
    return "研报";
  }
  if (trimmed === "fixed_income") {
    return "固收";
  }
  return trimmed;
}

function isResearchSummaryVisible(summary: string): boolean {
  const text = summary.trim();
  return text.length > 0 && text !== "—";
}

function formatResearchInstitution(row: HomeResearchReportRow): string | null {
  const institution = row.institution.trim();
  if (institution && institution !== "—") {
    return institution;
  }
  const source = row.source.trim();
  if (source && source !== "—" && source !== "tushare_research") {
    return source;
  }
  return null;
}

function buildResearchMetaLine(row: HomeResearchReportRow): string {
  return [formatResearchInstitution(row), formatResearchCategoryLabel(row.category)].filter(Boolean).join(" · ");
}

function ResearchReportFeatured({ row }: { row: HomeResearchReportRow }) {
  const className = `${styles.dhTerminalReportFeatured}${row.isNewsFallback ? ` ${styles.dhTerminalReportFallback}` : ""}`;
  const content = (
    <>
      <span className={styles.dhTerminalReportFeaturedDate}>
        <b>{formatResearchMonthDay(row.publishedAt)}</b>
        <small>{row.isNewsFallback ? "补位" : "最新"}</small>
      </span>
      <span className={styles.dhTerminalReportFeaturedBody}>
        <span className={styles.dhTerminalReportFeaturedTitle}>{row.title}</span>
        {isResearchSummaryVisible(row.summary) ? (
          <span className={styles.dhTerminalReportFeaturedSummary}>{row.summary}</span>
        ) : null}
        <span className={styles.dhTerminalReportMetaRow}>
          <span className={styles.dhTerminalReportMetaText}>{buildResearchMetaLine(row)}</span>
          {row.link ? <span className={styles.dhTerminalReportPdfTag}>PDF</span> : null}
        </span>
      </span>
    </>
  );
  return row.link ? (
    <a className={className} href={row.link} target="_blank" rel="noreferrer" data-testid="dashboard-home-research-featured">
      {content}
    </a>
  ) : (
    <div className={className} data-testid="dashboard-home-research-featured">
      {content}
    </div>
  );
}

function ResearchReportCompactRow({ row }: { row: HomeResearchReportRow }) {
  const className = `${styles.dhTerminalReportCompactRow}${row.isNewsFallback ? ` ${styles.dhTerminalReportFallback}` : ""}`;
  const content = (
    <>
      <span className={styles.dhTerminalReportCompactDate}>{formatResearchMonthDay(row.publishedAt)}</span>
      <span className={styles.dhTerminalReportCompactTitle}>{row.title}</span>
      <span className={styles.dhTerminalReportCompactInstitution}>
        {formatResearchInstitution(row) ?? "—"}
      </span>
      <span className={styles.dhTerminalReportTypeTag}>{formatResearchCategoryLabel(row.category)}</span>
      {row.link ? <span className={styles.dhTerminalReportPdfTag}>PDF</span> : <span className={styles.dhTerminalReportPdfSpacer} />}
    </>
  );
  return row.link ? (
    <a className={className} href={row.link} target="_blank" rel="noreferrer" data-testid="dashboard-home-research-row">
      {content}
    </a>
  ) : (
    <div className={className} data-testid="dashboard-home-research-row">
      {content}
    </div>
  );
}

function ResearchReportsPanel({ view }: { view: DashboardHomeBodyView }) {
  const hasRows =
    (view.researchReportsState.kind === "ready" || view.researchReportsState.kind === "partial") &&
    view.researchReports.length > 0;
  const panelTitle = view.researchReportsState.label.includes("新闻补位") ? "研究资讯" : "券商研报";
  const [featured, ...compactRows] = view.researchReports;
  return (
    <article
      data-testid="dashboard-home-research-reports"
      className={`${styles.dhCard} ${styles.dhTerminalPanel} ${styles.dhTerminalReportsPanel}`}
    >
      <div className={styles.dhTerminalPanelHead}>
        <h3>{panelTitle}</h3>
        <DataStateBadge kind={view.researchReportsState.kind} label={view.researchReportsState.label} />
      </div>
      {hasRows && featured ? (
        <div className={styles.dhTerminalReportStack}>
          <ResearchReportFeatured row={featured} />
          {compactRows.length > 0 ? (
            <div className={styles.dhTerminalReportCompactList}>
              {compactRows.map((row) => (
                <ResearchReportCompactRow key={row.id} row={row} />
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <StateSurface state={view.researchReportsState} />
      )}
    </article>
  );
}

function IncomeTrendPanel({ view }: { view: DashboardHomeBodyView }) {
  const hasRows =
    (view.incomeTrendState.kind === "ready" || view.incomeTrendState.kind === "partial") &&
    view.incomeTrend.length > 0;
  const latestPoint = view.incomeTrend.at(-1);
  return (
    <article data-testid="dashboard-home-income-trend" className={`${styles.dhCard} ${styles.dhTerminalPanel}`}>
      <div className={styles.dhTerminalPanelHead}>
        <h3>收益趋势</h3>
        <div className={styles.dhPanelHeaderActions}>
          <DataStateBadge kind={view.incomeTrendState.kind} label={view.incomeTrendState.label} />
          <Link
            to={buildReportDatePath("/pnl-attribution", view.reportDate)}
            className={styles.dhPanelDrillLink}
          >
            归因明细 →
          </Link>
        </div>
      </div>
      {hasRows ? (
        <div className={styles.dhTerminalIncomeStack}>
          {latestPoint ? (
            <div className={styles.dhTerminalIncomeSummary}>
              <span>
                <small>组合</small>
                <b className={styles.dhNum}>{latestPoint.portfolioPnl}</b>
              </span>
              <span>
                <small>基准</small>
                <b className={styles.dhNum}>{latestPoint.benchmarkPnl}</b>
              </span>
              <span>
                <small>超额</small>
                <b className={styles.dhNum}>{latestPoint.excessPnl}</b>
              </span>
            </div>
          ) : null}
          {latestPoint ? (
            <div className={styles.dhTerminalIncomeMeta}>
              <span>{`数据截至 ${latestPoint.date}`}</span>
              <span>{`CDB_INDEX / MoM${view.incomeTrendState.kind === "partial" ? ` · ${view.incomeTrendState.label}` : ""}`}</span>
            </div>
          ) : null}
          <div className={styles.dhTerminalIncomeLegend} aria-label="收益趋势图例">
            <span data-series="portfolio">组合</span>
            <span data-series="benchmark">CDB基准</span>
            <span data-series="excess">超额</span>
          </div>
          <div className={styles.dhTerminalIncomeTrend}>
            <div className={styles.dhTerminalIncomeChart}>
              <LazyEChart
                option={buildIncomeTrendOption(view.incomeTrend)}
              />
            </div>
            <div className={styles.dhTerminalIncomeList}>
              {view.incomeTrend.slice(-4).map((point) => (
                <div key={point.id} className={styles.dhTerminalIncomeRow}>
                  <span>{point.date.slice(5)}</span>
                  <b className={styles.dhNum}>{point.portfolioPnl}</b>
                  <small>{`基准 ${point.benchmarkPnl} · 超额 ${point.excessPnl}`}</small>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <StateSurface state={view.incomeTrendState} />
      )}
    </article>
  );
}

export function TerminalHomeWorkGrid({ view }: TerminalHomeWorkGridProps) {
  return (
    <section data-testid="dashboard-home-work-grid" className={styles.dhTerminalGrid}>
      <HoldingsPanel view={view} />
      <DistributionPanel
        title="资产分布"
        state={view.assetDistributionState}
        slices={view.assetDistribution}
        chart="pie"
      />
      <DistributionPanel
        title="评级分布"
        state={view.ratingDistributionState}
        slices={view.ratingDistribution}
        chart="pie"
      />
      <DistributionPanel
        title="行业分布"
        state={view.industryDistributionState}
        slices={view.industryDistribution}
        chart="pie"
      />
      <DistributionPanel
        title="久期分布"
        state={view.maturityDistributionState}
        slices={view.maturityDistribution}
        chart="bar"
      />
      <RiskExposurePanel view={view} />
      <PositionChangesPanel view={view} />
      <IncomeTrendPanel view={view} />
      <ResearchReportsPanel view={view} />
    </section>
  );
}
