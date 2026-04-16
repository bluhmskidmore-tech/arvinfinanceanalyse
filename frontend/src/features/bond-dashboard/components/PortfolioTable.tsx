import { Button, Card, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type {
  PortfolioComparisonItem,
  PortfolioComparisonPayload,
} from "../../../api/contracts";
import {
  formatDv01Wan,
  formatRatePercent,
  formatYi,
  nativeToNumber,
} from "../utils/format";

export function PortfolioTable({
  data,
  loading,
}: {
  data: PortfolioComparisonPayload | undefined;
  loading: boolean;
}) {
  const rows = data?.items ?? [];

  const columns: ColumnsType<PortfolioComparisonItem> = [
    { title: "组合名称", dataIndex: "portfolio_name", key: "portfolio_name" },
    {
      title: "规模(亿)",
      dataIndex: "total_market_value",
      key: "mv",
      align: "right",
      render: (value: string) => formatYi(value),
    },
    {
      title: "收益率(%)",
      dataIndex: "weighted_ytm",
      key: "ytm",
      align: "right",
      render: (value: string) => formatRatePercent(value),
    },
    {
      title: "久期(年)",
      dataIndex: "weighted_duration",
      key: "dur",
      align: "right",
      render: (value: string) => nativeToNumber(value).toFixed(2),
    },
    {
      title: "DV01(万元)",
      dataIndex: "total_dv01",
      key: "dv01",
      align: "right",
      render: (value: string) => formatDv01Wan(value),
    },
    { title: "数量", dataIndex: "bond_count", key: "n", align: "right" },
  ];

  return (
    <Card
      loading={loading}
      title="组合表现"
      extra={<Button type="link">更多</Button>}
      style={{ borderRadius: 8 }}
      styles={{ body: { padding: 0 } }}
    >
      <Table<PortfolioComparisonItem>
        size="small"
        pagination={false}
        rowKey={(row) => row.portfolio_name}
        columns={columns}
        dataSource={rows}
      />
    </Card>
  );
}
