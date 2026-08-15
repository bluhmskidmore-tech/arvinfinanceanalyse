import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { Numeric, SpreadAnalysisItem, SpreadAnalysisPayload } from "../../../api/contracts";
import { formatRatePercent, formatYi } from "../utils/format";

/** 数值列等宽（BondDashboardTableSections.css，section 文件已 import）。 */
const NUM_CELL = "bond-dashboard-table-num-cell";

const COLUMNS: ColumnsType<SpreadAnalysisItem> = [
  { title: "券种", dataIndex: "bond_type", key: "bond_type" },
  {
    title: "收益率中位数(%)",
    dataIndex: "median_yield",
    key: "my",
    align: "right",
    className: NUM_CELL,
    render: (v: Numeric | null) => formatRatePercent(v),
  },
  { title: "数量", dataIndex: "bond_count", key: "n", align: "right", className: NUM_CELL },
  {
    title: "市值(亿)",
    dataIndex: "total_market_value",
    key: "mv",
    align: "right",
    className: NUM_CELL,
    render: (v: Numeric) => formatYi(v),
  },
];

export function SpreadTable({
  data,
  loading,
}: {
  data: SpreadAnalysisPayload | undefined;
  loading: boolean;
}) {
  const rows = data?.items ?? [];

  return (
    <div className="bond-dashboard-page__panel bond-dashboard-table-panel">
      <h3 className="bond-dashboard-table-panel__title">利差分析</h3>
      {loading ? (
        <p className="bond-dashboard-page__surface bond-dashboard-page__surface--loading">
          载入中…
        </p>
      ) : rows.length === 0 ? (
        <p className="bond-dashboard-page__surface bond-dashboard-page__surface--empty">
          暂无数据
        </p>
      ) : (
        <Table<SpreadAnalysisItem>
          size="small"
          pagination={false}
          rowKey={(r) => r.bond_type}
          columns={COLUMNS}
          dataSource={rows}
          scroll={{ x: "max-content" }}
        />
      )}
    </div>
  );
}
