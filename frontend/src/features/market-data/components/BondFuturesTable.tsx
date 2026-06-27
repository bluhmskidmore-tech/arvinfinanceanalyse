import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type {
  MarketDataBondFuturesRow,
  MarketDataBondFuturesSection,
  MarketDataSourcePendingSection,
} from "../lib/marketDataTerminalModel";
import { formatTerminalSourceSummary } from "../lib/marketDataTerminalModel";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

type BondFuturesModel = MarketDataBondFuturesSection | MarketDataSourcePendingSection;

const columns: ColumnsType<MarketDataBondFuturesRow> = [
  { title: "合约", dataIndex: "contract", key: "contract", width: 76 },
  { title: "席位", dataIndex: "memberName", key: "memberName", ellipsis: true },
  { title: "成交", dataIndex: "volumeText", key: "volumeText", align: "right", width: 84 },
  { title: "成交变动", dataIndex: "volumeChangeText", key: "volumeChangeText", align: "right", width: 88 },
  { title: "多单", dataIndex: "longHoldingText", key: "longHoldingText", align: "right", width: 84 },
  { title: "空单", dataIndex: "shortHoldingText", key: "shortHoldingText", align: "right", width: 84 },
  { title: "交易日", dataIndex: "tradeDate", key: "tradeDate", width: 104 },
];

function isPending(model: BondFuturesModel): model is MarketDataSourcePendingSection {
  return model.status === "source-pending";
}

export function BondFuturesTable({ model }: { model: BondFuturesModel }) {
  return (
    <section data-testid="market-data-bond-futures-table" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>国债期货</h2>
      {isPending(model) ? (
        <div
          data-testid="market-data-bond-futures-source-pending"
          className="market-data-terminal-pending-compact"
        >
          <span className="market-data-terminal-pending-compact__status">未接入</span>
          <span>国债期货行情源尚未纳入合同</span>
          <span className="market-data-terminal-pending-compact__contract" aria-hidden="true">
            未接入
          </span>
        </div>
      ) : (
        <>
          <p className="market-data-terminal-source">
            {formatTerminalSourceSummary(model.source)}
            {model.asOfDate ? ` · ${model.contract} · ${model.asOfDate}` : ` · ${model.contract}`}
          </p>
          {model.status === "ready" ? (
            <Table<MarketDataBondFuturesRow>
              size="small"
              pagination={false}
              columns={columns}
              dataSource={model.rows}
              rowKey="key"
              scroll={{ x: true }}
            />
          ) : (
            <div data-testid="market-data-bond-futures-empty" className="market-data-terminal-empty">
              {model.emptyReason}
            </div>
          )}
        </>
      )}
    </section>
  );
}
