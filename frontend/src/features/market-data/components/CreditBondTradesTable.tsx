import type { MarketDataSourcePendingSection } from "../lib/marketDataTerminalModel";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

export function CreditBondTradesTable({ model }: { model: MarketDataSourcePendingSection }) {
  return (
    <section data-testid="market-data-credit-bond-trades" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>信用债成交明细</h2>
      <div
        data-testid="market-data-credit-trades-source-pending"
        className="market-data-terminal-pending-compact"
        title={model.emptyReason}
      >
        <span className="market-data-terminal-pending-compact__status">未接入</span>
        <span>信用债成交数据源未接入</span>
      </div>
    </section>
  );
}
