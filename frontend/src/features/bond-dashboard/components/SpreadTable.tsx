import { Button, Card, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { SpreadAnalysisItem, SpreadAnalysisPayload } from "../../../api/contracts";
import { formatRatePercent, formatYi } from "../utils/format";

export function SpreadTable({
  data,
  loading,
}: {
  data: SpreadAnalysisPayload | undefined;
  loading: boolean;
}) {
  const columns: ColumnsType<SpreadAnalysisItem> = [
    { title: "券种", dataIndex: "bond_type", key: "bond_type" },
    {
      title: "收益率中位数(%)",
      dataIndex: "median_yield",
      key: "my",
      align: "right",
      render: (v: string) => formatRatePercent(v),
    },
    { title: "数量", dataIndex: "bond_count", key: "n", align: "right" },
    {
      title: "市值(亿)",
      dataIndex: "total_market_value",
      key: "mv",
      align: "right",
      render: (v: string) => formatYi(v),
    },
  ];

  return (
    <Card
      loading={loading}
      title="利差分析"
      extra={<Button type="link">更多</Button>}
      style={{ borderRadius: 8 }}
      styles={{ body: { padding: 0 } }}
    >
      <Table<SpreadAnalysisItem>
        size="small"
        pagination={false}
        rowKey={(r) => r.bond_type}
        columns={columns}
        dataSource={data?.items ?? []}
      />
    </Card>
  );
}
