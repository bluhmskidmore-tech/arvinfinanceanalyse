import { useMemo, useState } from "react";
import { Table, Tabs } from "antd";
import type { ColumnsType } from "antd/es/table";

import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

type TabKey = "main" | "cash";

type TradeRow = {
  key: string;
  time: string;
  name: string;
  tenor: string;
  price: string;
  yieldPct: string;
  volume: string;
  side: "买入" | "卖出";
};

const MAIN_ROWS: TradeRow[] = [
  { key: "m1", time: "10:29:51", name: "T2409", tenor: "标准合约", price: "103.245", yieldPct: "—", volume: "1,256", side: "买入" },
  { key: "m2", time: "10:29:32", name: "TF2409", tenor: "标准合约", price: "101.560", yieldPct: "—", volume: "892", side: "卖出" },
  { key: "m3", time: "10:28:15", name: "TS2409", tenor: "标准合约", price: "99.248", yieldPct: "—", volume: "445", side: "买入" },
  { key: "m4", time: "10:27:03", name: "TL2409", tenor: "标准合约", price: "110.880", yieldPct: "—", volume: "2,103", side: "买入" },
  { key: "m5", time: "10:26:41", name: "T2409", tenor: "标准合约", price: "103.220", yieldPct: "—", volume: "678", side: "卖出" },
];

const CASH_ROWS: TradeRow[] = [
  { key: "c1", time: "10:29:51", name: "23 国债 05", tenor: "9.76Y", price: "102.356", yieldPct: "1.943", volume: "5,200", side: "买入" },
  { key: "c2", time: "10:29:32", name: "24 国开 03", tenor: "2.76Y", price: "100.560", yieldPct: "2.050", volume: "3,100", side: "卖出" },
  { key: "c3", time: "10:28:58", name: "23 附息国债 18", tenor: "4.52Y", price: "101.125", yieldPct: "2.015", volume: "2,800", side: "买入" },
  { key: "c4", time: "10:28:12", name: "24 国开 10", tenor: "9.92Y", price: "102.890", yieldPct: "2.128", volume: "4,560", side: "卖出" },
  { key: "c5", time: "10:27:44", name: "22 国债 17", tenor: "7.35Y", price: "103.012", yieldPct: "2.088", volume: "1,920", side: "买入" },
  { key: "c6", time: "10:27:01", name: "23 国开 15", tenor: "5.08Y", price: "101.445", yieldPct: "2.232", volume: "6,700", side: "买入" },
  { key: "c7", time: "10:26:33", name: "24 国债 02", tenor: "2.15Y", price: "100.285", yieldPct: "1.892", volume: "890", side: "卖出" },
  { key: "c8", time: "10:25:19", name: "21 国开 08", tenor: "8.40Y", price: "104.100", yieldPct: "2.305", volume: "3,400", side: "卖出" },
];

const sideStyle = (side: TradeRow["side"]) =>
  side === "买入"
    ? { background: "#fff0f0", color: "#a02626" }
    : { background: "#edf8f2", color: "#1f6b45" };

export function BondTradeDetail() {
  const [tab, setTab] = useState<TabKey>("cash");
  const dataSource = tab === "main" ? MAIN_ROWS : CASH_ROWS;

  const columns: ColumnsType<TradeRow> = useMemo(
    () => [
      { title: "时间", dataIndex: "time", key: "time", width: 88 },
      { title: "债券简称", dataIndex: "name", key: "name", ellipsis: true },
      { title: "期限", dataIndex: "tenor", key: "tenor", width: 88 },
      { title: "价格", dataIndex: "price", key: "price", align: "right", width: 88 },
      { title: "收益率%", dataIndex: "yieldPct", key: "yieldPct", align: "right", width: 88 },
      { title: "成交量", dataIndex: "volume", key: "volume", align: "right", width: 88 },
      {
        title: "方向",
        dataIndex: "side",
        key: "side",
        width: 72,
        render: (side: TradeRow["side"]) => (
          <span
            style={{
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: 6,
              fontSize: 12,
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
    <section data-testid="market-data-bond-trade-detail" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>债券成交明细（现券）</h2>
      <Tabs
        size="small"
        activeKey={tab}
        onChange={(k) => setTab(k as TabKey)}
        items={[
          { key: "main", label: "主力合约" },
          { key: "cash", label: "现券" },
        ]}
      />
      <div style={{ maxHeight: 320, overflow: "auto" }}>
        <Table<TradeRow>
          size="small"
          pagination={false}
          columns={columns}
          dataSource={dataSource}
          rowKey="key"
          scroll={{ x: true }}
        />
      </div>
    </section>
  );
}
