import { tabularNumsStyle } from "../../../theme/designSystem";
import type { MarketTerminalTickerItem } from "../lib/marketDataTerminalModel";
import { MarketTerminalSparkline } from "./MarketTerminalSparkline";

type MarketTerminalTickerProps = {
  items: MarketTerminalTickerItem[];
  basisLabel?: string;
  emptyReason?: string;
};

export function MarketTerminalTicker({ items, basisLabel, emptyReason }: MarketTerminalTickerProps) {
  if (items.length === 0) {
    return (
      <div data-testid="market-data-terminal-ticker-empty" className="market-data-terminal-ticker-empty">
        {emptyReason ?? "正式利率读面暂无可用序列，前端不补示例行情。"}
      </div>
    );
  }

  return (
    <section
      data-testid="market-data-terminal-ticker"
      className="market-data-terminal-ticker"
      aria-label="市场终端快讯"
    >
      <div className="market-data-terminal-ticker-head">
        <span className="market-data-terminal-ticker-kicker">Market Tape</span>
        {basisLabel ? <span className="market-data-terminal-ticker-basis">{basisLabel}</span> : null}
      </div>
      <div className="market-data-terminal-ticker-grid">
        {items.map((item, index) => (
          <div
            key={item.key}
            data-testid={`market-data-terminal-ticker-${item.key}`}
            className="market-data-terminal-ticker-cell"
          >
            <span className="market-data-terminal-ticker-label">{item.label}</span>
            <strong className="market-data-terminal-ticker-value" style={tabularNumsStyle}>
              {item.value}
            </strong>
            {item.sparklineValues.length >= 2 ? (
              <MarketTerminalSparkline
                values={item.sparklineValues}
                tone={item.tone}
                variant="ticker"
              />
            ) : (
              <span className="market-data-terminal-ticker-sparkline-placeholder" aria-hidden />
            )}
            <span className="market-data-terminal-ticker-delta" data-tone={item.tone} style={tabularNumsStyle}>
              {item.delta}
            </span>
            <span className="market-data-terminal-ticker-date">{item.tradeDate}</span>
            {index < items.length - 1 ? <span className="market-data-terminal-ticker-rule" aria-hidden /> : null}
          </div>
        ))}
      </div>
    </section>
  );
}
