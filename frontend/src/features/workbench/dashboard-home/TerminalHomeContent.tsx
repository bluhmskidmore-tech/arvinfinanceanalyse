import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRightOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  ExclamationCircleOutlined,
  FundProjectionScreenOutlined,
  InfoCircleOutlined,
  LineChartOutlined,
  LoadingOutlined,
  SafetyCertificateOutlined,
  StarFilled,
  WarningOutlined,
} from "@ant-design/icons";

import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import type {
  DashboardHomeView,
  HomeDataStateKind,
  HomeDistributionSlice,
  HomeTerminalListState,
} from "./dashboardHomeView";
import { resolveDeltaClass } from "./dashboardHomeView";
import { HomeSparkline } from "./HomeSparkline";
import { ResearchCalendarSection } from "./sections/ResearchCalendarSection";
import styles from "./dashboardHome.module.css";

type TerminalHomeContentProps = {
  view: DashboardHomeView;
};

const CHART_COLORS = ["#1850a1", "#2f68b8", "#86acdb", "#1f7a55", "#b94743", "#9aa7b8"];

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
  if (kind === "loading") return <LoadingOutlined />;
  if (kind === "error" || kind === "backend-gap") return <ExclamationCircleOutlined />;
  if (kind === "stale" || kind === "partial") return <WarningOutlined />;
  return <InfoCircleOutlined />;
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

function sparkStroke(tone: DashboardHomeView["terminalKpis"][number]["deltaTone"]): string {
  if (tone === "up" || tone === "warn") return "#b94743";
  if (tone === "down") return "#1f7a55";
  return "#1850a1";
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
          borderColor: "#fff",
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
    color: ["#1850a1"],
    grid: { top: 8, right: 10, bottom: 8, left: 28 },
    xAxis: {
      type: "category",
      data: slices.map((slice) => slice.label),
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#cdd5e1" } },
    },
    yAxis: {
      type: "value",
      axisLabel: {
        fontSize: 10,
        formatter: (value: number) => `${Number(value).toFixed(0)}%`,
      },
      splitLine: { lineStyle: { color: "#eef2f7" } },
    },
    tooltip: { trigger: "axis" },
    series: [
      {
        type: "bar",
        data: slices.map((slice) => Number(slice.pctRaw.toFixed(2))),
        barWidth: 14,
        barMaxWidth: 16,
        itemStyle: { borderRadius: [3, 3, 0, 0] },
      },
    ],
  };
}

function buildIncomeTrendOption(points: DashboardHomeView["incomeTrend"]): EChartsOption {
  return {
    color: ["#1850a1"],
    grid: { top: 12, right: 10, bottom: 22, left: 36 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: points.map((point) => point.date.slice(5)),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#cdd5e1" } },
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: "value",
      axisLabel: {
        fontSize: 10,
        formatter: (value: number) => `${(Number(value) / 100_000_000).toFixed(1)}亿`,
      },
      splitLine: { lineStyle: { color: "#eef2f7" } },
    },
    series: [
      {
        type: "line",
        smooth: true,
        showSymbol: false,
        data: points.map((point) => point.portfolioRaw ?? 0),
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.12 },
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
  state: DashboardHomeView["ratingDistributionState"];
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
            <ReactECharts
              option={chart === "pie" ? buildPieOption(slices) : buildBarOption(slices)}
              opts={{ renderer: "canvas" }}
              notMerge
              lazyUpdate
              style={{ height: "100%", width: "100%" }}
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

function TerminalKpiStrip({ view }: { view: DashboardHomeView }) {
  return (
    <section data-testid="dashboard-home-hero" className={styles.dhTerminalHero}>
      {view.terminalKpis.map((kpi) => (
        <article
          key={kpi.id}
          data-testid={`dashboard-home-kpi-${kpi.id}`}
          className={`${styles.dhCard} ${styles.dhTerminalKpi}`}
        >
          <div className={styles.dhTerminalKpiTop}>
            <span>{kpi.label}</span>
            {kpi.state === "ready" ? null : <DataStateBadge kind={kpi.state} />}
          </div>
          <div className={`${styles.dhTerminalKpiValue} ${styles.dhNum}`}>
            {kpi.value}
            {kpi.unit ? <small>{kpi.unit}</small> : null}
          </div>
          <div className={`${styles.dhTerminalKpiDelta} ${resolveDeltaClass(kpi.deltaTone, styles)}`}>
            {kpi.delta}
          </div>
          <HomeSparkline
            values={kpi.sparkline}
            stroke={sparkStroke(kpi.deltaTone)}
            className={styles.dhTerminalKpiSpark}
            area
          />
        </article>
      ))}
    </section>
  );
}

function RiskStrip({ items }: { items: DashboardHomeView["keyRiskStrip"] }) {
  const hasItems = items.length > 0;
  return (
    <section data-testid="dashboard-home-market" className={`${styles.dhCard} ${styles.dhTerminalRiskStrip}`}>
      <div className={styles.dhTerminalPanelHead}>
        <h3>关键风险</h3>
        <Link to="/risk" className={styles.dhLink}>
          更多市场数据 →
        </Link>
      </div>
      {hasItems ? (
        <div className={styles.dhTerminalRiskGrid}>
          {items.map((item) => (
            <div key={item.id} className={styles.dhTerminalRiskCell}>
              <span>{item.label}</span>
              <b className={styles.dhNum}>{item.value}</b>
              <em className={resolveDeltaClass(item.deltaTone, styles)}>{item.delta}</em>
            </div>
          ))}
        </div>
      ) : (
        <StateSurface state={{ kind: "empty", label: "关键风险暂无数据" }} compact />
      )}
    </section>
  );
}

function HoldingsPanel({ view }: { view: DashboardHomeView }) {
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

function RiskExposurePanel({ view }: { view: DashboardHomeView }) {
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

function PositionChangesPanel({ view }: { view: DashboardHomeView }) {
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
              <span className={styles.dhTerminalChangeReason}>{row.reason}</span>
              <span className={styles.dhTerminalChangeBar}>
                <span
                  className={styles.dhTerminalChangeFill}
                  data-direction={row.direction}
                  style={{ "--dh-terminal-bar-width": `${row.barPct}%` } as CSSProperties}
                />
              </span>
              <span className={`${styles.dhTerminalChangeValue} ${styles.dhNum} ${resolveDeltaClass(row.tone, styles)}`}>
                {row.changeValue}
              </span>
              <span className={`${styles.dhTerminalChangeCurrent} ${styles.dhNum}`}>{row.currentValue}</span>
            </div>
          ))}
        </div>
      ) : (
        <StateSurface state={view.positionChangesState} />
      )}
    </article>
  );
}

function ResearchReportsPanel({ view }: { view: DashboardHomeView }) {
  const hasRows = view.researchReportsState.kind === "ready" && view.researchReports.length > 0;
  return (
    <article
      data-testid="dashboard-home-research-reports"
      className={`${styles.dhCard} ${styles.dhTerminalPanel} ${styles.dhTerminalReportsPanel}`}
    >
      <div className={styles.dhTerminalPanelHead}>
        <h3>研究报告</h3>
        <DataStateBadge kind={view.researchReportsState.kind} label={view.researchReportsState.label} />
      </div>
      {hasRows ? (
        <div className={styles.dhTerminalReportList}>
          {view.researchReports.map((row) => {
            const content = (
              <>
                <span className={styles.dhTerminalReportMeta}>
                  {row.category}
                  <em>{row.publishedAt}</em>
                </span>
                <b>{row.title}</b>
                <small>{row.summary}</small>
              </>
            );
            return row.link ? (
              <a key={row.id} className={styles.dhTerminalReportItem} href={row.link} target="_blank" rel="noreferrer">
                {content}
              </a>
            ) : (
              <div key={row.id} className={styles.dhTerminalReportItem}>
                {content}
              </div>
            );
          })}
        </div>
      ) : (
        <StateSurface state={view.researchReportsState} />
      )}
    </article>
  );
}

function IncomeTrendPanel({ view }: { view: DashboardHomeView }) {
  const hasRows =
    (view.incomeTrendState.kind === "ready" || view.incomeTrendState.kind === "partial") &&
    view.incomeTrend.length > 0;
  return (
    <article data-testid="dashboard-home-income-trend" className={`${styles.dhCard} ${styles.dhTerminalPanel}`}>
      <div className={styles.dhTerminalPanelHead}>
        <h3>收益趋势</h3>
        <DataStateBadge kind={view.incomeTrendState.kind} label={view.incomeTrendState.label} />
      </div>
      {hasRows ? (
        <div className={styles.dhTerminalIncomeTrend}>
          <div className={styles.dhTerminalIncomeChart}>
            <ReactECharts
              option={buildIncomeTrendOption(view.incomeTrend)}
              opts={{ renderer: "canvas" }}
              notMerge
              lazyUpdate
              style={{ height: "100%", width: "100%" }}
            />
          </div>
          <div className={styles.dhTerminalIncomeList}>
            {view.incomeTrend.slice(-4).map((point) => (
              <div key={point.id} className={styles.dhTerminalIncomeRow}>
                <span>{point.date.slice(5)}</span>
                <b className={styles.dhNum}>{point.portfolioPnl}</b>
                <small>基准 {point.benchmarkPnl}</small>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <StateSurface state={view.incomeTrendState} />
      )}
    </article>
  );
}

function BackendGapPanel({ gaps }: { gaps: DashboardHomeView["backendGaps"] }) {
  return (
    <article className={`${styles.dhCard} ${styles.dhTerminalPanel} ${styles.dhTerminalGapPanel}`}>
      <div className={styles.dhTerminalPanelHead}>
        <h3>后端工单</h3>
        <DataStateBadge kind="backend-gap" />
      </div>
      <div className={styles.dhTerminalGapList}>
        {gaps.map((gap) => (
          <div
            key={gap.id}
            data-testid={`dashboard-home-backend-gap-${gap.id}`}
            className={styles.dhTerminalGap}
          >
            <b>{gap.title}</b>
            <span>后端待接入</span>
            <small>{gap.neededEndpoint}</small>
          </div>
        ))}
      </div>
    </article>
  );
}

function QuickDrilldowns({ view }: { view: DashboardHomeView }) {
  const icons = [BarChartOutlined, LineChartOutlined, SafetyCertificateOutlined, FundProjectionScreenOutlined, DatabaseOutlined, StarFilled];
  return (
    <section data-testid="dashboard-home-bottom-grid" className={styles.dhTerminalBottom}>
      {view.quickDrilldowns.slice(0, 6).map((item, index) => {
        const Icon = icons[index] ?? ArrowRightOutlined;
        return (
          <Link key={item.id} to={item.path} className={`${styles.dhCard} ${styles.dhTerminalQuick}`}>
            <span>
              <Icon />
            </span>
            <b>{item.label}</b>
            <em>进入</em>
          </Link>
        );
      })}
    </section>
  );
}

export function TerminalHomeContent({ view }: TerminalHomeContentProps) {
  return (
    <>
      <TerminalKpiStrip view={view} />
      <RiskStrip items={view.keyRiskStrip} />

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
        {view.backendGaps.length > 0 ? <BackendGapPanel gaps={view.backendGaps} /> : null}
      </section>

      <ResearchCalendarSection calendar={view.researchCalendar} />
      <QuickDrilldowns view={view} />
    </>
  );
}
