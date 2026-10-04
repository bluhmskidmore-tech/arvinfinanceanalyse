import type { IndustryDistItem, IndustryDistPayload } from "../../../api/contracts";
import { DataTable, type DataTableColumn } from "../../../components/layout";
import type { BondSectionDataState } from "../sectionStatus";
import { formatRatePercent, formatYi } from "../utils/format";

/*
 * 占比分母口径（代码事实）：bond_dashboard_service._bond_dashboard_industry_payload
 * 以 Top-N 行合计为分母（repo 查询先 limit top_n 再求和），页面固定 topN=10，
 * 故列题口径为「Top10 内占比」，不是全组合占比。
 */
const INDUSTRY_COLUMNS: readonly DataTableColumn<IndustryDistItem>[] = [
  { key: "industry_name", title: "行业" },
  {
    key: "total_market_value",
    title: "金额",
    unit: "亿",
    align: "numeric",
    render: (row) => formatYi(row.total_market_value),
  },
  { key: "bond_count", title: "只数", align: "numeric" },
  {
    key: "percentage",
    title: "占比",
    unit: "%",
    align: "numeric",
    render: (row) => formatRatePercent(row.percentage),
  },
];

/** 页面固定请求 topN=10，骨架按同样行数占位，信封到达时不产生高度跳变。 */
const INDUSTRY_TOP_N = 10;

export function IndustryTable({
  data,
  state,
}: {
  data: IndustryDistPayload | undefined;
  state: BondSectionDataState;
}) {
  return (
    <div
      data-testid="bond-dashboard-industry-table"
      className="bond-dashboard-page__panel"
    >
      <div className="bond-dashboard-page__panel-head">
        <h3 className="bond-dashboard-page__panel-head-title">行业分布</h3>
        <span className="bond-dashboard-page__panel-head-note">占比为 Top10 内占比</span>
      </div>
      {/*
       * status 由分区级读取结果推导：loading 才出骨架，分区失败出错误面并说明原因，
       * ready 时 rows=[] 才是「暂无数据」。骨架只在真的在读时出现（§6）。
       */}
      <DataTable<IndustryDistItem>
        rows={data?.items}
        rowKey="industry_name"
        columns={INDUSTRY_COLUMNS}
        status={state.status}
        errorMessage={state.message ?? undefined}
        skeletonRows={INDUSTRY_TOP_N}
      />
    </div>
  );
}
