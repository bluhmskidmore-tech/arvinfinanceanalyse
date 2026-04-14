import { Card, Table, Typography } from "antd";

import type { LiabilityCpRow } from "./LiabilityCounterpartyBlock";

const { Text } = Typography;

export function LiabilityCustomerTable({
  rows,
  loading,
  subtitle,
}: {
  rows: LiabilityCpRow[];
  loading: boolean;
  subtitle?: string;
}) {
  return (
    <Card
      size="small"
      title="客户维度明细表（业务规模 & 加权负债成本）"
      extra={<Text type="secondary">客户数：{loading ? "—" : rows.length}</Text>}
    >
      {subtitle ? (
        <Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 8 }}>
          {subtitle}
        </Text>
      ) : null}
      <Table<LiabilityCpRow & { key: string }>
        size="small"
        loading={loading}
        pagination={false}
        scroll={{ x: 900, y: 460 }}
        dataSource={rows.map((r, idx) => ({ ...r, key: `${r.name}-${idx}` }))}
        columns={[
          { title: "对手方/客户", dataIndex: "name", ellipsis: true },
          {
            title: "业务规模(亿元)",
            dataIndex: "valueYuan",
            align: "right",
            render: (v: number) => (v / 1e8).toFixed(2),
          },
          {
            title: "占比",
            dataIndex: "pct",
            align: "right",
            render: (v: number) => `${v.toFixed(2)}%`,
          },
          {
            title: "加权负债成本",
            dataIndex: "weightedCost",
            align: "right",
            render: (v: number | null) =>
              v === null || v === undefined ? "—" : `${(Number(v) * 100).toFixed(2)}%`,
          },
          {
            title: "类型",
            dataIndex: "type",
            ellipsis: true,
            render: (v: string) => v || "—",
          },
        ]}
      />
    </Card>
  );
}
