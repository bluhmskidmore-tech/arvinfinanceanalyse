import { useMemo, useState } from "react";
import { Table, Tabs } from "antd";
import type { ColumnsType } from "antd/es/table";

import { designTokens } from "../../../theme/designSystem";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

type TabKey = "interbank" | "main";

type FutureRow = {
  key: string;
  contract: string;
  price: string;
  change: string;
  changePct: string;
  volume: string;
  openInterest: string;
};

const INTERBANK: FutureRow[] = [
  { key: "i1", contract: "T2409", price: "103.245", change: "+0.105", changePct: "+0.10%", volume: "156.7万", openInterest: "12.4万" },
  { key: "i2", contract: "TF2409", price: "101.560", change: "+0.070", changePct: "+0.07%", volume: "89.2万", openInterest: "8.1万" },
  { key: "i3", contract: "TS2409", price: "99.245", change: "+0.025", changePct: "+0.03%", volume: "42.5万", openInterest: "5.6万" },
  { key: "i4", contract: "TL2409", price: "110.875", change: "+0.060", changePct: "+0.05%", volume: "63.8万", openInterest: "7.2万" },
];

const MAIN: FutureRow[] = [
  { key: "m1", contract: "T主力", price: "103.198", change: "+0.098", changePct: "+0.09%", volume: "402.1万", openInterest: "28.9万" },
  { key: "m2", contract: "TF主力", price: "101.512", change: "+0.055", changePct: "+0.05%", volume: "256.4万", openInterest: "19.3万" },
  { key: "m3", contract: "TS主力", price: "99.221", change: "+0.018", changePct: "+0.02%", volume: "118.7万", openInterest: "14.2万" },
  { key: "m4", contract: "TL主力", price: "110.840", change: "+0.052", changePct: "+0.05%", volume: "201.5万", openInterest: "22.1万" },
];

export function BondFuturesTable() {
  const [tab, setTab] = useState<TabKey>("interbank");
  const dataSource = tab === "interbank" ? INTERBANK : MAIN;

  const columns: ColumnsType<FutureRow> = useMemo(
    () => [
      { title: "合约", dataIndex: "contract", key: "contract", width: 88 },
      { title: "价格", dataIndex: "price", key: "price", align: "right" },
      {
        title: "涨跌",
        dataIndex: "change",
        key: "change",
        align: "right",
        render: (v: string) => (
          <span
            style={{
              color: v.startsWith("-")
                ? designTokens.color.semantic.profit
                : designTokens.color.semantic.loss,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {v}
          </span>
        ),
      },
      {
        title: "涨跌幅%",
        dataIndex: "changePct",
        key: "changePct",
        align: "right",
        render: (v: string) => (
          <span
            style={{
              color: v.startsWith("-")
                ? designTokens.color.semantic.profit
                : designTokens.color.semantic.loss,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {v}
          </span>
        ),
      },
      { title: "成交量", dataIndex: "volume", key: "volume", align: "right" },
      { title: "持仓量", dataIndex: "openInterest", key: "openInterest", align: "right" },
    ],
    [],
  );

  return (
    <section data-testid="market-data-bond-futures-table" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>国债期货</h2>
      <Tabs
        size="small"
        activeKey={tab}
        onChange={(k) => setTab(k as TabKey)}
        items={[
          { key: "interbank", label: "银行间" },
          { key: "main", label: "主力合约" },
        ]}
      />
      <Table<FutureRow>
        size="small"
        pagination={false}
        columns={columns}
        dataSource={dataSource}
        rowKey="key"
        scroll={{ x: true }}
      />
    </section>
  );
}
