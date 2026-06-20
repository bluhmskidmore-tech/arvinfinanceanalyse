import { useMemo } from "react";
import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { designTokens } from "../../../theme/designSystem";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

type Row = {
  key: string;
  time: string;
  name: string;
  tenor: string;
  price: string;
  yieldPct: string;
  volume: string;
  side: "买入" | "卖出";
  rating: string;
};

const DATA: Row[] = [
  { key: "1", time: "10:30:12", name: "24 电网 MTN001", tenor: "2.85Y", price: "100.892", yieldPct: "2.42", volume: "2,100", side: "买入", rating: "AAA" },
  { key: "2", time: "10:29:55", name: "23 城投 07", tenor: "3.10Y", price: "99.765", yieldPct: "3.05", volume: "1,450", side: "卖出", rating: "AA+" },
  { key: "3", time: "10:29:21", name: "24 中化 SCP001", tenor: "0.45Y", price: "100.125", yieldPct: "2.18", volume: "5,600", side: "买入", rating: "AAA" },
  { key: "4", time: "10:28:47", name: "22 城建 MTN003", tenor: "4.22Y", price: "101.340", yieldPct: "3.28", volume: "980", side: "卖出", rating: "AA" },
  { key: "5", time: "10:28:05", name: "24 宝钢 MTN002", tenor: "2.98Y", price: "100.512", yieldPct: "2.65", volume: "3,200", side: "买入", rating: "AAA" },
  { key: "6", time: "10:27:38", name: "23 津投 CP002", tenor: "0.92Y", price: "99.890", yieldPct: "3.45", volume: "760", side: "卖出", rating: "AA" },
  { key: "7", time: "10:26:52", name: "24 华润 MTN001", tenor: "4.95Y", price: "102.015", yieldPct: "2.88", volume: "4,120", side: "买入", rating: "AAA" },
  { key: "8", time: "10:26:11", name: "23 苏交通 MTN005", tenor: "3.67Y", price: "101.228", yieldPct: "2.72", volume: "1,890", side: "卖出", rating: "AAA" },
];

const s = designTokens.space;

const sideStyle = (side: Row["side"]) =>
  side === "买入"
    ? { background: designTokens.color.danger[50], color: designTokens.color.danger[700] }
    : { background: designTokens.color.success[50], color: designTokens.color.success[600] };

export function CreditBondTradesTable() {
  const columns: ColumnsType<Row> = useMemo(
    () => [
      { title: "时间", dataIndex: "time", key: "time", width: 88 },
      { title: "债券简称", dataIndex: "name", key: "name", ellipsis: true },
      { title: "评级", dataIndex: "rating", key: "rating", width: 56 },
      { title: "期限", dataIndex: "tenor", key: "tenor", width: 72 },
      { title: "价格", dataIndex: "price", key: "price", align: "right", width: 80 },
      { title: "收益率%", dataIndex: "yieldPct", key: "yieldPct", align: "right", width: 80 },
      { title: "成交量", dataIndex: "volume", key: "volume", align: "right", width: 80 },
      {
        title: "方向",
        dataIndex: "side",
        key: "side",
        width: 72,
        render: (side: Row["side"]) => (
          <span
            style={{
              display: "inline-block",
              padding: `${s[1]}px ${s[2]}px`,
              borderRadius: designTokens.radius.sm,
              fontSize: designTokens.fontSize[12],
              fontWeight: 600,
              ...sideStyle(side),
            }}
          >
            {side}
          </span>
        ),
      },
    ],
    [],
  );

  return (
    <section data-testid="market-data-credit-bond-trades" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>信用债成交明细</h2>
      <div style={{ maxHeight: 320, overflow: "auto" }}>
        <Table<Row>
          size="small"
          pagination={false}
          columns={columns}
          dataSource={DATA}
          rowKey="key"
          scroll={{ x: true }}
        />
      </div>
    </section>
  );
}
