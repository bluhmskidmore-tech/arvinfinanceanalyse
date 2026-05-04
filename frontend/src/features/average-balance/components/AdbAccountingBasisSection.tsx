import { Card, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import type {
  AdbAccountingBasisDailyAvg,
  AdbAccountingBasisDailyAvgTrendItem,
} from "../../../api/contracts";
import AdbAccountingBasisTrendChart from "./AdbAccountingBasisTrendChart";

const YI = 100_000_000;
const { Text, Paragraph } = Typography;

type Row = {
  key: string;
  basis_bucket: string;
  daily_avg_yi: number;
  daily_avg_pct: number | null;
};

function buildSnapshotRows(snapshot: AdbAccountingBasisDailyAvg): Row[] {
  return snapshot.rows.map((r, i) => ({
    key: `${r.basis_bucket}-${i}`,
    basis_bucket: r.basis_bucket || "—",
    daily_avg_yi: r.daily_avg_balance / YI,
    daily_avg_pct: r.daily_avg_pct,
  }));
}

const snapshotColumns: ColumnsType<Row> = [
  { title: "分桶", dataIndex: "basis_bucket", key: "basis_bucket" },
  {
    title: "日均（亿元）",
    dataIndex: "daily_avg_yi",
    key: "daily_avg_yi",
    align: "right",
    render: (v: number) => v.toFixed(2),
  },
  {
    title: "占比（%）",
    dataIndex: "daily_avg_pct",
    key: "daily_avg_pct",
    align: "right",
    render: (v: number | null) => (v === null || v === undefined ? "—" : `${v.toFixed(2)}%`),
  },
];

type AdbAccountingBasisSectionProps = {
  /** 区间末附近一日的分桶结构（与 comparison 同包）。 */
  snapshot?: AdbAccountingBasisDailyAvg;
  /** 按日或按月的分桶序列（后端非空时展示）。 */
  trend?: AdbAccountingBasisDailyAvgTrendItem[];
  titleSuffix?: string;
};

/**
 * IFRS9 会计分桶日均：仅展示后端已算字段，不在前端重算正式口径。
 */
export default function AdbAccountingBasisSection({
  snapshot,
  trend,
  titleSuffix = "",
}: AdbAccountingBasisSectionProps) {
  if (!snapshot && !(trend && trend.length)) return null;

  const suffix = titleSuffix ? ` — ${titleSuffix}` : "";

  return (
    <Card
      size="small"
      data-testid="adb-accounting-basis-section"
      title={`会计计量分桶 · 日均结构${suffix}`}
    >
      <Space direction="vertical" size="middle" style={{ width: "100%" }}>
        <Text type="secondary">
          与「债券+同业」大类日均并列阅读；分桶口径以后端 rule_version / source_version 为准。
        </Text>
        {snapshot && snapshot.rows.length > 0 ? (
          <div>
            <Text strong>
              参考日 {snapshot.report_date || "—"}
              {snapshot.currency_basis ? ` · ${snapshot.currency_basis}` : ""}
            </Text>
            {snapshot.accounting_controls.length > 0 ? (
              <Paragraph type="secondary" style={{ marginBottom: 8, fontSize: 12 }}>
                控制项：{snapshot.accounting_controls.join("；")}
              </Paragraph>
            ) : null}
            <Table<Row>
              size="small"
              pagination={false}
              rowKey={(r) => r.key}
              columns={snapshotColumns}
              dataSource={buildSnapshotRows(snapshot)}
            />
          </div>
        ) : null}
        {trend && trend.length > 1 ? (
          <div data-testid="adb-accounting-basis-trend-chart">
            <Text strong style={{ display: "block", marginBottom: 8 }}>
              分桶日均走势（亿元）
            </Text>
            <AdbAccountingBasisTrendChart trend={trend} />
          </div>
        ) : null}
      </Space>
    </Card>
  );
}
