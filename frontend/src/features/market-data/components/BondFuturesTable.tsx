import type { MarketDataSourcePendingSection } from "../lib/marketDataTerminalModel";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

export function BondFuturesTable({ model }: { model: MarketDataSourcePendingSection }) {
  return (
    <section data-testid="market-data-bond-futures-table" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>国债期货</h2>
      <div
        data-testid="market-data-bond-futures-source-pending"
        className="market-data-terminal-empty"
      >
        <span className="market-data-terminal-empty__status">{model.status}</span>
        <span>{model.emptyReason}</span>
      </div>
    </section>
  );
}
