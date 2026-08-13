import type { CSSProperties } from "react";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { EM_DASH } from "../../../utils/format";
import { PORTFOLIO_DIST_CHART_COLORS } from "./portfolioDistributionChart";
import type {
  ModuleHomeDetailPanel,
  ModuleHomeDistributionPanel,
  ModuleHomeDistributionRow,
  ModuleHomeTone,
} from "./moduleHomeModel";
import styles from "./portfolioHome.module.css";

const TABLE_ROW_LIMIT = 8;
const PORTFOLIO_ROW_LIMIT = 8;

function toneClass(tone: ModuleHomeTone) {
  if (tone === "ok") return styles.toneOk;
  if (tone === "watch") return styles.toneWatch;
  if (tone === "error") return styles.toneError;
  return styles.toneMuted;
}

function sortedRows(rows: ModuleHomeDistributionRow[]) {
  return [...rows].sort((left, right) => right.barPct - left.barPct).slice(0, TABLE_ROW_LIMIT);
}

function clampedPct(value: number) {
  return `${Math.max(0, Math.min(value, 100))}%`;
}

function segmentPct(value: number, total: number) {
  if (total <= 0) {
    return "0%";
  }
  return clampedPct((Math.max(value, 0) / total) * 100);
}

type PortfolioHoldingsHeroBandProps = {
  panel: ModuleHomeDistributionPanel | undefined;
  portfolioComparisonPanel?: ModuleHomeDetailPanel;
};

export function PortfolioHoldingsHeroBand({
  panel,
  portfolioComparisonPanel,
}: PortfolioHoldingsHeroBandProps) {
  const assetRows = panel ? sortedRows(panel.rows) : [];
  const portfolioRows = portfolioComparisonPanel?.rows.slice(0, PORTFOLIO_ROW_LIMIT) ?? [];
  const hasAssetData = assetRows.length > 0;
  const hasPortfolioData = portfolioRows.length > 0;
  const visibleAssetRows = assetRows.slice(0, 5);
  const visibleStackRows = visibleAssetRows.filter((row) => row.barPct > 0);
  const visibleTotalPct = visibleStackRows.reduce((sum, row) => sum + Math.max(row.barPct, 0), 0);

  if (!panel && !portfolioComparisonPanel) {
    return (
      <section
        data-testid="module-home-portfolio-holdings-hero"
        className={`${dhStyles.dhCard} ${styles.holdingsHeroBand}`}
      >
        <p className={`${styles.holdingsHeroEmpty} ${styles.toneWatch}`}>
          券种分布与子组合对比待返回；不展示样例持仓表。
        </p>
      </section>
    );
  }

  const heroTone = panel?.tone ?? portfolioComparisonPanel?.tone ?? "muted";
  // 用面板自身口径命名；外层区块头已经是「持仓结构全景」，此处再重复一次会撞名。
  const heroTitle = panel?.title ?? portfolioComparisonPanel?.title ?? "券种分布";
  const heroMeta = panel?.meta ?? portfolioComparisonPanel?.meta ?? "";
  const leadingRow = assetRows[0];
  const comparisonTable = hasPortfolioData ? (
    <table className={styles.srOnly} data-testid="module-home-portfolio-comparison-hero-table">
      <tbody>
        {portfolioRows.map((row) => {
          const cells = [
            row.label,
            row.scaleDisplay ?? row.value,
            row.durationDisplay,
            row.ytmDisplay,
            row.dv01Display,
            row.countDisplay,
          ].filter(Boolean);
          return (
            <tr key={row.key} data-testid={`module-home-portfolio-comparison-row-${row.key}`}>
              <td>{cells.join(" ")}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  ) : null;

  return (
    <section
      data-testid="module-home-portfolio-holdings-hero"
      className={`${dhStyles.dhCard} ${styles.holdingsHeroBand}`}
      data-tone={heroTone}
    >
      <div className={styles.holdingsHeroHead}>
        <div>
          <strong>{heroTitle}</strong>
          <p className={styles.holdingsHeroMeta}>{heroMeta}</p>
        </div>
        <em className={styles.holdingsHeroTotal}>{panel?.totalDisplay ?? "结构总览待返回"}</em>
      </div>

      {hasAssetData ? (
        <div className={styles.holdingsHeroSplit}>
          <div className={styles.holdingsHeroFigure}>
            <span className={styles.srOnly} data-testid="module-home-portfolio-holdings-lead">
              {leadingRow?.label ?? ""}
            </span>
            <span className={styles.srOnly} data-testid="module-home-portfolio-holdings-bars">
              {assetRows.map((row) => row.label).join(" ")}
            </span>
            <div className={styles.holdingsHeroFigureHead}>
              <span>{leadingRow?.label ?? "TOP"}</span>
              <strong>{leadingRow?.share !== EM_DASH ? leadingRow?.share : `${leadingRow?.barPct.toFixed(1) ?? 0}%`}</strong>
            </div>
            <div className={styles.holdingsHeroStackBar} aria-hidden="true">
              {visibleStackRows.map((row, index) => (
                <span
                  className={styles.holdingsHeroStackSegment}
                  data-color-index={index % PORTFOLIO_DIST_CHART_COLORS.length}
                  key={row.key}
                  style={
                    {
                      "--holdings-hero-segment-width": segmentPct(row.barPct, visibleTotalPct),
                    } as CSSProperties
                  }
                />
              ))}
            </div>
            <div className={styles.holdingsHeroFigureMeta}>
              <span>{panel?.totalDisplay ?? "合计"}</span>
              <em>{visibleAssetRows.length} 类</em>
            </div>
          </div>
          <ol className={styles.holdingsHeroBars}>
            {visibleAssetRows.map((row, index) => {
              const width = clampedPct(row.barPct);
              return (
                <li
                  className={styles.holdingsHeroBarRow}
                  data-testid={`module-home-portfolio-holdings-row-${row.key}`}
                  key={row.key}
                >
                  <div className={styles.holdingsHeroBarTop}>
                    <span className={styles.holdingsHeroBarLabel}>{row.label}</span>
                    <strong>{row.share !== EM_DASH ? row.share : `${row.barPct.toFixed(2)}%`}</strong>
                  </div>
                  <span className={styles.holdingsHeroBarTrack} aria-hidden="true">
                    <span
                      className={styles.holdingsHeroBarFill}
                      data-color-index={index % PORTFOLIO_DIST_CHART_COLORS.length}
                      style={{ "--holdings-hero-bar-width": width } as CSSProperties}
                    />
                  </span>
                  <span className={styles.holdingsHeroBarValue}>{row.marketValue}</span>
                </li>
              );
            })}
          </ol>
        </div>
      ) : (
        <p className={`${styles.holdingsHeroEmpty} ${toneClass(heroTone)}`}>
          {panel?.stateDetail ?? portfolioComparisonPanel?.stateDetail ?? "持仓读数待返回。"}
        </p>
      )}
      {comparisonTable}
    </section>
  );
}
