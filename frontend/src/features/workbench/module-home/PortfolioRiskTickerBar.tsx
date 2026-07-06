import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { resolveMarketChangeDirection } from "./marketHomeChangeTone";
import { MarketHomeKpiSparkline } from "./MarketHomeKpiSparkline";
import type { ModuleHomeDetailPanel } from "./moduleHomeModel";
import styles from "./portfolioHome.module.css";

const TICKER_LIMIT = 7;

type PortfolioRiskTickerBarProps = {
  riskPanel?: ModuleHomeDetailPanel;
  unavailable?: boolean;
  unavailableTitle?: string;
  unavailableDetail?: string;
};

function tickerChangeClass(detail: string | undefined, sparkline: readonly number[] | undefined) {
  const direction = resolveMarketChangeDirection(detail, sparkline);
  if (direction === "up") return dhStyles.dhUpRed;
  if (direction === "down") return dhStyles.dhDownGreen;
  return styles.portfolioRiskTickerChangeNeutral;
}

export function PortfolioRiskTickerBar({
  riskPanel,
  unavailable = false,
  unavailableTitle,
  unavailableDetail,
}: PortfolioRiskTickerBarProps) {
  const rows = riskPanel?.rows.slice(0, TICKER_LIMIT) ?? [];

  if (unavailable || rows.length === 0) {
    return (
      <section
        className={`${styles.portfolioRiskTickerBar} ${unavailable ? styles.portfolioRiskTickerUnavailable : ""}`}
        data-testid="module-home-portfolio-risk-ticker"
        aria-label="组合风险指标条"
      >
        <div className={styles.portfolioRiskTickerHead}>
          <span>风险口径</span>
          <strong>{unavailable ? unavailableTitle ?? "风险读数不可用" : "风险读数待返回"}</strong>
        </div>
        <p className={styles.portfolioRiskTickerEmpty}>
          {unavailable
            ? unavailableDetail ?? "风险链路未通过正式闭合校验，不构成实时风险判断。"
            : "风险指标待返回"}
        </p>
      </section>
    );
  }

  return (
    <section
      className={styles.portfolioRiskTickerBar}
      data-testid="module-home-portfolio-risk-ticker"
      aria-label="组合风险指标条"
    >
      <div className={styles.portfolioRiskTickerHead}>
        <span>风险口径</span>
        <strong>风险读数</strong>
      </div>
      <div className={styles.portfolioRiskTickerTrack}>
        {rows.map((row) => {
          const changeDirection = resolveMarketChangeDirection(row.detail, row.sparkline);
          return (
            <div
              className={styles.portfolioRiskTickerCell}
              data-tone={row.tone}
              data-testid={`module-home-portfolio-ticker-${row.key}`}
              key={row.key}
            >
              <span className={styles.portfolioRiskTickerLabel}>{row.label}</span>
              <div className={styles.portfolioRiskTickerValueRow}>
                <strong className={`${dhStyles.dhNum} ${styles.portfolioRiskTickerValue}`}>
                  {row.value}
                </strong>
                {row.sparkline && row.sparkline.length >= 2 ? (
                  <MarketHomeKpiSparkline
                    values={row.sparkline}
                    tone={row.tone}
                    changeDirection={changeDirection}
                    variant="ticker"
                  />
                ) : null}
              </div>
              <em
                className={`${dhStyles.dhNum} ${styles.portfolioRiskTickerChange} ${tickerChangeClass(
                  row.detail,
                  row.sparkline,
                )}`}
                data-change={changeDirection ?? "flat"}
              >
                {row.source ?? row.detail ?? "—"}
              </em>
            </div>
          );
        })}
      </div>
    </section>
  );
}
