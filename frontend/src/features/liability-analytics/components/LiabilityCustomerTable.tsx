import { Card, Table, Typography } from "antd";

import type { Numeric } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { numericToYiNumeric } from "../utils/money";
import type { LiabilityCpRow } from "./LiabilityCounterpartyBlock";

const { Text } = Typography;

function numericDisplay(value: Numeric | null | undefined): string {
  return value?.display ?? EM_DASH;
}

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
      className="liability-customer-table"
      title="客户维度明细表（业务规模与加权负债成本）"
      extra={<Text type="secondary">客户数：{loading ? EM_DASH : rows.length}</Text>}
    >
      {subtitle ? (
        <Text type="secondary" className="liability-table-caption">
          {subtitle}
        </Text>
      ) : null}
      <Table<LiabilityCpRow & { key: string }>
        size="small"
        loading={loading}
        pagination={false}
        locale={{ emptyText: "暂无数据" }}
        scroll={{ x: 900, y: 460 }}
        dataSource={rows.map((row, index) => ({ ...row, key: `${row.name}-${index}` }))}
        columns={[
          { title: "对手方/客户", dataIndex: "name", ellipsis: true },
          {
            title: "业务规模(亿元)",
            dataIndex: "value",
            align: "right",
            render: (value: Numeric | null) => numericDisplay(numericToYiNumeric(value)),
          },
          {
            title: "占比",
            dataIndex: "share",
            align: "right",
            render: (value: Numeric | null) => numericDisplay(value),
          },
          {
            title: "加权负债成本",
            dataIndex: "weightedCost",
            align: "right",
            render: (value: Numeric | null) => numericDisplay(value),
          },
          {
            title: "类型",
            dataIndex: "type",
            ellipsis: true,
            render: (value: string) => value || EM_DASH,
          },
        ]}
      />
    </Card>
  );
}
