import { Table } from "antd";

import type { Numeric } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { counterpartyTypeLabel, unsignedNumericDisplay } from "../utils/labels";
import { numericToYiNumeric } from "../utils/money";
import type { LiabilityCpRow } from "./LiabilityCounterpartyBlock";

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
    <div className="liability-panel liability-customer-table">
      <div className="liability-panel__head">
        <h3 className="liability-panel__title">客户维度明细表（业务规模与加权负债成本）</h3>
        <span className="liability-panel__meta">客户数：{loading ? EM_DASH : rows.length}</span>
      </div>
      {subtitle ? <p className="liability-caption">{subtitle}</p> : null}
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
            // 成本是水平值不是变动量，剥掉 sign_aware 的前导「+」。
            render: (value: Numeric | null) => unsignedNumericDisplay(value),
          },
          {
            title: "类型",
            dataIndex: "type",
            ellipsis: true,
            render: (value: string) => counterpartyTypeLabel(value) || EM_DASH,
          },
        ]}
      />
    </div>
  );
}
