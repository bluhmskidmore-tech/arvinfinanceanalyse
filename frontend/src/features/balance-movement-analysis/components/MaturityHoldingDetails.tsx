import { useState } from "react";
import { Input, Table } from "antd";
import type { BalanceZqtzMaturityBucket } from "../../../api/contracts/balanceLedger";
import { EM_DASH, formatYuanAmountAsYiPlain as formatYiCell } from "../../../utils/format";

export function MaturityHoldingDetails({ bucket: selectedBucket, reportDate }: {
  bucket: BalanceZqtzMaturityBucket | undefined;
  reportDate: string;
}) {
  const [search, setSearch] = useState("");
  const selectedKey = selectedBucket?.maturity_bucket;
  const selectedItems = selectedBucket?.items?.filter((item) =>
    `${item.instrument_code} ${item.instrument_name} ${item.portfolio_name}`.toLowerCase().includes(search.toLowerCase()),
  );
  return (
      <div className="balance-movement-maturity-detail" data-testid="balance-movement-maturity-detail">
        <h3>{selectedBucket?.bucket_label ?? "请选择期限桶"}：持仓明细</h3>
        <p>本金或利息逾期天数大于零表示来源已记录逾期；零天不等于已结清，缺失值表示来源未提供。</p>
        <Input aria-label="搜索期限桶持仓" placeholder="搜索证券代码、名称或组合" value={search} onChange={(event) => setSearch(event.target.value)} allowClear />
        {selectedItems === undefined ? <p>当前接口未提供该桶持仓明细。</p> : (
          <Table
            key={`${reportDate}:${selectedKey}:${search}`}
            size="small"
            dataSource={selectedItems.map((item, index) => ({ ...item, key: index }))}
            pagination={{ pageSize: 10, showSizeChanger: false, hideOnSinglePage: true }}
            scroll={{ x: 1050 }}
            locale={{ emptyText: "当前筛选下无持仓" }}
            columns={[
              { title: "证券代码", dataIndex: "instrument_code", render: (value: string) => value || EM_DASH },
              { title: "名称", dataIndex: "instrument_name", render: (value: string) => value || EM_DASH },
              { title: "组合", dataIndex: "portfolio_name", render: (value: string) => value || EM_DASH },
              { title: "会计分类", dataIndex: "accounting_basis", render: (value: string) => value || EM_DASH },
              { title: "余额（亿元）", dataIndex: "current_amount", align: "right", render: (value: string) => <span title={`${value} 元`}>{formatYiCell(value)}</span> },
              { title: "来源到期日", dataIndex: "maturity_date", render: (value: string | null) => value || EM_DASH },
              { title: "本金逾期天数", dataIndex: "overdue_principal_days", align: "right", render: (value: number | null) => <span className={value !== null && value > 0 ? "balance-movement-tone--warning" : undefined}>{value ?? EM_DASH}</span> },
              { title: "利息逾期天数", dataIndex: "overdue_interest_days", align: "right", render: (value: number | null) => <span className={value !== null && value > 0 ? "balance-movement-tone--warning" : undefined}>{value ?? EM_DASH}</span> },
            ]}
          />
        )}
      </div>
  );
}
