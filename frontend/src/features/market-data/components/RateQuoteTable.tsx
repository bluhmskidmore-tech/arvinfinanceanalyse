import { useMemo, useState } from "react";
import { Table, Tabs } from "antd";
import type { ColumnsType } from "antd/es/table";

import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

type CurveKind = "treasury" | "cdb";

type RateQuoteRow = {
  key: string;
  variety: string;
  tenor: string;
  ratePct: string;
  deltaBp: number;
  volume: number;
  range: string;
};

const TREASURY_ROWS: RateQuoteRow[] = [
  { key: "t1", variety: "国债", tenor: "1Y", ratePct: "1.78%", deltaBp: -2.0, volume: 1245, range: "1.76-1.80" },
  { key: "t2", variety: "国债", tenor: "3Y", ratePct: "1.95%", deltaBp: -1.8, volume: 2163, range: "1.93-1.99" },
  { key: "t3", variety: "国债", tenor: "5Y", ratePct: "2.15%", deltaBp: -1.5, volume: 3512, range: "2.13-2.18" },
  { key: "t4", variety: "国债", tenor: "7Y", ratePct: "2.08%", deltaBp: -1.3, volume: 2890, range: "2.06-2.11" },
  { key: "t5", variety: "国债", tenor: "10Y", ratePct: "1.94%", deltaBp: -1.2, volume: 4856, range: "1.92-1.96" },
];

const CDB_ROWS: RateQuoteRow[] = [
  { key: "c1", variety: "国开", tenor: "1Y", ratePct: "1.85%", deltaBp: -1.5, volume: 842, range: "1.83-1.87" },
  { key: "c2", variety: "国开", tenor: "3Y", ratePct: "2.02%", deltaBp: -1.4, volume: 1532, range: "2.00-2.05" },
  { key: "c3", variety: "国开", tenor: "5Y", ratePct: "2.18%", deltaBp: -1.2, volume: 2988, range: "2.16-2.21" },
  { key: "c4", variety: "国开", tenor: "7Y", ratePct: "2.12%", deltaBp: -1.0, volume: 1766, range: "2.10-2.15" },
  { key: "c5", variety: "国开", tenor: "10Y", ratePct: "2.05%", deltaBp: -0.9, volume: 4102, range: "2.03-2.08" },
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

export function RateQuoteTable() {
  const [curve, setCurve] = useState<CurveKind>("treasury");
  const dataSource = curve === "treasury" ? TREASURY_ROWS : CDB_ROWS;

  const columns: ColumnsType<RateQuoteRow> = useMemo(
    () => [
      { title: "品种", dataIndex: "variety", key: "variety", width: 72 },
      { title: "期限", dataIndex: "tenor", key: "tenor", width: 56 },
      { title: "利率%", dataIndex: "ratePct", key: "ratePct", align: "right", width: 88 },
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
      { title: "区间", dataIndex: "range", key: "range", ellipsis: true },
    ],
    [],
  );

  return (
    <section data-testid="market-data-rate-quote-table" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>利率行情</h2>
      <Tabs
        size="small"
        activeKey={curve}
        onChange={(k) => setCurve(k as CurveKind)}
        items={[
          { key: "treasury", label: "国债" },
          { key: "cdb", label: "国开" },
        ]}
      />
      <Table<RateQuoteRow>
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
