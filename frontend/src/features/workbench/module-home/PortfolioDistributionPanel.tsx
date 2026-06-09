import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import dhStyles from "../dashboard-home/dashboardHome.module.css";
import type { ModuleHomeDistributionPanel, ModuleHomeDistributionRow, ModuleHomeTone } from "./moduleHomeModel";
import styles from "./portfolioHome.module.css";

const CHART_COLORS = ["#1850a1", "#2563eb", "#2d8a5e", "#d97706", "#ef4444"];
const EMPTY_BAR_COUNT = 5;

function toneClass(tone: ModuleHomeTone) {
  if (tone === "ok") return styles.toneOk;
  if (tone === "watch") return styles.toneWatch;
  if (tone === "error") return styles.toneError;
  return styles.toneMuted;
}

function sortedRows(rows: ModuleHomeDistributionRow[]) {
  return [...rows].sort((left, right) => right.barPct - left.barPct).slice(0, 5);
}

function topRow(rows: ModuleHomeDistributionRow[]) {
  if (rows.length === 0) {
    return null;
  }
  return rows.reduce((best, row) => (row.barPct > best.barPct ? row : best));
}

function formatMetric(row: ModuleHomeDistributionRow) {
  const value = row.marketValue.replace(" 亿元", "亿");
  const share = row.share !== "-" ? row.share : `${row.barPct.toFixed(2)}%`;
  return `${value} · ${share}`;
}

function buildPieOption(rows: ModuleHomeDistributionRow[]): EChartsOption {
  return {
    color: CHART_COLORS,
    animationDuration: 420,
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(8, 25, 47, 0.94)",
      borderColor: "rgba(96, 165, 250, 0.42)",
      borderWidth: 1,
      padding: [8, 10],
      textStyle: {
        color: "#f8fafc",
        fontSize: 11,
        fontWeight: 650,
      },
      formatter: (params: unknown) => {
        const item = params as { name: string; percent: number };
        const row = rows.find((entry) => entry.label === item.name);
        return `${item.name}<br/>${item.percent.toFixed(2)}%${row ? `<br/>${row.marketValue}` : ""}`;
      },
    },
    series: [
      {
        type: "pie",
        radius: ["50%", "82%"],
        center: ["50%", "50%"],
        startAngle: 104,
        minAngle: 4,
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: {
          borderColor: "#f8fafc",
          borderWidth: 3,
          shadowBlur: 8,
          shadowColor: "rgba(15, 23, 42, 0.12)",
        },
        emphasis: {
          scale: true,
          scaleSize: 6,
          itemStyle: {
            shadowBlur: 14,
            shadowColor: "rgba(15, 23, 42, 0.22)",
          },
        },
        data: rows.map((row, index) => ({
          name: row.label,
          value: Math.max(row.barPct, 0),
          itemStyle: {
            color: CHART_COLORS[index % CHART_COLORS.length],
          },
        })),
      },
    ],
  };
}

type PortfolioDistributionPanelProps = {
  panel: ModuleHomeDistributionPanel;
};

export function PortfolioDistributionPanel({ panel }: PortfolioDistributionPanelProps) {
  const rows = sortedRows(panel.rows);
  const hasData = rows.length > 0;
  const leader = topRow(rows);

  return (
    <article
      className={`${dhStyles.dhCard} ${dhStyles.dhTerminalPanel} ${styles.distPanel}`}
      data-testid={`module-home-distribution-${panel.key}`}
    >
      <div className={`${dhStyles.dhTerminalPanelHead} ${styles.distPanelHead}`}>
        <h3>{panel.title}</h3>
        <div className={styles.distHeadActions}>
          {panel.viewAllPath ? (
            <Link className={styles.distViewAll} to={panel.viewAllPath}>
              查看全部
            </Link>
          ) : null}
          {panel.tone === "ok" ? null : (
            <span className={`${styles.distStateBadge} ${toneClass(panel.tone)}`}>{panel.stateLabel}</span>
          )}
        </div>
      </div>

      <div className={styles.distSummaryStrip}>
        {leader ? (
          <p className={styles.distTopHighlight} data-testid={`module-home-distribution-top-${panel.key}`}>
            <span className={styles.distTopLabel}>最大项</span>
            <strong title={leader.label}>{leader.label}</strong>
            <em>{leader.share !== "-" ? leader.share : `${leader.barPct.toFixed(2)}%`}</em>
          </p>
        ) : null}
        <p className={styles.distMeta}>{panel.meta}</p>
        {panel.subtitle ? <p className={styles.distSubtitle}>{panel.subtitle}</p> : null}
      </div>

      {hasData ? (
        <div className={styles.distBody}>
          <div className={styles.distChartCol}>
            <ReactECharts
              option={buildPieOption(rows)}
              opts={{ renderer: "canvas" }}
              notMerge
              lazyUpdate
              style={{ height: "var(--dist-chart-height, 188px)", width: "100%" }}
            />
            <div className={styles.distChartCenter} aria-hidden="true">
              <span>{panel.totalDisplay ? "合计" : "Top1"}</span>
              <strong>{panel.totalDisplay ?? (leader ? leader.share : "—")}</strong>
            </div>
          </div>

          <ul className={styles.distList}>
            {rows.map((row, index) => {
              const width = `${Math.max(4, Math.min(row.barPct, 100))}%`;
              return (
                <li className={styles.distItem} key={row.key} title={`${row.label} ${formatMetric(row)}`}>
                  <div className={styles.distItemHead}>
                    <span
                      className={styles.distDot}
                      data-color-index={index % CHART_COLORS.length}
                      aria-hidden="true"
                    />
                    <span className={styles.distLabel} title={row.label}>
                      {row.label}
                    </span>
                    <span className={styles.distMetric}>{row.share !== "-" ? row.share : `${row.barPct.toFixed(2)}%`}</span>
                    <span className={styles.distMarketValue}>{row.marketValue}</span>
                  </div>
                  <div className={styles.distBarTrack} aria-hidden="true">
                    <span
                      className={styles.distBarFill}
                      data-color-index={index % CHART_COLORS.length}
                      style={{ "--dist-bar-width": width } as CSSProperties}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <div
          className={styles.distEmptyState}
          data-tone={panel.tone}
          data-testid={`module-home-distribution-empty-${panel.key}`}
        >
          <div className={styles.distEmptyChart} aria-hidden="true">
            {Array.from({ length: EMPTY_BAR_COUNT }, (_, index) => (
              <span data-color-index={index % CHART_COLORS.length} key={index} />
            ))}
          </div>
          <div className={styles.distEmptyBars} aria-hidden="true">
            {Array.from({ length: EMPTY_BAR_COUNT }, (_, index) => (
              <span data-color-index={index % CHART_COLORS.length} key={index} />
            ))}
          </div>
          <p className={`${styles.distMeta} ${toneClass(panel.tone)}`}>{panel.stateDetail}</p>
        </div>
      )}
    </article>
  );
}
