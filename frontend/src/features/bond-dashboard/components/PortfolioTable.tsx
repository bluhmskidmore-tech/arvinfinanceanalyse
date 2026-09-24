import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { BondDashboardHeadlinePayload, Numeric, PortfolioComparisonItem, PortfolioComparisonPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../pageModel";
import { formatDv01Wan, formatRatePercent, formatYears, formatYi, nativeToNumber } from "../utils/format";

/** 数值列等宽（BondDashboardTableSections.css，section 文件已 import）。 */
const NUM_CELL = "bond-dashboard-table-num-cell";

/** antd 已废弃 rowKey(record, index) 的 index 参数，行键改为建行时预生成（`key` 为 antd 默认 rowKey）。 */
type PortfolioRow = PortfolioComparisonItem & { key: string };

function sumComplete(values: (Numeric | null | undefined)[]): number | null {
  let sum = 0;
  for (const value of values) {
    const raw = nativeToNumber(value);
    if (raw === null) return null;
    sum += raw;
  }
  return sum;
}

const COLUMNS: ColumnsType<PortfolioRow> = [
  {
    title: "组合名称",
    dataIndex: "portfolio_name",
    key: "portfolio_name",
    // 后端存在空名组合行（真实数据观察），缺名按缺值纪律渲染 EM_DASH。
    render: (v: string) => (v && v.trim() ? v : EM_DASH),
  },
  {
    title: "规模(亿)",
    dataIndex: "total_market_value",
    key: "mv",
    align: "right",
    className: NUM_CELL,
    render: (v: Numeric) => formatYi(v),
  },
  {
    title: "收益率(%)",
    dataIndex: "weighted_ytm",
    key: "ytm",
    align: "right",
    className: NUM_CELL,
    render: (v: Numeric) => formatRatePercent(v),
  },
  {
    title: "久期(年)",
    dataIndex: "weighted_duration",
    key: "dur",
    align: "right",
    className: NUM_CELL,
    render: (v: Numeric) => formatYears(v),
  },
  {
    title: "DV01(万元/bp)",
    dataIndex: "total_dv01",
    key: "dv01",
    align: "right",
    className: NUM_CELL,
    render: (v: Numeric) => formatDv01Wan(v),
  },
  { title: "数量", dataIndex: "bond_count", key: "n", align: "right", className: NUM_CELL },
];

export function PortfolioTable({
  data,
  headline,
  loading,
}: {
  data: PortfolioComparisonPayload | undefined;
  headline: BondDashboardHeadlinePayload | undefined;
  loading: boolean;
}) {
  const rows: PortfolioRow[] = (data?.items ?? []).map((item, index) => ({
    ...item,
    key: item.portfolio_name && item.portfolio_name.trim() ? item.portfolio_name : `unnamed-${index}`,
  }));
  const totalMv = sumComplete(rows.map((r) => r.total_market_value));
  const totalDv01 = sumComplete(rows.map((r) => r.total_dv01));
  const totalBonds = rows.reduce((s, r) => s + r.bond_count, 0);

  return (
    <div className="bond-dashboard-page__panel bond-dashboard-table-panel">
      <h3 className="bond-dashboard-table-panel__title">组合表现</h3>
      {loading ? (
        <p className="bond-dashboard-page__surface bond-dashboard-page__surface--loading">
          载入中…
        </p>
      ) : rows.length === 0 ? (
        <p className="bond-dashboard-page__surface bond-dashboard-page__surface--empty">
          暂无数据
        </p>
      ) : (
        <Table<PortfolioRow>
          size="small"
          pagination={false}
          columns={COLUMNS}
          dataSource={rows}
          scroll={{ x: "max-content" }}
          summary={() => (
            <Table.Summary fixed>
              <Table.Summary.Row>
                <Table.Summary.Cell index={0}>
                  <strong>合计 / 后端加权</strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={1} align="right" className={NUM_CELL}>
                  <strong>{formatYi(totalMv)}</strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={2} align="right" className={NUM_CELL}>
                  <strong data-testid="bond-dashboard-portfolio-summary-ytm">
                    {headline ? formatRatePercent(headline.kpis.weighted_ytm) : EM_DASH}
                  </strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={3} align="right" className={NUM_CELL}>
                  <strong data-testid="bond-dashboard-portfolio-summary-duration">
                    {headline ? formatYears(headline.kpis.weighted_duration) : EM_DASH}
                  </strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={4} align="right" className={NUM_CELL}>
                  <strong>{formatDv01Wan(totalDv01)}</strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={5} align="right" className={NUM_CELL}>
                  <strong>{totalBonds}</strong>
                </Table.Summary.Cell>
              </Table.Summary.Row>
            </Table.Summary>
          )}
        />
      )}
    </div>
  );
}
