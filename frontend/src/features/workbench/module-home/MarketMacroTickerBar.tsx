import type { ReactNode } from "react";

import dhStyles from "../dashboard-home/dashboardHome.module.css";
import { resolveMarketChangeDirection } from "./marketHomeChangeTone";
import type { ModuleHomeDetailPanel, ModuleHomeDetailRow } from "./moduleHomeModel";
import { MarketHomeKpiSparkline } from "./MarketHomeKpiSparkline";
import marketStyles from "./marketHome.module.css";

function tickerChangeClass(detail: string | undefined, sparkline: readonly number[] | undefined) {
  const direction = resolveMarketChangeDirection(detail, sparkline);
  if (direction === "up") return marketStyles.macroTickerChangeUp;
  if (direction === "down") return marketStyles.macroTickerChangeDown;
  return marketStyles.macroTickerChangeNeutral;
}

const TICKER_CELL_LIMIT = 16;
const TICKER_PRIORITY_KEYS = [
  "gov-10y",
  "gov-2y",
  "gov-5y",
  "gov-7y",
  "gov-30y",
  "gov-1y",
  "gov-3y",
  "dr007",
  "r007",
  "shibor-on",
  "cdb-10y",
  "cdb-5y",
  "omo-7d",
  "ncd-3m",
  "aa-5y",
] as const;

function isSpreadTickerRow(row: ModuleHomeDetailRow) {
  return row.key.startsWith("term-spread-");
}

type MarketMacroTickerBarProps = {
  keyRatePanel?: ModuleHomeDetailPanel;
  macroPanel?: ModuleHomeDetailPanel;
  macroOverviewPanel?: ModuleHomeDetailPanel;
};

function macroStanceRow(panel?: ModuleHomeDetailPanel): ModuleHomeDetailRow | undefined {
  if (!panel) {
    return undefined;
  }
  return (
    panel.rows.find((row) => row.key === "macro-stance") ??
    panel.rows.find((row) => row.key.includes("stance") || row.label.includes("立场")) ??
    panel.rows[0]
  );
}

function csiRow(macroPanel?: ModuleHomeDetailPanel): ModuleHomeDetailRow | undefined {
  return macroPanel?.rows.find(
    (row) =>
      row.label.includes("沪深300") ||
      row.label.includes("CSI300") ||
      row.key.includes("csi300") ||
      row.key.includes("hs300"),
  );
}

function offshoreRow(macroPanel?: ModuleHomeDetailPanel): ModuleHomeDetailRow | undefined {
  return macroPanel?.rows.find(
    (row) =>
      row.label.includes("USD/CNY") ||
      row.label.includes("USDCNY") ||
      row.label.includes("汇率") ||
      row.label.includes("Brent") ||
      row.label.includes("原油"),
  );
}

type TickerGroup = "rates" | "cross" | "stance";

type TickerEntry = {
  row: ModuleHomeDetailRow;
  group: TickerGroup;
};

const TICKER_GROUP_LABELS: Record<TickerGroup, string> = {
  rates: "利率",
  cross: "跨资产",
  stance: "立场",
};

const TICKER_GROUP_ORDER: Record<TickerGroup, number> = {
  rates: 0,
  cross: 1,
  stance: 2,
};

function tickerEntries(
  keyRatePanel?: ModuleHomeDetailPanel,
  macroPanel?: ModuleHomeDetailPanel,
  macroOverviewPanel?: ModuleHomeDetailPanel,
): TickerEntry[] {
  const seen = new Set<string>();
  const entries: TickerEntry[] = [];
  const keyRateRows = keyRatePanel?.rows ?? [];
  const macroRows = macroPanel?.rows ?? [];

  function pushRow(row: ModuleHomeDetailRow | undefined, group: TickerGroup) {
    if (!row || seen.has(row.key) || isSpreadTickerRow(row) || entries.length >= TICKER_CELL_LIMIT) {
      return;
    }
    seen.add(row.key);
    entries.push({ row, group });
  }

  for (const key of TICKER_PRIORITY_KEYS) {
    pushRow(keyRateRows.find((row) => row.key === key), "rates");
  }

  pushRow(csiRow(macroPanel), "cross");
  pushRow(offshoreRow(macroPanel), "cross");
  pushRow(macroStanceRow(macroOverviewPanel), "stance");

  for (const row of keyRateRows) {
    pushRow(row, "rates");
  }

  for (const row of macroRows) {
    pushRow(row, "cross");
  }

  // 同一组只出现一段：收集顺序里 rates/cross 会交错两次，渲染前按组稳定归并，
  // 保证分组标签每组至多一枚（sort 为稳定排序，组内保持收集顺序）。
  return entries.sort((a, b) => TICKER_GROUP_ORDER[a.group] - TICKER_GROUP_ORDER[b.group]);
}

export function MarketMacroTickerBar({
  keyRatePanel,
  macroPanel,
  macroOverviewPanel,
}: MarketMacroTickerBarProps) {
  const entries = tickerEntries(keyRatePanel, macroPanel, macroOverviewPanel);

  if (entries.length === 0) {
    return (
      <section className={marketStyles.macroTickerBar} data-testid="module-home-market-macro-ticker" aria-label="宏观监控条">
        <p className={marketStyles.macroTickerEmpty}>暂无可用基准序列</p>
      </section>
    );
  }

  const cells: ReactNode[] = [];
  let lastGroup: TickerGroup | null = null;
  let groupRunIndex = 0;
  for (const entry of entries) {
    if (entry.group !== lastGroup) {
      groupRunIndex += 1;
      cells.push(
        <span
          className={marketStyles.macroTickerGroupChip}
          aria-hidden="true"
          key={`group-${entry.group}-${groupRunIndex}`}
        >
          {TICKER_GROUP_LABELS[entry.group]}
        </span>,
      );
      lastGroup = entry.group;
    }
    const row = entry.row;
    const changeDirection = resolveMarketChangeDirection(row.detail, row.sparkline);
    const dateLabel = row.tradeDate && row.tradeDate !== "-" ? row.tradeDate : null;
    cells.push(
      <div
        className={marketStyles.macroTickerCell}
        data-tone={row.tone}
        data-testid={`module-home-market-ticker-${row.key}`}
        key={row.key}
      >
        <span className={marketStyles.macroTickerLabel}>{row.label}</span>
        <div className={marketStyles.macroTickerValueRow}>
          <strong className={`${dhStyles.dhNum} ${marketStyles.marketMetricNum} ${marketStyles.macroTickerValue}`}>
            {row.value === "缺省值" || !row.value ? <span className={marketStyles.macroTickerMissing}>--</span> : row.value}
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
          {row.detail === "缺省值" || !row.detail ? "--" : row.detail}
        </small>
        {dateLabel ? <span className={marketStyles.macroTickerDate}>{dateLabel}</span> : null}
      </div>,
    );
  }

  return (
    <section className={marketStyles.macroTickerBar} data-testid="module-home-market-macro-ticker" aria-label="宏观监控条">
      <div className={marketStyles.macroTickerScrollBlock} data-testid="module-home-market-macro-ticker-scroll">
        <div
          aria-label="宏观监控序列"
          className={marketStyles.macroTickerTrack}
          data-testid="module-home-market-macro-ticker-grid"
          role="region"
          tabIndex={0}
        >
          {cells}
        </div>
      </div>
    </section>
  );
}
