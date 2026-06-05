import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { AttributionWaterfallChart } from "../../dashboard/sections/AttributionWaterfallChart";
import type { DashboardCockpitWaterfallItem } from "../../dashboard/dashboardCockpitModel";
import type { DashboardHomeView, HomeAttributionTab } from "../dashboardHomeView";
import { resolveDeltaClass } from "../dashboardHomeView";
import styles from "../dashboardHome.module.css";

type WorkGridSectionProps = {
  portfolioStats: DashboardHomeView["portfolioStats"];
  assetBars: DashboardHomeView["assetBars"];
  assetBarsPlaceholder: boolean;
  centerAum: DashboardHomeView["centerAum"];
  interbank: DashboardHomeView["interbank"];
  attributionTabs: DashboardHomeView["attributionTabs"];
  attributionWaterfall: DashboardHomeView["attributionWaterfall"];
  attributionInsights: DashboardHomeView["attributionInsights"];
  attributionNote: DashboardHomeView["attributionNote"];
  riskCards: DashboardHomeView["riskCards"];
  riskCardsPlaceholder: boolean;
  riskRadar: DashboardHomeView["riskRadar"];
  todos: DashboardHomeView["todos"];
  watchlist: DashboardHomeView["watchlist"];
  watchlistPlaceholder: boolean;
  liabilityWatchBasisNote: string | null;
};

const FILL_CLASS: Record<string, string> = {
  blue: styles.dhFillBlue,
  redish: styles.dhFillRed,
  greenish: styles.dhFillGreen,
  grey: styles.dhFillGrey,
};

const DIST_COLOR: Record<string, string> = {
  blue: "var(--dh-dist-blue)",
  redish: "var(--dh-dist-cyan)",
  greenish: "var(--dh-dist-teal)",
  grey: "var(--dh-dist-neutral)",
};

const ATTRIBUTION_TAB_ORDER: readonly HomeAttributionTab["id"][] = ["day", "week", "month", "ytd"];

function buildDonutGradient(bars: DashboardHomeView["assetBars"]): string {
  if (bars.length === 0) {
    return "conic-gradient(var(--dh-dist-blue) 0 100%)";
  }
  let cursor = 0;
  const stops = bars.map((bar) => {
    const start = cursor;
    cursor += bar.pct;
    const color = DIST_COLOR[bar.fillClass] ?? DIST_COLOR.blue;
    return `${color} ${start}% ${cursor}%`;
  });
  return `conic-gradient(${stops.join(", ")})`;
}

function priorityClass(priority: string): string {
  if (priority === "高") return styles.dhPriorityHi;
  if (priority === "中") return styles.dhPriorityMid;
  return styles.dhPriorityLow;
}

function PlaceholderBadge() {
  return <span className={styles.dhBadgePlaceholder}>样例数据 · 接入中</span>;
}

const RADAR_RADII = [66, 49, 33] as const;
const RADAR_OUTER = 66;
const RADAR_CENTER_X = 100;
const RADAR_CENTER_Y = 92;
const RADAR_LABEL_RADIUS = RADAR_OUTER + 20;

function RadarChart({ radar }: { radar: DashboardHomeView["riskRadar"] }) {
  const polygon = buildRadarPolygonPoints(radar.values, RADAR_OUTER);
  const axisPoints = buildRadarAxisPoints(radar.dimensions.length, RADAR_OUTER);
  const labelPos = buildRadarLabelPos(radar.dimensions.length, RADAR_LABEL_RADIUS);
  const warnPoints = buildRadarPolygonPoints(
    Array.from({ length: radar.dimensions.length }, () => 80),
    RADAR_OUTER,
  );
  return (
    <svg viewBox="0 0 200 200" className={styles.dhRadarSvg} role="img" aria-label="风险敞口雷达">
      <g transform={`translate(${RADAR_CENTER_X} ${RADAR_CENTER_Y})`}>
        {RADAR_RADII.map((radius) => {
          const ringPoints = buildRadarAxisPoints(radar.dimensions.length, radius);
          return (
            <polygon
              key={radius}
              points={ringPoints.join(" ")}
              fill="none"
              stroke={radius === RADAR_OUTER ? "#dbe4ef" : "#e5ebf3"}
            />
          );
        })}
        {axisPoints.map((pt, idx) => (
          <line key={idx} x1="0" y1="0" x2={pt.split(",")[0]} y2={pt.split(",")[1]} stroke="#e3e9f1" />
        ))}
        {warnPoints ? (
          <polygon points={warnPoints} className={styles.dhRadarWarnLine} />
        ) : null}
        {polygon ? (
          <polygon points={polygon} className={styles.dhRadarPolyFill} />
        ) : null}
        {radar.values.map((value, idx) => {
          const normalized = Math.max(0, Math.min(1, value / 100));
          const r = normalized * RADAR_OUTER;
          const angleStep = (Math.PI * 2) / radar.values.length;
          const angle = -Math.PI / 2 + idx * angleStep;
          const cx = Math.cos(angle) * r;
          const cy = Math.sin(angle) * r;
          return (
            <circle
              key={idx}
              cx={cx.toFixed(2)}
              cy={cy.toFixed(2)}
              r="3"
              className={styles.dhRadarDot}
            />
          );
        })}
      </g>
      <g fontSize="10" fill="#334155" fontWeight="700">
        {radar.dimensions.map((dim, idx) => {
          const pos = labelPos[idx]!;
          const x = RADAR_CENTER_X + pos.x;
          const y = RADAR_CENTER_Y + pos.y + 3;
          const anchor = pos.x > 6 ? "start" : pos.x < -6 ? "end" : "middle";
          return (
            <text key={dim} x={x} y={y} textAnchor={anchor}>
              {dim}
            </text>
          );
        })}
      </g>
      <g fontSize="9" fill="#334155">
        <line x1="24" y1="188" x2="38" y2="188" className={styles.dhRadarLegendCurrent} />
        <text x="44" y="191">当前水平</text>
        <line x1="108" y1="188" x2="122" y2="188" className={styles.dhRadarLegendWarn} />
        <text x="127" y="191">预警线</text>
      </g>
    </svg>
  );
}

function buildRadarPolygonPoints(values: readonly number[], radius: number, max = 100): string {
  if (values.length === 0) {
    return "";
  }
  const angleStep = (Math.PI * 2) / values.length;
  return values
    .map((value, index) => {
      const normalized = Math.max(0, Math.min(1, value / max));
      const r = normalized * radius;
      const angle = -Math.PI / 2 + index * angleStep;
      const x = Math.cos(angle) * r;
      const y = Math.sin(angle) * r;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function buildRadarAxisPoints(count: number, radius: number): string[] {
  const angleStep = (Math.PI * 2) / count;
  return Array.from({ length: count }, (_, index) => {
    const angle = -Math.PI / 2 + index * angleStep;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });
}

function buildRadarLabelPos(count: number, radius: number) {
  const angleStep = (Math.PI * 2) / count;
  return Array.from({ length: count }, (_, index) => {
    const angle = -Math.PI / 2 + index * angleStep;
    return {
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
    };
  });
}

function attributionSummaryLabels(tabId: HomeAttributionTab["id"]) {
  switch (tabId) {
    case "week":
      return {
        pnl: "周度规模变动",
        change: "较上周规模变动",
        yield: "周度收益率",
      };
    case "month":
      return {
        pnl: "月度损益",
        change: "较上月规模变动",
        yield: "月度收益率",
      };
    case "ytd":
      return {
        pnl: "YTD 损益",
        change: "YTD 明细",
        yield: "YTD 收益率",
      };
    case "day":
    default:
      return {
        pnl: "当日损益（不含FTP）",
        change: "较昨日规模变动",
        yield: "日度收益率",
      };
  }
}

export function WorkGridSection({
  portfolioStats,
  assetBars,
  assetBarsPlaceholder,
  centerAum,
  interbank,
  attributionTabs,
  attributionWaterfall,
  attributionInsights,
  attributionNote,
  riskCards,
  riskCardsPlaceholder,
  riskRadar,
  todos,
  watchlist,
  watchlistPlaceholder,
  liabilityWatchBasisNote,
}: WorkGridSectionProps) {
  const [activeTab, setActiveTab] = useState<HomeAttributionTab["id"]>("day");
  const active = attributionTabs.find((tab) => tab.id === activeTab) ?? attributionTabs[0];
  const summaryLabels = attributionSummaryLabels(activeTab);
  const donutStyle = useMemo(() => ({ background: buildDonutGradient(assetBars) }), [assetBars]);
  const waterfallItems = attributionWaterfall as readonly DashboardCockpitWaterfallItem[];

  return (
    <section data-testid="dashboard-home-work-grid" className={styles.dhWorkGrid}>
      <article className={`${styles.dhCard} ${styles.dhPanel}`}>
        <div className={styles.dhSectionTitle}>
          <span>资产与收益概览</span>
        </div>
        <div className={styles.dhStatsRow}>
          {portfolioStats.map((stat) => (
            <div key={stat.id} className={styles.dhStat}>
              <div className={styles.dhStatLabel}>{stat.label}</div>
              <div className={`${styles.dhStatValue} ${styles.dhNum}`}>{stat.value}</div>
            </div>
          ))}
        </div>
        <div className={`${styles.dhSectionTitle} ${styles.dhSectionTitleSm}`}>
          <span>资产分布（按券种）</span>
          {assetBarsPlaceholder ? <PlaceholderBadge /> : null}
        </div>
        <div
          className={`${styles.dhDistWrap}${assetBarsPlaceholder ? ` ${styles.dhDimmed}` : ""}`}
        >
          <div>
            {assetBars.map((bar) => (
              <div key={bar.id} className={styles.dhAssetRow}>
                <span>{bar.label}</span>
                <div className={styles.dhTrack}>
                  <div
                    className={FILL_CLASS[bar.fillClass] ?? styles.dhFillBlue}
                    style={{ width: `${bar.pct}%` }}
                  />
                </div>
                <span>{bar.value}</span>
                <span>{bar.pct.toFixed(1)}%</span>
              </div>
            ))}
          </div>
          <div className={styles.dhDonut} style={donutStyle}>
            <div className={styles.dhDonutHole} />
            <div className={styles.dhDonutCenter}>
              <div>
                <small>{centerAum.label}</small>
                <b className={styles.dhNum}>{centerAum.value}</b>
              </div>
            </div>
          </div>
        </div>
        <div className={`${styles.dhInterbank} ${styles.dhPanelFooter}`}>
          <div className={styles.dhIb}>
            <div className={styles.dhStatLabel}>同业资产</div>
            <div className={`${styles.dhStatValue} ${styles.dhNum}`}>{interbank.assets}</div>
          </div>
          <div className={styles.dhIb}>
            <div className={styles.dhStatLabel}>同业负债</div>
            <div className={`${styles.dhStatValue} ${styles.dhNum}`}>{interbank.liabilities}</div>
          </div>
          <div className={styles.dhIb}>
            <div className={styles.dhStatLabel}>净头寸</div>
            <div
              className={`${styles.dhStatValue} ${styles.dhNum} ${resolveDeltaClass(interbank.netTone, styles)}`}
            >
              {interbank.net}
            </div>
          </div>
        </div>
      </article>

      <article className={`${styles.dhCard} ${styles.dhPanel}`}>
        <div className={styles.dhSectionTitle}>
          <span>损益归因（今日）</span>
          <Link to="/product-category-pnl" className={styles.dhLink}>
            归因明细 →
          </Link>
        </div>
        <div className={styles.dhTabs} role="tablist">
          {ATTRIBUTION_TAB_ORDER.map((tabId) => {
            const tab = attributionTabs.find((item) => item.id === tabId);
            if (!tab) {
              return null;
            }
            return (
              <button
                key={tabId}
                type="button"
                role="tab"
                className={
                  tabId === activeTab ? `${styles.dhTab} ${styles.dhTabActive}` : styles.dhTab
                }
                onClick={() => setActiveTab(tabId)}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
        <div className={styles.dhSummaryRow}>
          <div className={styles.dhSummaryItem}>
            <div className={styles.dhStatLabel}>{summaryLabels.pnl}</div>
            <div className={`${styles.dhStatValue} ${styles.dhNum}`}>{active?.pnl ?? "—"}</div>
          </div>
          <div className={styles.dhSummaryItem}>
            <div className={styles.dhStatLabel}>{summaryLabels.change}</div>
            <div className={`${styles.dhStatValue} ${styles.dhNum}`}>{active?.change ?? "—"}</div>
          </div>
          <div className={styles.dhSummaryItem}>
            <div className={styles.dhStatLabel}>{summaryLabels.yield}</div>
            <div className={`${styles.dhStatValue} ${styles.dhNum}`}>{active?.yield ?? "—"}</div>
          </div>
        </div>
        <div className={`${styles.dhSectionTitle} ${styles.dhSectionTitleSm}`}>
          <span>收益来源拆解（单位：万）</span>
        </div>
        <div className={styles.dhAttributionChartWrap}>
          {waterfallItems.length > 0 ? (
            <AttributionWaterfallChart items={waterfallItems} />
          ) : (
            <p className={styles.dhEmpty}>归因瀑布图待同步</p>
          )}
        </div>
        <div
          className={
            attributionNote.length > 0
              ? styles.dhInsightRow
              : `${styles.dhInsightRow} ${styles.dhPanelFooter}`
          }
        >
          <span>
            最大拖累：{attributionInsights.maxDragLabel}{" "}
            <b className={styles.dhUpRed}>{attributionInsights.maxDragValue}</b>
          </span>
          <span>
            最大贡献：{attributionInsights.maxContributionLabel}{" "}
            <b className={styles.dhDownGreen}>{attributionInsights.maxContributionValue}</b>
          </span>
        </div>
        {attributionNote.length > 0 ? (
          <div className={`${styles.dhNoteBox} ${styles.dhPanelFooter}`}>
            <b>组合变化说明</b>
            <br />
            {attributionNote.map((line, index) => (
              <span key={index}>
                {index + 1}. {line}
                <br />
              </span>
            ))}
          </div>
        ) : null}
      </article>

      <article className={`${styles.dhCard} ${styles.dhPanel}`}>
        <div className={styles.dhSectionTitle}>
          <span>风险处置总览</span>
          <Link to="/risk-tensor" className={styles.dhLink}>
            进入风险处置台 →
          </Link>
        </div>
        <div className={styles.dhRiskLayout}>
          <div className={styles.dhRadarWrap}>
            <div className={styles.dhSectionTitleRow}>
              <span>风险敞口雷达</span>
            </div>
            {riskRadar.placeholder ? (
              <span className={`${styles.dhBadgePlaceholder} ${styles.dhRadarBadge}`}>
                样例数据 · 接入中
              </span>
            ) : null}
            <RadarChart radar={riskRadar} />
          </div>
          <div>
            <div className={styles.dhRiskCards}>
              {riskCards.map((card) => (
                <div key={card.id} className={styles.dhRiskCard}>
                  <div className={styles.dhStatLabel}>{card.label}</div>
                  <div
                    className={`${styles.dhStatValue} ${styles.dhNum} ${resolveDeltaClass(card.tone, styles)}`}
                  >
                    {card.count}
                  </div>
                </div>
              ))}
            </div>
            {riskCardsPlaceholder ? (
              <div className={styles.dhInlineHint}>中/低风险口径接入中</div>
            ) : null}
            <div className={`${styles.dhSectionTitle} ${styles.dhSectionTitleSm}`}>
              <span>待办清单</span>
            </div>
            <ul className={styles.dhTodoList}>
              {todos.length === 0 ? (
                <li className={styles.dhInlineHint}>待办接入中</li>
              ) : (
                todos.map((todo) => (
                  <li key={todo.id}>
                    <span>{todo.title}</span>
                    <span className={priorityClass(todo.priority)}>{todo.priority}</span>
                  </li>
                ))
              )}
            </ul>
          </div>
        </div>
        <div className={`${styles.dhWatchlistDivider} ${styles.dhPanelFooter}`}>
          <div className={`${styles.dhSectionTitle} ${styles.dhSectionTitleSm}`}>
            <span>观察清单</span>
            {watchlistPlaceholder ? <PlaceholderBadge /> : null}
          </div>
          {liabilityWatchBasisNote ? (
            <p className={styles.dhLiabilityBasisNote}>{liabilityWatchBasisNote}</p>
          ) : null}
          <div className={watchlistPlaceholder ? styles.dhDimmed : undefined}>
            {watchlist.map((item) => (
              <div key={item.id} className={styles.dhObsRow}>
                <span>{item.label}</span>
                <b className={styles.dhNum}>{item.count}</b>
              </div>
            ))}
          </div>
        </div>
      </article>
    </section>
  );
}
