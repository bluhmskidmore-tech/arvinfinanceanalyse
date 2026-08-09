import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { LightIcon } from "../../../components/LightIcon";
import {
  buildBondTradingDeskPath,
  normalizeBondCode,
} from "../../bond-trading-desk/lib/bondTradingDeskPageModel";
import type {
  DashboardHomeBodyView,
  HomeDistributionSlice,
  HomeRiskExposureMetric,
  HomeTerminalListState,
} from "./dashboardHomeBodyView";
import type { DashboardHomeAvailability } from "./dashboardHomeAvailability";
import type { DashboardHomeFirstScreenView } from "./dashboardHomeFirstScreenTypes";
import { DashboardHomeHoldingDrawer } from "./DashboardHomeHoldingDrawer";
import { DashboardHomeOptionTwoGovernanceSection } from "./DashboardHomeOptionTwoGovernanceSection";
import { DashboardHomeOptionTwoResearchList } from "./DashboardHomeOptionTwoResearchList";
import { DashboardHomeOptionTwoSupportBand } from "./DashboardHomeOptionTwoSupportBand";
import {
  compactClock,
  reportDatePath,
  stateLabel,
  statusTone,
} from "./dashboardHomeOptionTwoShared";
import {
  normalizeHomeResearchLink,
  normalizeHomeResearchPublishedDate,
} from "./dashboardHomeResearchContract";
import {
  BondNewsSection,
  type BondNewsActions,
} from "./sections/BondNewsSection";
import { ResearchCalendarSection } from "./sections/ResearchCalendarSection";
import styles from "./dashboardHomeOptionTwo.module.css";

type DashboardHomeOptionTwoBodyProps = {
  view: DashboardHomeBodyView;
  firstScreenView: DashboardHomeFirstScreenView;
  bondNewsActions?: BondNewsActions;
  homeAvailability?: DashboardHomeAvailability;
  homeAvailabilityKind?: "normal" | "serviceUnavailable";
  focusPolicyFunding?: boolean;
  onRefresh?: () => void | Promise<unknown>;
  snapshotRefreshing?: boolean;
  supplementalStateLabel?: string;
  updatedAt?: string;
};

type AnalyticsTab = "asset" | "rating" | "maturity" | "industry" | "yield";
type MarketTab = "market" | "research";

const ANALYTICS_TABS: ReadonlyArray<{ id: AnalyticsTab; label: string }> = [
  { id: "asset", label: "资产配置" },
  { id: "rating", label: "信用评级" },
  { id: "maturity", label: "期限结构" },
  { id: "industry", label: "行业分布" },
  { id: "yield", label: "收益归因" },
];

function holdingDetailPath(code: string, reportDate: string): string | null {
  const normalizedCode = normalizeBondCode(code);
  const normalizedReportDate = reportDate.trim();
  if (
    !normalizedCode ||
    normalizedCode === "—" ||
    !/^\d{4}-\d{2}-\d{2}$/.test(normalizedReportDate)
  ) {
    return null;
  }
  return buildBondTradingDeskPath(normalizedCode, normalizedReportDate);
}

function ResearchPublishedAt({ value, compact = false }: { value: string; compact?: boolean }) {
  const publishedAt = normalizeHomeResearchPublishedDate(value);
  if (!publishedAt) return <>—</>;
  return (
    <time dateTime={publishedAt}>
      {compact ? publishedAt.slice(5, 10) : publishedAt}
    </time>
  );
}

function handleTabArrowKey<T extends string>(
  event: React.KeyboardEvent<HTMLButtonElement>,
  tabs: readonly T[],
  activeTab: T,
  onSelect: (tab: T) => void,
) {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  event.preventDefault();
  const currentIndex = tabs.indexOf(activeTab);
  const offset = event.key === "ArrowRight" ? 1 : -1;
  const nextIndex = (currentIndex + offset + tabs.length) % tabs.length;
  onSelect(tabs[nextIndex]);
  const tablist = event.currentTarget.parentElement;
  const buttons = tablist?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
  buttons?.[nextIndex]?.focus();
}

function StateMessage({ state }: { state: HomeTerminalListState }) {
  return (
    <div className={styles.stateMessage} data-tone={statusTone(state.kind)}>
      <strong>{stateLabel(state.kind)}</strong>
      <span>{state.label}</span>
    </div>
  );
}

function distributionPercent(value: number): number {
  return Math.max(0, Math.min(100, value));
}

type AggregateDisplay = {
  tone: "up" | "down" | "flat";
  value: string;
};

function aggregateDisplayValues(values: readonly string[]): AggregateDisplay | null {
  const parsed: Array<{ numeric: number; unit: string }> = [];
  for (const value of values) {
    const normalized = value.replaceAll(",", "").replaceAll("−", "-").trim();
    const match = normalized.match(/[+-]?\d+(?:\.\d+)?/);
    if (!match) return null;
    const numeric = Number(match[0]);
    if (!Number.isFinite(numeric)) return null;
    parsed.push({ numeric, unit: normalized.replace(match[0], "").trim() });
  }
  const units = new Set(parsed.map((item) => item.unit));
  if (parsed.length === 0 || units.size > 1) return null;
  const total = parsed.reduce((sum, item) => sum + item.numeric, 0);
  const sign = total > 0 ? "+" : "";
  const unit = parsed[0]?.unit;
  return {
    tone: total > 0 ? "up" : total < 0 ? "down" : "flat",
    value: `${sign}${total.toFixed(2)}${unit ? ` ${unit}` : ""}`,
  };
}

function DistributionColumn({
  title,
  rows,
  state,
}: {
  title: string;
  rows: readonly HomeDistributionSlice[];
  state: HomeTerminalListState;
}) {
  if (state.kind !== "ready" || rows.length === 0) {
    return (
      <section className={styles.distributionColumn}>
        <h3>{title}</h3>
        <StateMessage state={state} />
      </section>
    );
  }

  return (
    <section className={styles.distributionColumn}>
      <h3>{title}</h3>
      <div className={styles.distributionRows}>
        {rows.slice(0, 6).map((row) => (
          <div key={row.id} className={styles.distributionRow}>
            <span title={row.label}>{row.label}</span>
            <progress max={100} value={distributionPercent(row.pctRaw)} />
            <strong>{row.value}</strong>
            <em>{row.pct}</em>
          </div>
        ))}
        <div className={styles.distributionTotal}>
          <span>可见合计</span>
          <strong>
            {`${rows
              .slice(0, 6)
              .reduce((sum, row) => sum + distributionPercent(row.pctRaw), 0)
              .toFixed(2)}%`}
          </strong>
        </div>
      </div>
    </section>
  );
}

function readinessSummary(states: readonly HomeTerminalListState[]) {
  const ready = states.filter((state) => state.kind === "ready").length;
  const attention = states.length - ready;
  return { ready, attention, total: states.length };
}

export function DashboardHomeOptionTwoBody({
  view,
  firstScreenView,
  bondNewsActions,
  homeAvailability,
  homeAvailabilityKind = "normal",
  focusPolicyFunding = false,
  onRefresh,
  snapshotRefreshing = false,
  supplementalStateLabel,
  updatedAt,
}: DashboardHomeOptionTwoBodyProps) {
  const [analyticsTab, setAnalyticsTab] = useState<AnalyticsTab>("asset");
  const [marketTab, setMarketTab] = useState<MarketTab>("market");
  const [selectedHoldingId, setSelectedHoldingId] = useState<string | null>(null);
  const selectedHolding =
    view.holdingRows.find((row) => row.id === selectedHoldingId) ?? null;
  const visiblePositionChanges = view.positionChanges.slice(0, 5);
  const positionCurrentTotal = aggregateDisplayValues(
    visiblePositionChanges.map((row) => row.currentValue),
  );
  const positionChangeTotal = aggregateDisplayValues(
    visiblePositionChanges.map((row) => row.changeValue),
  );
  const visibleResearchReports = view.researchReports.slice(0, 5);
  const hasResearchNewsFallback = visibleResearchReports.some(
    (report) => report.isNewsFallback,
  );
  const researchDisclosure = hasResearchNewsFallback
    ? view.researchReportsState.label.includes("新闻补位")
      ? view.researchReportsState.label
      : `${view.researchReportsState.kind === "ready" ? "" : `${view.researchReportsState.label} · `}新闻补位`
    : view.researchReportsState.kind === "ready"
      ? null
      : view.researchReportsState.label;

  const distributionSets = useMemo(
    () => ({
      asset: {
        title: "资产分布（按市值口径）",
        rows: view.assetDistribution,
        state: view.assetDistributionState,
      },
      rating: {
        title: "评级分布（信用债）",
        rows: view.ratingDistribution,
        state: view.ratingDistributionState,
      },
      maturity: {
        title: "到期期限分布",
        rows: view.maturityDistribution,
        state: view.maturityDistributionState,
      },
      industry: {
        title: "行业分布（按市值口径）",
        rows: view.industryDistribution,
        state: view.industryDistributionState,
      },
      yield: {
        title: "收益分布",
        rows: view.yieldDistribution,
        state: view.yieldDistributionState,
      },
    }),
    [view],
  );
  const selectedDistribution = distributionSets[analyticsTab];
  const secondaryDistribution =
    analyticsTab === "rating" ? distributionSets.asset : distributionSets.rating;
  const tertiaryDistribution =
    analyticsTab === "maturity" ? distributionSets.industry : distributionSets.maturity;

  const moduleStates = [
    view.holdingsState,
    view.positionChangesState,
    view.riskExposureState,
    view.assetDistributionState,
    view.researchReportsState,
    view.incomeTrendState,
  ] as const;
  const trust = readinessSummary(moduleStates);
  const serviceUnavailable =
    homeAvailabilityKind === "serviceUnavailable" || homeAvailability?.kind === "error";
  const actions = firstScreenView.decisionRail.actions
    .filter((action) => action.id !== "no-action" && action.statusKind !== "empty")
    .slice(0, 4);
  const suggestions = firstScreenView.decisionRail.suggestions.slice(0, 4);
  const recommendationCount = actions.length > 0 ? actions.length : suggestions.length;
  const riskObservations = firstScreenView.keyRiskStrip.slice(
    0,
    Math.max(0, 4 - recommendationCount),
  );
  const riskPrimaryMetrics: HomeRiskExposureMetric[] = [];
  for (const labelToken of ["久期", "凸性"] as const) {
    const metric = view.riskExposureMetrics.find((item) => item.label.includes(labelToken));
    if (metric && !riskPrimaryMetrics.some((item) => item.id === metric.id)) {
      riskPrimaryMetrics.push(metric);
    }
  }
  for (const metric of view.riskExposureMetrics) {
    if (riskPrimaryMetrics.length >= 2) break;
    if (!riskPrimaryMetrics.some((item) => item.id === metric.id)) {
      riskPrimaryMetrics.push(metric);
    }
  }
  const riskPrimaryIds = new Set(riskPrimaryMetrics.map((metric) => metric.id));
  const riskSecondaryMetrics = view.riskExposureMetrics
    .filter((metric) => !riskPrimaryIds.has(metric.id))
    .slice(0, 3);
  const visibleRiskMetrics = [...riskPrimaryMetrics, ...riskSecondaryMetrics].slice(0, 5);
  const visibleRecommendationCount = actions.length > 0
    ? Math.min(actions.length, 3)
    : Math.min(suggestions.length, 3);
  const visibleRiskObservations = riskObservations.slice(
    0,
    Math.max(0, 3 - visibleRecommendationCount),
  );
  const riskItemCount = visibleRecommendationCount + visibleRiskObservations.length;
  const trustCompleteness = trust.total > 0
    ? Math.round((trust.ready / trust.total) * 100)
    : 0;
  const marketRows =
    view.marketTape && view.marketTape.length > 0
      ? view.marketTape.slice(0, 5).map((row) => ({
          id: row.id,
          label: row.label,
          value: row.value,
          delta: row.delta,
          tone: row.deltaTone,
        }))
      : view.marketContext.rateSeries.length > 0
        ? view.marketContext.rateSeries.slice(0, 5).map((row) => ({
            id: row.id,
            label: row.label,
            value: row.value,
            delta: row.delta,
            tone: row.deltaTone,
          }))
      : view.marketContext.curveTable.rows.slice(0, 5).map((row) => ({
          id: row.tenor,
          label: row.tenor,
          value: row.yieldLabel,
          delta: row.deltaLabel,
          tone: row.deltaTone,
        }));

  return (
    <section data-testid="dashboard-home-work-grid" className={styles.bodyGrid}>
      {homeAvailability && homeAvailability.kind !== "available" ? (
        <section
          className={styles.availabilityNotice}
          data-testid="dashboard-home-data-availability"
          data-state={homeAvailability.kind}
          data-tone={serviceUnavailable ? "bad" : "warn"}
        >
          <span>
            <strong>{homeAvailability.label}</strong>
            <small>{homeAvailability.reason}</small>
          </span>
          {onRefresh ? (
            <button
              type="button"
              data-testid="dashboard-home-data-availability-retry"
              onClick={() => void onRefresh()}
              disabled={snapshotRefreshing}
            >
              <LightIcon name="reload" />
              {snapshotRefreshing ? "刷新中" : "重新读取"}
            </button>
          ) : null}
        </section>
      ) : null}

      <div className={styles.holdingsRiskRow}>
        <section className={styles.holdingsChanges} aria-labelledby="option-two-holdings-title">
          <header className={styles.panelHeader}>
            <h2 id="option-two-holdings-title">重点持仓与变动</h2>
            <Link to={reportDatePath("/positions", view.reportDate)}>查看全部持仓</Link>
          </header>
          <div className={styles.holdingsChangesBody}>
            <section
              data-testid="dashboard-home-holdings-panel"
              className={styles.holdingsTablePanel}
            >
              <h3>{`重点持仓 Top${Math.min(12, view.holdingRows.length || 12)}`}</h3>
              {view.holdingsState.kind === "ready" && view.holdingRows.length > 0 ? (
                <div className={styles.tableScroller}>
                  <table data-testid="dashboard-home-holdings-table">
                    <thead>
                      <tr>
                        <th>排名</th>
                        <th>债券代码</th>
                        <th>债券简称</th>
                        <th>市值（亿）</th>
                        <th>占比</th>
                        <th>收益率</th>
                        <th>久期</th>
                      </tr>
                    </thead>
                    <tbody>
                      {view.holdingRows.slice(0, 12).map((row, index) => (
                        <tr key={row.id} data-testid="dashboard-home-holding-row">
                          <td>{index + 1}</td>
                          <td title={row.code}>{row.code}</td>
                          <td title={row.name}>
                            <button
                              type="button"
                              className={styles.holdingTrigger}
                              data-testid="dashboard-home-holding-open"
                              aria-label={`查看 ${row.name} 明细`}
                              onClick={() => setSelectedHoldingId(row.id)}
                            >
                              {row.name}
                            </button>
                          </td>
                          <td>{row.marketValue}</td>
                          <td>{row.weight}</td>
                          <td>{row.ytm}</td>
                          <td>{row.duration}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <StateMessage state={view.holdingsState} />
              )}
            </section>

            <section
              data-testid="dashboard-home-position-changes"
              className={styles.positionMatrix}
            >
          <h3>持仓变动矩阵（较上一报告日）</h3>
              {view.positionChangesState.kind === "ready" && view.positionChanges.length > 0 ? (
                <table>
                  <thead>
                    <tr>
                      <th>债券</th>
                      <th>当前</th>
                      <th>变动</th>
                      <th>方向</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visiblePositionChanges.map((row) => {
                      const detailPath = holdingDetailPath(row.code, view.reportDate);
                      return (
                        <tr key={row.id} data-testid="dashboard-home-position-change-row">
                          <td title={`${row.code} ${row.name}`}>
                            <strong>{row.name}</strong>
                            <small>{row.code}</small>
                          </td>
                          <td>{row.currentValue}</td>
                          <td data-tone={row.tone}>{row.changeValue}</td>
                          <td data-direction={row.direction}>
                            {detailPath ? (
                              <Link
                                to={detailPath}
                                aria-label={`查看 ${row.name}（${row.code}）明细`}
                              >
                                明细
                              </Link>
                            ) : (
                              <span
                                data-testid="dashboard-home-position-operation"
                                data-state="unavailable"
                                data-source="unavailable"
                              >
                                —
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  {positionCurrentTotal && positionChangeTotal ? (
                    <tfoot>
                      <tr>
                        <td>可见行合计</td>
                        <td>{positionCurrentTotal.value}</td>
                        <td data-tone={positionChangeTotal.tone}>{positionChangeTotal.value}</td>
                        <td>{`${visiblePositionChanges.length} 券`}</td>
                      </tr>
                    </tfoot>
                  ) : null}
                </table>
              ) : (
                <StateMessage state={view.positionChangesState} />
              )}
              <div
                className={styles.positionComparisonState}
                data-testid="dashboard-home-position-comparison"
                data-state={view.portfolioComparisonState.kind === "ready" ? "ready" : "unavailable"}
              >
                <span>组合对比</span>
                <strong>{stateLabel(view.portfolioComparisonState.kind)}</strong>
              </div>
              <section className={styles.incomeTrend} data-testid="dashboard-home-income-trend">
                <h3>收益趋势（组合 / 基准 / 超额）</h3>
                {view.incomeTrend.length > 0 ? (
                  <table>
                    <thead>
                      <tr>
                        <th>月份</th>
                        <th>组合损益</th>
                        <th>基准损益</th>
                        <th>超额损益</th>
                      </tr>
                    </thead>
                    <tbody>
                      {view.incomeTrend.slice(-3).map((row) => (
                        <tr key={row.id}>
                          <td>{row.date.slice(0, 7)}</td>
                          <td>{row.portfolioPnl}</td>
                          <td>{row.benchmarkPnl}</td>
                          <td>{row.excessPnl}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <StateMessage state={view.incomeTrendState} />
                )}
              </section>
            </section>
          </div>
        </section>

        <section
          data-testid="dashboard-home-risk-exposure"
          className={styles.riskTasks}
          aria-labelledby="option-two-risk-title"
        >
          <header className={styles.panelHeader}>
            <h2 id="option-two-risk-title">风险概览</h2>
            <span>
              {firstScreenView.headerStatus.governanceFeedAvailable === true
                ? `观测 ${riskItemCount} · 治理待办 ${firstScreenView.headerStatus.riskReviewCount}`
                : `观测 ${riskItemCount} · 治理待办未接入`}
            </span>
          </header>
          <section data-testid="dashboard-home-risk-metric-strip" className={styles.riskMetricGrid}>
            {visibleRiskMetrics.map((metric) => (
              <div key={metric.id}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
              </div>
            ))}
          </section>
          <section className={styles.actionList} aria-label="风险观测与建议">
            <h3>风险观测与建议</h3>
            {actions.length > 0 ? (
              actions.slice(0, 3).map((action) => (
                <div key={action.id} data-priority={action.priority}>
                  <span>
                    <LightIcon name={action.priority === "high" ? "alert" : "warning"} />
                    <strong>{action.title}</strong>
                    <small>{action.reason || action.sourceLabel}</small>
                  </span>
                  {action.to ? (
                    <Link to={action.to} aria-label={`查看风险项：${action.title}`}>
                      查看
                    </Link>
                  ) : (
                    <em>{stateLabel(action.statusKind)}</em>
                  )}
                </div>
              ))
            ) : suggestions.length > 0 ? (
              suggestions.slice(0, 3).map((suggestion) => (
                <div key={suggestion.id}>
                  <span>
                    <LightIcon name="bulb" />
                    <strong>{suggestion.text}</strong>
                    <small>组合建议</small>
                  </span>
                  {suggestion.to ? (
                    <Link to={suggestion.to} aria-label={`查看建议：${suggestion.text}`}>
                      查看
                    </Link>
                  ) : (
                    <em>待关注</em>
                  )}
                </div>
              ))
            ) : visibleRiskObservations.length === 0 ? (
              <p>
                {firstScreenView.headerStatus.governanceFeedAvailable === true
                  ? "暂无治理待办或风险观测"
                  : "暂无风险观测，治理待办源未接入"}
              </p>
            ) : null}
            {visibleRiskObservations.map((observation) => (
              <div key={`risk-observation-${observation.id}`} data-observation="true">
                <span>
                  <LightIcon name="info-circle" />
                  <strong>{observation.label}</strong>
                  <small>{`${observation.value} · ${observation.delta}`}</small>
                </span>
                <Link
                  to={reportDatePath("/risk-overview", view.reportDate)}
                  aria-label={`查看风险观测：${observation.label}`}
                >
                  查看
                </Link>
              </div>
            ))}
          </section>
        </section>
      </div>

      <div className={styles.analyticsMarketRow}>
        <section
          data-testid="dashboard-home-structure-board"
          className={styles.analyticsPanel}
          aria-labelledby="option-two-analytics-title"
        >
          <header className={styles.tabHeader}>
            <h2 id="option-two-analytics-title">组合透视</h2>
            <div role="tablist" aria-label="组合透视分类">
              {ANALYTICS_TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  id={`option-two-analytics-tab-${tab.id}`}
                  aria-controls="option-two-analytics-panel"
                  aria-selected={analyticsTab === tab.id}
                  tabIndex={analyticsTab === tab.id ? 0 : -1}
                  onClick={() => setAnalyticsTab(tab.id)}
                  onKeyDown={(event) =>
                    handleTabArrowKey(
                      event,
                      ANALYTICS_TABS.map((item) => item.id),
                      analyticsTab,
                      setAnalyticsTab,
                    )
                  }
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </header>
          <div
            id="option-two-analytics-panel"
            role="tabpanel"
            aria-labelledby={`option-two-analytics-tab-${analyticsTab}`}
            className={styles.analyticsColumns}
            data-testid="dashboard-home-structure-expanded-grid"
          >
            <DistributionColumn {...selectedDistribution} />
            <DistributionColumn {...secondaryDistribution} />
            <DistributionColumn {...tertiaryDistribution} />
          </div>
          <dl className={styles.portfolioMetrics}>
            {view.riskExposureMetrics.slice(0, 6).map((metric) => (
              <div key={metric.id} data-testid="dashboard-home-portfolio-metric">
                <dt>{metric.label}</dt>
                <dd>{metric.value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section
          data-testid="dashboard-home-deferred-matrix"
          className={styles.marketResearchPanel}
          aria-labelledby="option-two-market-title"
        >
          <header className={styles.tabHeader}>
            <h2 id="option-two-market-title">市场与研究</h2>
            <div role="tablist" aria-label="市场与研究分类">
              <button
                type="button"
                role="tab"
                id="option-two-market-tab-market"
                aria-controls="option-two-market-panel"
                aria-selected={marketTab === "market"}
                tabIndex={marketTab === "market" ? 0 : -1}
                onClick={() => setMarketTab("market")}
                onKeyDown={(event) =>
                  handleTabArrowKey(event, ["market", "research"], marketTab, setMarketTab)
                }
              >
                市场动态
              </button>
              <button
                type="button"
                role="tab"
                id="option-two-market-tab-research"
                aria-controls="option-two-market-panel"
                aria-selected={marketTab === "research"}
                tabIndex={marketTab === "research" ? 0 : -1}
                onClick={() => setMarketTab("research")}
                onKeyDown={(event) =>
                  handleTabArrowKey(event, ["market", "research"], marketTab, setMarketTab)
                }
              >
                研究报告
              </button>
            </div>
          </header>

          {marketTab === "market" ? (
            <div
              id="option-two-market-panel"
              role="tabpanel"
              aria-labelledby="option-two-market-tab-market"
              data-testid="dashboard-home-deferred-matrix-market"
            >
              <div className={styles.marketTape}>
                {marketRows.map((row) => (
                  <div key={row.id}>
                    <span>{row.label}</span>
                    <strong>{row.value}</strong>
                    <em data-tone={row.tone}>{row.delta}</em>
                  </div>
                ))}
              </div>
              <div
                className={styles.researchTableWrap}
                data-has-notice={researchDisclosure ? "true" : "false"}
                data-testid="dashboard-home-research-reports"
              >
                {researchDisclosure ? (
                  <div
                    className={styles.researchTableNotice}
                    data-state={view.researchReportsState.kind}
                    data-testid="dashboard-home-research-disclosure"
                    role="status"
                  >
                    {researchDisclosure}
                  </div>
                ) : null}
                <table>
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>标题</th>
                      <th>来源</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleResearchReports.map((row) => {
                      const researchLink = normalizeHomeResearchLink(row.link);
                      return (
                        <tr key={row.id} data-testid="dashboard-home-research-row">
                          <td><ResearchPublishedAt value={row.publishedAt} compact /></td>
                          <td title={row.title}>
                            {researchLink ? <a href={researchLink}>{row.title}</a> : row.title}
                          </td>
                          <td>{row.institution || row.source}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {view.researchReports.length === 0 ? (
                  <StateMessage state={view.researchReportsState} />
                ) : null}
              </div>
            </div>
          ) : (
            <div
              id="option-two-market-panel"
              role="tabpanel"
              aria-labelledby="option-two-market-tab-research"
              className={styles.researchList}
              data-testid="dashboard-home-deferred-matrix-research"
            >
              <DashboardHomeOptionTwoResearchList
                reports={view.researchReports}
                state={view.researchReportsState}
              />
            </div>
          )}

          <footer>
            <Link to={reportDatePath("/market-overview", view.reportDate)}>查看更多市场资讯</Link>
          </footer>
        </section>
      </div>

      <DashboardHomeOptionTwoSupportBand
        view={view}
        dataStatusKind={firstScreenView.headerStatus.dataStatusKind}
      />

      <section
        data-testid="dashboard-home-data-tasks"
        className={styles.trustFooter}
        aria-label="数据证据"
      >
        <strong>数据证据</strong>
        <span>
          <LightIcon name="database" />
          {`核心模块 ${trust.total}`}
        </span>
        <span data-tone={trust.ready === trust.total ? "ok" : "warn"}>
          <LightIcon name="check-circle" />
          {`核心就绪 ${trust.ready}/${trust.total}`}
        </span>
        <span data-tone={trust.attention > 0 ? "warn" : "ok"}>
          <LightIcon name={trust.attention > 0 ? "alert" : "safety-certificate"} />
          {`核心关注 ${trust.attention} 项`}
        </span>
        <span>
          <LightIcon name="check-square" />
          {`核心模块就绪率 ${trustCompleteness}%`}
        </span>
        <span>
          <LightIcon name="calendar" />
          {`报告日 ${view.reportDate}`}
        </span>
        <span>
          <LightIcon name="clock" />
          {`更新 ${compactClock(updatedAt || firstScreenView.headerStatus.dataUpdatedAt)}`}
        </span>
        {supplementalStateLabel ? (
          <span data-tone="warn">{`辅助来源 · ${supplementalStateLabel}`}</span>
        ) : null}
        <Link
          data-testid="dashboard-home-data-task-footer"
          to={reportDatePath("/reports", view.reportDate)}
        >
          查看数据质量报告
          <LightIcon name="arrow-right" />
        </Link>
      </section>

      <DashboardHomeOptionTwoGovernanceSection
        view={view}
        availability={homeAvailability}
        supplementalStateLabel={supplementalStateLabel}
      />

      <section
        className={styles.extendedEvidence}
        aria-labelledby="dashboard-home-research-evidence-title"
      >
        <header className={styles.extendedEvidenceHeader}>
          <div>
            <span aria-hidden="true">04</span>
            <h2 id="dashboard-home-research-evidence-title">研究与资讯证据</h2>
          </div>
          <small>事件、政策与债券新闻</small>
        </header>
        <ResearchCalendarSection
          macroBriefing={view.macroBriefing}
          focusPolicyFunding={focusPolicyFunding}
        />
        <BondNewsSection
          bondNews={view.bondNews}
          actions={bondNewsActions}
          sectionIndex="04.1"
          updatedAt={compactClock(updatedAt || firstScreenView.headerStatus.dataUpdatedAt)}
        />
      </section>

      {selectedHolding ? (
        <DashboardHomeHoldingDrawer
          holdingCount={view.holdingRows.length}
          holdingsState={view.holdingsState}
          onClose={() => setSelectedHoldingId(null)}
          reportDate={view.reportDate}
          row={selectedHolding}
        />
      ) : null}
    </section>
  );
}
