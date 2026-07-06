import type { ModuleHomeDetailPanel, ModuleHomeDetailRow, ModuleHomeTone } from "./moduleHomeModel";
import { PortfolioStructureChart } from "./PortfolioStructureChart";
import dhStyles from "../dashboard-home/dashboardHome.module.css";
import styles from "./portfolioHome.module.css";

function toneClass(tone: ModuleHomeTone) {
  if (tone === "ok") return styles.toneOk;
  if (tone === "watch") return styles.toneWatch;
  if (tone === "error") return styles.toneError;
  return styles.toneMuted;
}

function statePillClass(tone: ModuleHomeTone) {
  if (tone === "ok") return `${styles.statePill} ${styles.stateOk}`;
  if (tone === "error") return `${styles.statePill} ${styles.stateError}`;
  if (tone === "watch") return `${styles.statePill} ${styles.stateWatch}`;
  return styles.statePill;
}

function structureRowMetrics(row: ModuleHomeDetailRow) {
  const sourceParts = row.source
    .split("·")
    .map((part) => part.trim())
    .filter(Boolean);
  const fallbackMetric = sourceParts[0]?.replace(/^DV01\s*/i, "") ?? row.source;
  const fallbackCount = sourceParts[1] ?? "";
  return {
    metric: row.dv01Display ?? fallbackMetric,
    count: row.countDisplay ? `${row.countDisplay} 只` : fallbackCount,
  };
}

type PortfolioStructureTabPanelProps = {
  panel: ModuleHomeDetailPanel;
};

export function PortfolioStructureTabPanel({ panel }: PortfolioStructureTabPanelProps) {
  const hasChart = Boolean(panel.chart && panel.chart.categories.length > 0);

  return (
    <div className={`${styles.embeddedPanel} ${hasChart ? styles.structureSplit : ""}`}>
      <div className={styles.structureListCol}>
        <div className={styles.embeddedPanelHead}>
          <span className={statePillClass(panel.tone)}>{panel.stateLabel}</span>
        </div>
        <p className={styles.detailSource}>{panel.meta}</p>
        {panel.rows.length > 0 ? (
          <>
            <div className={styles.compactListHeader} aria-hidden="true">
              <span>子组合</span>
              <span>DV01</span>
              <span>持仓</span>
              <span>市值</span>
            </div>
            <ul className={styles.compactList}>
              {panel.rows.map((row) => {
                const metrics = structureRowMetrics(row);
                return (
                  <li className={styles.compactRow} key={row.key}>
                    <div className={styles.compactRowMain}>
                      <span className={styles.compactLabel}>{row.label}</span>
                    </div>
                    <span className={styles.compactSource}>{metrics.metric}</span>
                    <span className={styles.compactCount}>{metrics.count}</span>
                    <span className={`${styles.compactValue} ${toneClass(row.tone)}`}>{row.value}</span>
                  </li>
                );
              })}
            </ul>
          </>
        ) : (
          <p className={`${styles.detailSource} ${toneClass(panel.tone)}`}>{panel.stateDetail}</p>
        )}
      </div>
      {hasChart && panel.chart ? (
        <div className={`${dhStyles.dhInsetSurface} ${styles.structureChartCol}`}>
          <PortfolioStructureChart chart={panel.chart} />
        </div>
      ) : null}
    </div>
  );
}
