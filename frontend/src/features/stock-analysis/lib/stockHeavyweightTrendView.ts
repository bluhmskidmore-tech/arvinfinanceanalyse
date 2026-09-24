import type {
  StockHeavyweightTrendStock,
  StockHeavyweightTrendsPayload,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import type { StockAnalysisTrendSparklineTone } from "../components/StockAnalysisTrendSparkline";

export type StockHeavyweightTrendRow = {
  /** Backend cumulative percent series relative to the first observed close. */
  values: number[];
  tone: StockAnalysisTrendSparklineTone;
  /** Hover text for the row; also carries the reason when the line cannot be drawn. */
  title: string;
  /** Formatted window return, or EM_DASH when the backend has no usable series. */
  returnLabel: string;
  plottable: boolean;
};

export type StockHeavyweightTrendIndex = {
  byStockCode: Map<string, StockHeavyweightTrendRow>;
  windowLabel: string | null;
  sessionCount: number;
};

const EMPTY_INDEX: StockHeavyweightTrendIndex = {
  byStockCode: new Map(),
  windowLabel: null,
  sessionCount: 0,
};

const TREND_STATE_REASONS: Record<string, string> = {
  missing: "该股在窗口内无可交易收盘价",
  insufficient: "该股窗口内仅 1 个交易日，不足以画走势",
};

function resolveTone(stock: StockHeavyweightTrendStock): StockAnalysisTrendSparklineTone {
  const windowReturn = stock.window_return_pct;
  if (windowReturn == null || !Number.isFinite(windowReturn) || windowReturn === 0) {
    return "neutral";
  }
  return windowReturn > 0 ? "positive" : "negative";
}

function formatWindowReturn(value: number | null): string {
  if (value == null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function buildTitle(
  stock: StockHeavyweightTrendStock,
  windowLabel: string | null,
  plottable: boolean,
): string {
  const scope = windowLabel ? `${windowLabel} · ` : "";
  if (!plottable) {
    const reason = TREND_STATE_REASONS[stock.trend_state] ?? "该股走势数据缺失";
    return `${scope}${reason}`;
  }
  const sessions = `${stock.point_count} 个交易日`;
  const gap =
    stock.missing_point_count > 0 ? ` · 停牌缺 ${stock.missing_point_count} 日` : "";
  return `${scope}${sessions}${gap} · 区间 ${formatWindowReturn(stock.window_return_pct)}`;
}

/**
 * Flatten the heavyweight-trends payload into a stock-code lookup the card can
 * read per row. Rows without a usable series stay in the map with
 * ``plottable: false`` so the component can degrade quietly instead of guessing.
 */
export function buildHeavyweightTrendIndex(
  payload: StockHeavyweightTrendsPayload | null | undefined,
): StockHeavyweightTrendIndex {
  if (!payload || payload.state !== "ok") {
    return EMPTY_INDEX;
  }
  const dates = payload.window_trade_dates ?? [];
  const windowLabel =
    dates.length > 0 ? `${dates[0]} 至 ${dates[dates.length - 1]}` : null;

  const byStockCode = new Map<string, StockHeavyweightTrendRow>();
  for (const sector of payload.sectors ?? []) {
    for (const stock of sector.stocks ?? []) {
      const values = (stock.cum_pct_changes ?? []).filter((value) => Number.isFinite(value));
      const plottable = values.length >= 2;
      byStockCode.set(stock.stock_code, {
        values,
        tone: resolveTone(stock),
        title: buildTitle(stock, windowLabel, plottable),
        returnLabel: plottable ? formatWindowReturn(stock.window_return_pct) : EM_DASH,
        plottable,
      });
    }
  }
  return { byStockCode, windowLabel, sessionCount: dates.length };
}
