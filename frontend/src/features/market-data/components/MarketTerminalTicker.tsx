import { tabularNumsStyle } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import type { MarketTerminalTickerItem } from "../lib/marketDataTerminalModel";
import { MarketTerminalSparkline } from "./MarketTerminalSparkline";

type MarketTerminalTickerProps = {
  items: MarketTerminalTickerItem[];
  basisLabel?: string;
  emptyReason?: string;
  compact?: boolean;
  statusDate?: string;
  statusLabel?: string;
};

export function MarketTerminalTicker({
  items,
  basisLabel,
  emptyReason,
  compact = false,
  statusDate,
  statusLabel = "正常",
}: MarketTerminalTickerProps) {
  if (items.length === 0) {
    return (
      <div
        data-testid="market-data-terminal-ticker-empty"
        className={`market-data-terminal-ticker-empty${compact ? " market-data-terminal-ticker-empty--compact" : ""}`}
      >
        {emptyReason ?? "正式利率读面暂无可用序列，前端不补示例行情。"}
      </div>
    );
  }

  return (
    <section
      data-testid="market-data-terminal-ticker"
      className={`market-data-terminal-ticker${compact ? " market-data-terminal-ticker--compact" : ""}`}
      aria-label="市场终端快讯"
    >
      {!compact ? (
        <div className="market-data-terminal-ticker-head">
          <span className="market-data-terminal-ticker-kicker">Market Tape</span>
          {basisLabel ? <span className="market-data-terminal-ticker-basis">{basisLabel}</span> : null}
        </div>
      ) : null}
      <div className="market-data-terminal-ticker-grid">
        {items.map((item) => (
          <div
            key={item.key}
            data-testid={`market-data-terminal-ticker-${item.key}`}
            className="market-data-terminal-ticker-cell"
          >
            <span className="market-data-terminal-ticker-label">{item.label}</span>
            <strong className="market-data-terminal-ticker-value" style={tabularNumsStyle}>
              {item.value}
            </strong>
            {!compact ? (
              item.sparklineValues.length >= 2 ? (
                <MarketTerminalSparkline
                  values={item.sparklineValues}
                  tone={item.tone}
                  variant="ticker"
                />
              ) : (
                <span className="market-data-terminal-ticker-sparkline-placeholder" aria-hidden />
              )
            ) : null}
            <span className="market-data-terminal-ticker-delta" data-tone={item.tone} style={tabularNumsStyle}>
              {item.delta}
            </span>
            {!compact ? <span className="market-data-terminal-ticker-date">{item.tradeDate}</span> : null}
          </div>
        ))}
        {compact ? (
          <div className="market-data-terminal-ticker-status" data-testid="market-data-terminal-ticker-status">
            <span>{statusDate ?? items[items.length - 1]?.tradeDate ?? EM_DASH}</span>
            <strong data-tone="ok">{statusLabel}</strong>
          </div>
        ) : null}
      </div>
    </section>
  );
}
