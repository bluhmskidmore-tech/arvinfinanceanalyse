import type { MarketDataSourcePendingSection } from "../lib/marketDataTerminalModel";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

export function BondTradeDetail({ model }: { model: MarketDataSourcePendingSection }) {
  return (
    <section data-testid="market-data-bond-trade-detail" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>债券成交明细（现券）</h2>
      <div
        data-testid="market-data-bond-trades-source-pending"
        className="market-data-terminal-empty"
      >
        <span className="market-data-terminal-empty__status">{model.status}</span>
        <span>{model.emptyReason}</span>
      </div>
    </section>
  );
}
