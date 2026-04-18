import { Button, Card, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { IndustryDistItem, IndustryDistPayload } from "../../../api/contracts";
import { formatYi, nativeToNumber } from "../utils/format";

export function IndustryTable({
  data,
  loading,
}: {
  data: IndustryDistPayload | undefined;
  loading: boolean;
}) {
  const columns: ColumnsType<IndustryDistItem> = [
    { title: "行业", dataIndex: "industry_name", key: "industry_name" },
    {
      title: "金额(亿)",
      dataIndex: "total_market_value",
      key: "mv",
      align: "right",
      render: (v: string) => formatYi(v),
    },
    {
      title: "占比(%)",
      dataIndex: "percentage",
      key: "pct",
      align: "right",
      render: (v: string) => nativeToNumber(v).toFixed(2),
    },
  ];

  return (
    <Card
      data-testid="bond-dashboard-industry-table"
      loading={loading}
      title="行业分布"
      extra={<Button type="link">更多</Button>}
      style={{ borderRadius: 8 }}
      styles={{ body: { padding: 0 } }}
    >
      <Table<IndustryDistItem>
        size="small"
        pagination={false}
        rowKey={(r) => r.industry_name}
        columns={columns}
        dataSource={data?.items ?? []}
      />
    </Card>
  );
}
