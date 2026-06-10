import { Link } from "react-router-dom";

import ReactECharts from "../../../lib/echarts";
import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { buildPortfolioPieOption, PORTFOLIO_DIST_CHART_COLORS } from "./portfolioDistributionChart";
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
  const heroTitle = hasAssetData ? panel?.title : portfolioComparisonPanel?.title ?? "持仓 Tape";
  const heroMeta = panel?.meta ?? portfolioComparisonPanel?.meta ?? "";

  return (
    <section
      data-testid="module-home-portfolio-holdings-hero"
      className={`${dhStyles.dhCard} ${styles.holdingsHeroBand}`}
      data-tone={heroTone}
    >
      <div className={styles.holdingsHeroHead}>
        <div>
          <span className={styles.holdingsHeroKicker}>Holdings Tape</span>
          <strong>{heroTitle}</strong>
          <p className={styles.holdingsHeroMeta}>{heroMeta}</p>
        </div>
        <div className={styles.holdingsHeroActions}>
          {panel.viewAllPath ? (
            <Link className={styles.holdingsSectionLink} to={panel.viewAllPath}>
              债券总览
            </Link>
          ) : null}
          <Link className={styles.holdingsSectionLink} to="/positions">
            持仓透视
          </Link>
        </div>
      </div>

      {hasAssetData || hasPortfolioData ? (
        <div className={styles.holdingsHeroBody}>
          <div className={styles.holdingsHeroTableStack}>
            {hasAssetData ? (
              <div className={styles.holdingsHeroTableBlock}>
                <div className={styles.holdingsHeroTableTitle}>券种分布</div>
                <div className={styles.holdingsHeroTableWrap}>
                  <table className={styles.holdingsHeroTable}>
                    <thead>
                      <tr>
                        <th>券种</th>
                        <th>市值</th>
                        <th>占比</th>
                      </tr>
                    </thead>
                    <tbody>
                      {assetRows.map((row, index) => (
                        <tr key={row.key} data-testid={`module-home-portfolio-holdings-row-${row.key}`}>
                          <td>
                            <span
                              className={styles.holdingsHeroDot}
                              data-color-index={index % PORTFOLIO_DIST_CHART_COLORS.length}
                              aria-hidden="true"
                            />
                            <span title={row.label}>{row.label}</span>
                          </td>
                          <td className={styles.holdingsHeroNumeric}>{row.marketValue}</td>
                          <td className={styles.holdingsHeroNumeric}>
                            {row.share !== "-" ? row.share : `${row.barPct.toFixed(2)}%`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : panel ? (
              <p className={`${styles.holdingsHeroTableEmpty} ${toneClass(panel.tone)}`}>{panel.stateDetail}</p>
            ) : null}

            {portfolioComparisonPanel ? (
              <div className={styles.holdingsHeroTableBlock}>
                <div className={styles.holdingsHeroTableTitle}>
                  {portfolioComparisonPanel.title}
                  {portfolioComparisonPanel.stateLabel !== "已返回" ? (
                    <span className={styles.holdingsHeroTableState}>{portfolioComparisonPanel.stateLabel}</span>
                  ) : null}
                </div>
                {hasPortfolioData ? (
                  <div className={styles.holdingsHeroTableWrap}>
                    <table
                      className={styles.holdingsHeroTable}
                      data-testid="module-home-portfolio-comparison-hero-table"
                    >
                      <thead>
                        <tr>
                          <th>子组合</th>
                          <th>规模 / 久期 / YTM</th>
                          <th>DV01 / 只数</th>
                        </tr>
                      </thead>
                      <tbody>
                        {portfolioRows.map((row) => (
                          <tr
                            key={row.key}
                            data-testid={`module-home-portfolio-comparison-row-${row.key}`}
                          >
                            <td title={row.label}>{row.label}</td>
                            <td className={styles.holdingsHeroNumeric}>{row.value}</td>
                            <td className={styles.holdingsHeroNumeric}>{row.source ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className={`${styles.holdingsHeroTableEmpty} ${toneClass(portfolioComparisonPanel.tone)}`}>
                    {portfolioComparisonPanel.stateDetail}
                  </p>
                )}
              </div>
            ) : null}
          </div>

          <div className={styles.holdingsHeroChartCol}>
            {hasAssetData ? (
              <>
                <ReactECharts
                  option={buildPortfolioPieOption(assetRows)}
                  opts={{ renderer: "canvas" }}
                  notMerge
                  lazyUpdate
                  style={{ height: "220px", width: "100%" }}
                />
                <div className={styles.holdingsHeroChartCenter} aria-hidden="true">
                  <span>合计</span>
                  <strong>{panel?.totalDisplay ?? "—"}</strong>
                </div>
              </>
            ) : (
              <p className={`${styles.holdingsHeroChartEmpty} ${toneClass(heroTone)}`}>
                券种分布待返回；子组合读数见左侧表格。
              </p>
            )}
          </div>
        </div>
      ) : (
        <p className={`${styles.holdingsHeroEmpty} ${toneClass(heroTone)}`}>
          {panel?.stateDetail ?? portfolioComparisonPanel?.stateDetail ?? "持仓读数待返回。"}
        </p>
      )}
    </section>
  );
}
