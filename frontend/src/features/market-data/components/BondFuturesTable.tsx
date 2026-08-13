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

const codeCell = (value: string) => <span className="market-data-obs-code">{value}</span>;
const nameCell = (value: string) => <span className="market-data-obs-name">{value}</span>;
const numCell = (value: string) => <span className="market-data-obs-num">{value}</span>;

// 变动列绿涨红跌走页面 data-tone 规则（--dh-api-green/red），禁止内联色值；持平/缺前值 muted。
const deltaCell = (value: string) => {
  const tone = value.startsWith("+") ? "up" : value.startsWith("-") ? "down" : "flat";
  return (
    <span className="market-data-obs-num market-data-obs-delta" data-tone={tone}>
      {value}
    </span>
  );
};

const columns: ColumnsType<MarketDataBondFuturesRow> = [
  { title: "合约", dataIndex: "contract", key: "contract", width: 76, render: codeCell },
  { title: "席位", dataIndex: "memberName", key: "memberName", ellipsis: true, render: nameCell },
  { title: "成交", dataIndex: "volumeText", key: "volumeText", align: "right", width: 84, render: numCell },
  { title: "成交变动", dataIndex: "volumeChangeText", key: "volumeChangeText", align: "right", width: 88, render: deltaCell },
  { title: "多单", dataIndex: "longHoldingText", key: "longHoldingText", align: "right", width: 84, render: numCell },
  { title: "空单", dataIndex: "shortHoldingText", key: "shortHoldingText", align: "right", width: 84, render: numCell },
  { title: "交易日", dataIndex: "tradeDate", key: "tradeDate", width: 104, render: codeCell },
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
          title={model.emptyReason}
        >
          <span className="market-data-terminal-pending-compact__status">未接入</span>
          <span>国债期货数据源未接入</span>
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
