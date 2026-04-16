import { useMemo } from "react";
import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

type MoneyRow = {
  key: string;
  name: string;
  ratePct: string;
  deltaBp: number;
  volume: number;
  weighted: string;
  range: string;
};

const DATA: MoneyRow[] = [
  { key: "r001", name: "R001", ratePct: "1.35%", deltaBp: -3.2, volume: 23421, weighted: "1.38", range: "1.32-1.42" },
  { key: "dr001", name: "DR001", ratePct: "1.30%", deltaBp: -3.5, volume: 18652, weighted: "1.32", range: "1.28-1.36" },
  { key: "dr007", name: "DR007", ratePct: "1.82%", deltaBp: 2.1, volume: 24331, weighted: "1.84", range: "1.78-1.88" },
  { key: "r007", name: "R007", ratePct: "1.55%", deltaBp: -3.0, volume: 6321, weighted: "1.54", range: "1.50-1.60" },
];

function deltaBpColor(bp: number) {
  if (bp < 0) {
    return "#2f8f63";
  }
  if (bp > 0) {
    return "#c0392b";
  }
  return "#31425b";
}

export function MoneyMarketTable() {
  const columns: ColumnsType<MoneyRow> = useMemo(
    () => [
      { title: "品种", dataIndex: "name", key: "name", width: 72 },
      { title: "利率%", dataIndex: "ratePct", key: "ratePct", align: "right", width: 80 },
      {
        title: "涨跌bp",
        dataIndex: "deltaBp",
        key: "deltaBp",
        align: "right",
        width: 88,
        render: (v: number) => (
          <span style={{ color: deltaBpColor(v), fontVariantNumeric: "tabular-nums" }}>
            {v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)}
          </span>
        ),
      },
      {
        title: "成交量",
        dataIndex: "volume",
        key: "volume",
        align: "right",
        render: (v: number) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{v.toLocaleString()}</span>,
      },
      { title: "加权", dataIndex: "weighted", key: "weighted", align: "right", width: 72 },
      { title: "区间", dataIndex: "range", key: "range", ellipsis: true },
    ],
    [],
  );

  return (
    <section data-testid="market-data-money-market-table" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>资金市场</h2>
      <Table<MoneyRow>
        size="small"
        pagination={false}
        columns={columns}
        dataSource={DATA}
        rowKey="key"
        scroll={{ x: true }}
      />
    </section>
  );
}
