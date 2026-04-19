import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { SectionCard } from "../../../components/SectionCard";
import { BORDER, panelStyle } from "./bondAnalyticsCockpitTokens";

type Row = {
  key: string;
  name: string;
  scaleYi: string;
  yieldPct: string;
  excessBp: string;
  durationY: string;
  maxDdPct: string;
};

const DATA: Row[] = [
  {
    key: "1",
    name: "利率债组合",
    scaleYi: "1,256.34",
    yieldPct: "1.85",
    excessBp: "+23",
    durationY: "4.12",
    maxDdPct: "-1.32",
  },
  {
    key: "2",
    name: "信用债组合",
    scaleYi: "1,152.76",
    yieldPct: "2.65",
    excessBp: "+45",
    durationY: "2.87",
    maxDdPct: "-0.85",
  },
  {
    key: "3",
    name: "同业存单组合",
    scaleYi: "589.36",
    yieldPct: "1.72",
    excessBp: "+15",
    durationY: "0.08",
    maxDdPct: "-0.02",
  },
  {
    key: "4",
    name: "地方债组合",
    scaleYi: "403.21",
    yieldPct: "2.12",
    excessBp: "+32",
    durationY: "3.15",
    maxDdPct: "-1.05",
  },
  {
    key: "5",
    name: "高等级组合",
    scaleYi: "1,842.13",
    yieldPct: "2.05",
    excessBp: "+28",
    durationY: "2.95",
    maxDdPct: "-0.75",
  },
  {
    key: "6",
    name: "合计/加权",
    scaleYi: "3,287.09",
    yieldPct: "2.18",
    excessBp: "+28",
    durationY: "2.94",
    maxDdPct: "-0.82",
  },
];

const columns: ColumnsType<Row> = [
  { title: "组合名称", dataIndex: "name", key: "name" },
  { title: "规模(亿)", dataIndex: "scaleYi", key: "scaleYi", align: "right" },
  { title: "收益率%", dataIndex: "yieldPct", key: "yieldPct", align: "right" },
  { title: "初额较bp", dataIndex: "excessBp", key: "excessBp", align: "right" },
  { title: "久期(年)", dataIndex: "durationY", key: "durationY", align: "right" },
  { title: "最大回撤%", dataIndex: "maxDdPct", key: "maxDdPct", align: "right" },
];

export function PerformanceComparison() {
  return (
    <SectionCard
      title="组合表现对比（年初至今）"
      style={{ ...panelStyle("#ffffff"), border: `1px solid ${BORDER}` }}
    >
      <Table size="small" pagination={false} dataSource={DATA} columns={columns} />
    </SectionCard>
  );
}

export default PerformanceComparison;
