import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { IndustryDistItem, IndustryDistPayload, Numeric } from "../../../api/contracts";
import { formatRatePercent, formatYi } from "../utils/format";

/*
 * 占比分母口径（代码事实）：bond_dashboard_service._bond_dashboard_industry_payload
 * 以 Top-N 行合计为分母（repo 查询先 limit top_n 再求和），页面固定 topN=10，
 * 故列题口径为「Top10 内占比」，不是全组合占比。
 */
const INDUSTRY_COLUMNS: ColumnsType<IndustryDistItem> = [
  { title: "行业", dataIndex: "industry_name", key: "industry_name" },
  {
    title: "金额(亿)",
    dataIndex: "total_market_value",
    key: "mv",
    align: "right",
    render: (v: Numeric) => formatYi(v),
  },
  {
    title: "只数",
    dataIndex: "bond_count",
    key: "bond_count",
    align: "right",
  },
  {
    title: "占比(%)",
    dataIndex: "percentage",
    key: "pct",
    align: "right",
    render: (v: Numeric | null) => formatRatePercent(v),
  },
];

export function IndustryTable({
  data,
  loading,
}: {
  data: IndustryDistPayload | undefined;
  loading: boolean;
}) {
  const items = data?.items ?? [];

  return (
    <div
      data-testid="bond-dashboard-industry-table"
      className="bond-dashboard-page__panel bond-dashboard-charts__panel"
    >
      <div className="bond-dashboard-charts__head">
        <h3 className="bond-dashboard-charts__head-title">行业分布</h3>
        <span className="bond-dashboard-charts__head-note">占比为 Top10 内占比</span>
      </div>
      {loading ? (
        <p className="bond-dashboard-page__surface bond-dashboard-page__surface--loading">
          载入中…
        </p>
      ) : data && items.length === 0 ? (
        /* 仅真实空 payload 收敛为暂无数据；envelope 未到达时保留空表骨架防高度跳变。 */
        <p className="bond-dashboard-page__surface bond-dashboard-page__surface--empty">
          暂无数据
        </p>
      ) : (
        <Table<IndustryDistItem>
          size="small"
          pagination={false}
          rowKey={(r) => r.industry_name}
          columns={INDUSTRY_COLUMNS}
          dataSource={items}
          scroll={{ x: "max-content" }}
        />
      )}
    </div>
  );
}
