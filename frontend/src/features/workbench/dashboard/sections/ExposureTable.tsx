import { tabularNumsStyle } from "../../../../theme/designSystem";
import type { DashboardExposureRowMock } from "../dashboardMockData";
import { resolveKpiDeltaClass } from "../dashboardCockpitHomeModel";

type ExposureTableProps = {
  rows: readonly DashboardExposureRowMock[];
};

export function ExposureTable({ rows }: ExposureTableProps) {
  return (
    <section
      data-testid="dashboard-exposure-table"
      className="dashboard-cockpit-panel dashboard-cockpit-panel--table"
    >
      <header className="dashboard-cockpit-panel__head">
        <span className="dashboard-cockpit-panel__eyebrow">账户暴露</span>
        <h2 className="dashboard-cockpit-panel__title">账户与暴露摘要</h2>
      </header>
      <div className="dashboard-cockpit-table-wrap">
        <table className="dashboard-cockpit-table">
          <thead>
            <tr>
              <th>账户</th>
              <th>类型</th>
              <th>资产规模（亿）</th>
              <th>占比</th>
              <th>久期（年）</th>
              <th>DV01（万）</th>
              <th>日收益（万）</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.account}</td>
                <td>{row.type}</td>
                <td style={tabularNumsStyle}>{row.assetScale}</td>
                <td style={tabularNumsStyle}>{row.weight}</td>
                <td style={tabularNumsStyle}>{row.duration}</td>
                <td style={tabularNumsStyle}>{row.dv01}</td>
                <td className={resolveKpiDeltaClass(row.tone === "positive" ? "up" : row.tone === "negative" ? "down" : "flat")}>
                  {row.dailyPnl}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
