import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import dhStyles from "../dashboard-home/dashboardHome.module.css";
import type { ModuleHomeDistributionPanel, ModuleHomeDistributionRow, ModuleHomeTone } from "./moduleHomeModel";
import styles from "./portfolioHome.module.css";

const CHART_COLORS = ["#35679b", "#6f96c3", "#a8bfd8", "#3f8a6a", "#c76b66", "#b6c1cf"];

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
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const item = params as { name: string; percent: number };
        const row = rows.find((entry) => entry.label === item.name);
        return `${item.name}<br/>${item.percent.toFixed(2)}%${row ? `<br/>${row.marketValue}` : ""}`;
      },
    },
    series: [
      {
        type: "pie",
        radius: ["52%", "78%"],
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
        data: rows.map((row) => ({
          name: row.label,
          value: Math.max(row.barPct, 0),
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
      <div className={dhStyles.dhTerminalPanelHead}>
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
              style={{ height: 156, width: "100%" }}
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
                <li className={styles.distItem} key={row.key}>
                  <div className={styles.distItemHead}>
                    <span
                      className={styles.distDot}
                      data-color-index={index % CHART_COLORS.length}
                      aria-hidden="true"
                    />
                    <span className={styles.distLabel} title={row.label}>
                      {row.label}
                    </span>
                    <span className={styles.distMetric}>{formatMetric(row)}</span>
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
        <p className={`${styles.distMeta} ${toneClass(panel.tone)}`}>{panel.stateDetail}</p>
      )}
    </article>
  );
}
