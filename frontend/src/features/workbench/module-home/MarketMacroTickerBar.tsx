import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { resolveMarketChangeDirection } from "./marketHomeChangeTone";
import { handleHorizontalScrollKeyboard } from "./marketHomeHorizontalScroll";
import { MarketHomeKpiSparkline } from "./MarketHomeKpiSparkline";
import type { ModuleHomeDetailPanel, ModuleHomeDetailRow } from "./moduleHomeModel";
import marketStyles from "./marketHome.module.css";

function tickerChangeClass(detail: string | undefined, sparkline: readonly number[] | undefined) {
  const direction = resolveMarketChangeDirection(detail, sparkline);
  if (direction === "up") return marketStyles.macroTickerChangeUp;
  if (direction === "down") return marketStyles.macroTickerChangeDown;
  return marketStyles.macroTickerChangeNeutral;
}

const TICKER_LIMIT = 7;
const TICKER_PRIORITY_KEYS = ["gov-10y", "dr007", "gov-1y", "gov-5y", "cdb-10y", "cdb-5y"] as const;

type MarketMacroTickerBarProps = {
  keyRatePanel?: ModuleHomeDetailPanel;
  macroPanel?: ModuleHomeDetailPanel;
};

function tickerRows(keyRatePanel?: ModuleHomeDetailPanel, macroPanel?: ModuleHomeDetailPanel): ModuleHomeDetailRow[] {
  const seen = new Set<string>();
  const rows: ModuleHomeDetailRow[] = [];
  const keyRateRows = keyRatePanel?.rows ?? [];
  const priorityRows = TICKER_PRIORITY_KEYS
    .map((key) => keyRateRows.find((row) => row.key === key))
    .filter((row): row is ModuleHomeDetailRow => Boolean(row));

  for (const row of priorityRows) {
    if (seen.has(row.key)) {
      continue;
    }
    seen.add(row.key);
    rows.push(row);
    if (rows.length >= TICKER_LIMIT) {
      return rows;
    }
  }

  for (const row of keyRateRows) {
    if (seen.has(row.key)) {
      continue;
    }
    seen.add(row.key);
    rows.push(row);
    if (rows.length >= TICKER_LIMIT) {
      return rows;
    }
  }

  for (const row of macroPanel?.rows ?? []) {
    if (seen.has(row.key)) {
      continue;
    }
    seen.add(row.key);
    rows.push(row);
    if (rows.length >= TICKER_LIMIT) {
      break;
    }
  }

  return rows;
}

export function MarketMacroTickerBar({ keyRatePanel, macroPanel }: MarketMacroTickerBarProps) {
  const rows = tickerRows(keyRatePanel, macroPanel);

  if (rows.length === 0) {
    return (
      <section className={marketStyles.macroTickerBar} data-testid="module-home-market-macro-ticker" aria-label="市场基准条">
        <p className={marketStyles.macroTickerEmpty}>暂无可用基准序列</p>
      </section>
    );
  }

  return (
    <section className={marketStyles.macroTickerBar} data-testid="module-home-market-macro-ticker" aria-label="市场基准条">
      <div className={marketStyles.macroTickerScrollBlock} data-testid="module-home-market-macro-ticker-scroll">
        <span className={marketStyles.macroTickerScrollHint}>滑动查看更多利率</span>
        <div
          aria-label="市场基准序列"
          className={marketStyles.macroTickerTrack}
          onKeyDown={handleHorizontalScrollKeyboard}
          role="region"
          tabIndex={0}
        >
        {rows.map((row) => {
          const changeDirection = resolveMarketChangeDirection(row.detail, row.sparkline);
          return (
            <div className={marketStyles.macroTickerCell} data-tone={row.tone} data-testid={`module-home-market-ticker-${row.key}`} key={row.key}>
              <span className={marketStyles.macroTickerLabel}>{row.label}</span>
              <div className={marketStyles.macroTickerValueRow}>
                <strong className={`${dhStyles.dhNum} ${marketStyles.marketMetricNum} ${marketStyles.macroTickerValue}`}>
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
              <small
                className={`${dhStyles.dhNum} ${marketStyles.marketMetricNum} ${marketStyles.macroTickerChange} ${tickerChangeClass(row.detail, row.sparkline)}`}
                data-change={changeDirection ?? "flat"}
              >
                {row.detail ?? "—"}
              </small>
            </div>
          );
        })}
        </div>
      </div>
    </section>
  );
}
