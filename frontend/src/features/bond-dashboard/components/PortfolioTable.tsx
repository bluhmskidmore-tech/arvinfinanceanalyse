import type {
  BondDashboardHeadlinePayload,
  Numeric,
  PortfolioComparisonItem,
  PortfolioComparisonPayload,
} from "../../../api/contracts";
import {
  DataTable,
  type DataTableColumn,
  type DataTableSummaryRow,
} from "../../../components/layout";
import { EM_DASH } from "../../../pageModel";
import type { BondSectionDataState } from "../sectionStatus";
import { formatDv01Wan, formatRatePercent, formatYears, formatYi, nativeToNumber } from "../utils/format";

function sumComplete(values: (Numeric | null | undefined)[]): number | null {
  let sum = 0;
  for (const value of values) {
    const raw = nativeToNumber(value);
    if (raw === null) return null;
    sum += raw;
  }
  return sum;
}

const COLUMNS: readonly DataTableColumn<PortfolioComparisonItem>[] = [
  {
    key: "portfolio_name",
    title: "组合名称",
    // 后端存在空名组合行（真实数据观察），缺名按缺值纪律渲染 EM_DASH。
    render: (row) => (row.portfolio_name && row.portfolio_name.trim() ? row.portfolio_name : EM_DASH),
  },
  {
    key: "total_market_value",
    title: "规模",
    unit: "亿",
    align: "numeric",
    render: (row) => formatYi(row.total_market_value),
  },
  {
    key: "weighted_ytm",
    title: "收益率",
    unit: "%",
    align: "numeric",
    render: (row) => formatRatePercent(row.weighted_ytm),
  },
  {
    key: "weighted_duration",
    title: "久期",
    unit: "年",
    align: "numeric",
    render: (row) => formatYears(row.weighted_duration),
  },
  {
    key: "total_dv01",
    title: "DV01",
    unit: "万元/bp",
    align: "numeric",
    render: (row) => formatDv01Wan(row.total_dv01),
  },
  { key: "bond_count", title: "数量", align: "numeric" },
];

export function PortfolioTable({
  data,
  headline,
  state,
}: {
  data: PortfolioComparisonPayload | undefined;
  headline: BondDashboardHeadlinePayload | undefined;
  state: BondSectionDataState;
}) {
  const rows = data?.items ?? [];
  const totalMv = sumComplete(rows.map((r) => r.total_market_value));
  const totalDv01 = sumComplete(rows.map((r) => r.total_dv01));
  const totalBonds = rows.reduce((s, r) => s + r.bond_count, 0);

  /* 收益率/久期合计取后端 headline 加权值，不在前端按行重算加权。 */
  const summaryRow: DataTableSummaryRow = {
    portfolio_name: "合计 / 后端加权",
    total_market_value: formatYi(totalMv),
    weighted_ytm: (
      <span data-testid="bond-dashboard-portfolio-summary-ytm">
        {headline ? formatRatePercent(headline.kpis.weighted_ytm) : EM_DASH}
      </span>
    ),
    weighted_duration: (
      <span data-testid="bond-dashboard-portfolio-summary-duration">
        {headline ? formatYears(headline.kpis.weighted_duration) : EM_DASH}
      </span>
    ),
    total_dv01: formatDv01Wan(totalDv01),
    bond_count: totalBonds,
  };

  return (
    <div className="bond-dashboard-page__panel">
      <div className="bond-dashboard-page__panel-head">
        <h3 className="bond-dashboard-page__panel-head-title">组合表现</h3>
      </div>
      {/* 状态推导同行业分布表：骨架只在真的在读时出现，分区失败出错误面。 */}
      <DataTable<PortfolioComparisonItem>
        rows={data?.items}
        rowKey="portfolio_name"
        columns={COLUMNS}
        status={state.status}
        errorMessage={state.message ?? undefined}
        summaryRow={summaryRow}
        skeletonRows={6}
      />
    </div>
  );
}
