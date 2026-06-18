import type { MarketDataSourcePendingSection } from "../lib/marketDataTerminalModel";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

export function BondTradeDetail({ model: _model }: { model: MarketDataSourcePendingSection }) {
  return (
    <section data-testid="market-data-bond-trade-detail" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>债券成交明细（现券）</h2>
      <div
        data-testid="market-data-bond-trades-source-pending"
        className="market-data-terminal-pending-compact"
      >
        <span className="market-data-terminal-pending-compact__status">待接入</span>
        <span>现券成交明细源尚未纳入合同</span>
        <span className="market-data-terminal-pending-compact__contract" aria-hidden="true">
          待接入
        </span>
      </div>
    </section>
  );
}
