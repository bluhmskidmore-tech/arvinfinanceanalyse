import type { SpreadAnalysisItem, SpreadAnalysisPayload } from "../../../api/contracts";
import { DataTable, type DataTableColumn } from "../../../components/layout";
import type { BondSectionDataState } from "../sectionStatus";
import { formatRatePercent, formatYi } from "../utils/format";

const COLUMNS: readonly DataTableColumn<SpreadAnalysisItem>[] = [
  { key: "bond_type", title: "券种" },
  {
    key: "median_yield",
    title: "收益率中位数",
    unit: "%",
    align: "numeric",
    render: (row) => formatRatePercent(row.median_yield),
  },
  { key: "bond_count", title: "数量", align: "numeric" },
  {
    key: "total_market_value",
    title: "市值",
    unit: "亿",
    align: "numeric",
    render: (row) => formatYi(row.total_market_value),
  },
];

export function SpreadTable({
  data,
  state,
}: {
  data: SpreadAnalysisPayload | undefined;
  state: BondSectionDataState;
}) {
  return (
    <div className="bond-dashboard-page__panel">
      <div className="bond-dashboard-page__panel-head">
        <h3 className="bond-dashboard-page__panel-head-title">利差分析</h3>
      </div>
      {/* 状态推导同行业分布表：骨架只在真的在读时出现，分区失败出错误面。 */}
      <DataTable<SpreadAnalysisItem>
        rows={data?.items}
        rowKey="bond_type"
        columns={COLUMNS}
        status={state.status}
        errorMessage={state.message ?? undefined}
        skeletonRows={5}
      />
    </div>
  );
}
