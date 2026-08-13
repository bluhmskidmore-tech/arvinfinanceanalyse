import type { MarketDataSourcePendingSection } from "../lib/marketDataTerminalModel";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

export function BondTradeDetail({ model }: { model: MarketDataSourcePendingSection }) {
  return (
    <section data-testid="market-data-bond-trade-detail" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>债券成交明细（现券）</h2>
      <div
        data-testid="market-data-bond-trades-source-pending"
        className="market-data-terminal-pending-compact"
        title={model.emptyReason}
      >
        <span className="market-data-terminal-pending-compact__status">未接入</span>
        <span>现券成交数据源未接入</span>
      </div>
    </section>
  );
}
