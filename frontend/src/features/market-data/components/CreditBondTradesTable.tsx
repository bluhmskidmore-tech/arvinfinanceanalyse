import type { MarketDataSourcePendingSection } from "../lib/marketDataTerminalModel";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

export function CreditBondTradesTable({ model }: { model: MarketDataSourcePendingSection }) {
  return (
    <section data-testid="market-data-credit-bond-trades" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>信用债成交明细</h2>
      <div
        data-testid="market-data-credit-trades-source-pending"
        className="market-data-terminal-empty"
      >
        <span className="market-data-terminal-empty__status">{model.status}</span>
        <span>{model.emptyReason}</span>
      </div>
    </section>
  );
}
